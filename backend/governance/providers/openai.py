"""OpenAI API operations for embeddings and structured LLM responses."""

from openai import OpenAI

from ..api.tracing import trace_operation


def embed_texts(texts: list[str], *, timeout=60, max_retries=2) -> list[list[float]]:
    model = "text-embedding-3-small"
    with trace_operation("openai.embeddings.create", "EMBEDDING", {
        "embedding.model_name": model,
        "embedding.input_count": len(texts),
    }) as span, OpenAI(timeout=timeout, max_retries=max_retries) as client:
        response = client.embeddings.create(model=model, input=texts)
        span.set_attribute("embedding.token_count", response.usage.total_tokens)
    return [item.embedding for item in sorted(response.data, key=lambda item: item.index)]


def parse_response(model: str, instructions: str, input_json: str, schema):
    with trace_operation(
        "openai.responses.parse", "LLM", {"llm.model_name": model, "llm.provider": "openai"}
    ) as span, OpenAI(timeout=90, max_retries=0) as client:
        response = client.responses.parse(
            model=model,
            store=False,
            instructions=instructions,
            input=input_json,
            text_format=schema,
        )
        span.set_attribute("llm.model_name", response.model)
        if response.usage is not None:
            span.set_attributes({
                "llm.token_count.prompt": response.usage.input_tokens,
                "llm.token_count.completion": response.usage.output_tokens,
                "llm.token_count.total": response.usage.total_tokens,
            })
    return response.output_parsed
