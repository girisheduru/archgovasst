from os import getenv


def configure_arize():
    space_id = getenv("ARIZE_SPACE_ID", "").strip()
    api_key = getenv("ARIZE_API_KEY", "").strip()
    if not space_id and not api_key:
        return None
    if not space_id or not api_key:
        raise RuntimeError("Arize AX requires both ARIZE_SPACE_ID and ARIZE_API_KEY.")

    from arize.otel import register

    return register(
        space_id=space_id,
        api_key=api_key,
        project_name=getenv("ARIZE_PROJECT_NAME", "").strip() or "archgovasst",
        set_global_tracer_provider=False,
        verbose=False,
    )
