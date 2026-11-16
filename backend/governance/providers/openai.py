"""OpenAI API operations for rule embeddings and structured LLM responses."""

from openai import OpenAI


def embed_texts(texts: list[str]) -> list[list[float]]:
    with OpenAI(timeout=60) as client:
        response = client.embeddings.create(model="text-embedding-3-small", input=texts)
    return [item.embedding for item in sorted(response.data, key=lambda item: item.index)]


def parse_response(model: str, instructions: str, input_json: str, schema):
    with OpenAI(timeout=90, max_retries=0) as client:
        response = client.responses.parse(
            model=model,
            store=False,
            instructions=instructions,
            input=input_json,
            text_format=schema,
        )
    return response.output_parsed
