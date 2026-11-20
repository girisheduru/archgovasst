"""Export or publish the governance benchmark dataset and Prompt Hub templates."""

import argparse
import json
from hashlib import sha256
from os import getenv
from pathlib import Path

from ..agent.evidence import Extraction, GapGuidance
from ..agent.prompts import EVIDENCE_EXTRACTION, GAP_GUIDANCE, PASSAGE_EXTRACTION
from .dataset import load_dataset
from .experiment import build_dataset, publish_dataset
from .judge import JUDGE_INSTRUCTIONS, Judgment


def build_prompts(model: str):
    specs = (
        ("evidence-extraction", EVIDENCE_EXTRACTION, Extraction, "Extract evidence from a full design or supporting document."),
        ("passage-extraction", PASSAGE_EXTRACTION, Extraction, "Extract evidence from ranked design passages."),
        ("gap-guidance", GAP_GUIDANCE, GapGuidance, "Suggest what evidence to provide for a rule."),
        ("review-judge", JUDGE_INSTRUCTIONS, Judgment, "Grade an exported review against its source and answer key."),
    )
    return [
        {
            "name": f"governance-{name}",
            "description": description,
            "model": model,
            "provider": "OPEN_AI",
            "input_variable_format": "F_STRING",
            "messages": [
                {"role": "SYSTEM", "content": instructions},
                {"role": "USER", "content": "{payload}"},
            ],
            "response_schema": schema.model_json_schema(),
        }
        for name, instructions, schema, description in specs
    ]


def publish_prompt(client, space: str, template: dict):
    from arize.prompts.types import InputVariableFormat, LlmProvider, LLMMessageRequest

    name = template["name"]
    fingerprint = sha256(json.dumps(template, sort_keys=True).encode()).hexdigest()[:16]
    commit_message = f"Publish app prompt {fingerprint}"
    fields = {
        "commit_message": commit_message,
        "model": template["model"],
        "provider": LlmProvider(template["provider"]),
        "input_variable_format": InputVariableFormat(template["input_variable_format"]),
        "messages": [LLMMessageRequest(**message) for message in template["messages"]],
    }
    prompts = client.prompts.list(space=space, name=name).prompts or []
    existing = next((item for item in prompts if item.name == name), None)
    if existing is None:
        prompt = client.prompts.create(space=space, name=name, description=template["description"], **fields)
        return {"name": name, "prompt_id": prompt.id, "version_id": prompt.version.id}

    current = client.prompts.get(prompt=existing.id)
    version = current.version
    if version is None or version.commit_message != commit_message:
        version = client.prompts.create_version(prompt=existing.id, **fields)
    return {"name": name, "prompt_id": existing.id, "version_id": version.id}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--export", type=Path, help="Write a local JSON bundle without contacting Arize.")
    mode.add_argument("--env-file", type=Path, help="Load credentials from this file during local publishing.")
    args = parser.parse_args()

    if args.env_file:
        from dotenv import load_dotenv

        if not args.env_file.is_file():
            parser.error(f"Environment file not found: {args.env_file}")
        load_dotenv(args.env_file, override=True)
    space = getenv("ARIZE_SPACE_ID", "").strip()
    api_key = getenv("ARIZE_API_KEY", "").strip()
    if not args.export and not (space and api_key):
        parser.error("Set ARIZE_SPACE_ID and ARIZE_API_KEY or supply --env-file.")

    cases, rules = load_dataset()
    dataset = build_dataset(cases, rules)
    prompts = build_prompts(getenv("OPENAI_MODEL", "gpt-6-luna"))
    if args.export:
        args.export.write_text(json.dumps({"dataset": dataset, "prompts": prompts}, indent=2) + "\n", encoding="utf-8")
        print(f"Exported {len(cases)} designs and {len(prompts)} prompts to {args.export}.")
        return

    from arize import ArizeClient

    client = ArizeClient(api_key=api_key)
    published_dataset = publish_dataset(client, space, dataset)
    print(json.dumps({"dataset_name": dataset["name"], "dataset_id": published_dataset.id}), flush=True)
    for template in prompts:
        print(json.dumps(publish_prompt(client, space, template)), flush=True)


if __name__ == "__main__":
    main()
