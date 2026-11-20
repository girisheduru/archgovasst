"""Export or publish the governance benchmark dataset and Prompt Hub templates."""

import argparse
import json
from contextlib import contextmanager
from hashlib import sha256
from logging import getLogger
from os import getenv
from pathlib import Path

from ..agent.evidence import Extraction, GapGuidance
from ..agent.prompts import EVIDENCE_EXTRACTION, GAP_GUIDANCE, PASSAGE_EXTRACTION
from ..performance import save_report
from .dataset import load_dataset
from .experiment import build_dataset, publish_dataset
from .judge import JUDGE_INSTRUCTIONS, Judgment

logger = getLogger(__name__)
SAVE_REPORT = "Saving the Arize publication report"


class ArizePublicationError(RuntimeError):
    def __init__(self, phase: str, cause: Exception):
        self.phase = phase
        self.error_type = type(cause).__name__
        status = getattr(cause, "status", None) or getattr(cause, "status_code", None)
        self.status = status if isinstance(status, int) and 100 <= status < 600 else None
        hint = {
            400: "Arize rejected the request. Check the configured space and the backend SDK version.",
            401: "Arize rejected the API key. Check ARIZE_EVAL_API_KEY or ARIZE_API_KEY on the backend.",
            403: "Arize denied access. Set ARIZE_EVAL_API_KEY to a key with publishing permissions in the configured space.",
            404: "Arize could not find the resource. Check ARIZE_SPACE_ID and the Arize region.",
            409: "Arize reported a conflict. Retry after any other publication finishes.",
            422: "Arize rejected the request. Check the configured space and the backend SDK version.",
            429: "Arize rate limited the request. Try again shortly.",
        }.get(self.status, "Check the backend logs.")
        if phase == SAVE_REPORT:
            message = "Arize assets were published. Set PERFORMANCE_REPORT_DIR to a directory the backend can write to so the dashboard can display the IDs."
        else:
            if isinstance(cause, ImportError):
                hint = "Install the backend requirements and redeploy."
            elif phase == "Loading bundled benchmark fixtures":
                hint = "Check that the deployment includes backend/datadocs and run Validate benchmark fixtures."
            elif self.error_type in ("NotFoundError", "AmbiguousNameError"):
                hint = "Check ARIZE_SPACE_ID, the Arize region, and the API key's access to that space."
            status = f" (HTTP {self.status})" if self.status else ""
            message = f"Failed while {phase[:1].lower() + phase[1:]}{status}. {hint}"
        super().__init__(message)


@contextmanager
def publication_step(phase: str, on_phase):
    if on_phase:
        on_phase(phase)
    try:
        yield
    except Exception as exc:
        raise ArizePublicationError(phase, exc) from exc


def connect_arize(api_key: str, on_phase=None):
    with publication_step("Initializing the Arize AX client", on_phase):
        from arize import ArizeClient

        return ArizeClient(api_key=api_key)


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


def arize_api_key():
    return getenv("ARIZE_EVAL_API_KEY", "").strip() or getenv("ARIZE_API_KEY", "").strip()


def publish_assets(client, space: str, dataset: dict, model: str, on_phase=None):
    with publication_step("Publishing the dataset", on_phase):
        published_dataset = publish_dataset(client, space, dataset)
    summary = {
        "space_id": space,
        "dataset_name": dataset["name"],
        "dataset_id": published_dataset.id,
        "prompts": [],
    }
    try:
        with publication_step("Preparing the Prompt Hub templates", on_phase):
            templates = build_prompts(model)
        for template in templates:
            with publication_step(f"Publishing Prompt Hub template {template['name']}", on_phase):
                summary["prompts"].append(publish_prompt(client, space, template))
    except ArizePublicationError:
        try:
            save_report("assets", summary)
        except OSError as exc:
            logger.warning("Could not save the partial Arize publication report (%s).", type(exc).__name__)
        raise
    with publication_step(SAVE_REPORT, on_phase):
        save_report("assets", summary)
    return published_dataset, summary


def publish_bundled_assets(space: str, api_key: str, on_phase=None):
    with publication_step("Loading bundled benchmark fixtures", on_phase):
        cases, rules = load_dataset()
        dataset = build_dataset(cases, rules)
    model = getenv("OPENAI_MODEL", "gpt-6-luna")
    client = connect_arize(api_key, on_phase)
    _, summary = publish_assets(client, space, dataset, model, on_phase=on_phase)
    return summary


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
    api_key = arize_api_key()
    if not args.export and not (space and api_key):
        parser.error("Set ARIZE_SPACE_ID and an Arize API key or supply --env-file.")

    if args.export:
        cases, rules = load_dataset()
        dataset = build_dataset(cases, rules)
        prompts = build_prompts(getenv("OPENAI_MODEL", "gpt-6-luna"))
        args.export.write_text(json.dumps({"dataset": dataset, "prompts": prompts}, indent=2) + "\n", encoding="utf-8")
        print(f"Exported {len(cases)} designs and {len(prompts)} prompts to {args.export}.")
        return

    summary = publish_bundled_assets(space, api_key)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
