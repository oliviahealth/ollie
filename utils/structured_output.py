import json
import os
import re


DEFAULT_PROMPT_SCHEMA_MODEL_TAGS = ("gpt-oss-20b", "gpt-oss-120b")


def _model_identifier(llm):
    for attr in ("model_name", "model", "model_id"):
        value = getattr(llm, attr, None)
        if value:
            return str(value)
    return ""


def _prompt_schema_model_tags():
    raw = os.getenv("STRUCTURED_OUTPUT_PROMPT_MODELS")
    if not raw:
        return DEFAULT_PROMPT_SCHEMA_MODEL_TAGS
    return tuple(tag.strip().lower() for tag in raw.split(",") if tag.strip())


def _should_use_prompt_schema_fallback(llm):
    if os.getenv("FORCE_PROMPT_SCHEMA_FALLBACK", "").lower() in {"1", "true", "yes"}:
        return True

    model_id = _model_identifier(llm).lower()
    if not model_id:
        return False

    return any(tag in model_id for tag in _prompt_schema_model_tags())


def _clone_messages(messages):
    return [dict(message) for message in messages]


def _prepend_schema_instructions(messages, schema):
    schema_str = json.dumps(schema, ensure_ascii=False, indent=2)
    instructions = (
        "The output will be in JSON following this schema:\n\n"
        f"{schema_str}\n\n"
        "After thinking, output only the JSON according to this schema."
    )
    cloned_messages = _clone_messages(messages)

    for index in range(len(cloned_messages) - 1, -1, -1):
        if cloned_messages[index].get("role") != "user":
            continue
        original = cloned_messages[index].get("content", "")
        cloned_messages[index]["content"] = f"{instructions}\n\n{original}"
        return cloned_messages

    return [{"role": "system", "content": instructions}] + cloned_messages


def _coerce_content_to_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                text = part.get("text")
                if text:
                    parts.append(str(text))
        return "".join(parts)
    return str(content or "")


def _strip_code_fences(text):
    fenced = re.compile(r"^```(?:json)?\s*([\s\S]*?)\s*```$", re.MULTILINE)
    match = fenced.search((text or "").strip())
    if match:
        return match.group(1).strip()
    return (text or "").strip()


def _try_json_loads(text):
    try:
        return json.loads(text)
    except Exception:
        fixed = re.sub(r",\s*([}\]])", r"\1", text)
        fixed = fixed.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
        if fixed.count('"') < 2 and "'" in fixed:
            fixed = re.sub(r"'", '"', fixed)
        try:
            return json.loads(fixed)
        except Exception:
            return None


def _parse_structured_response(schema_model, raw_text):
    clean_text = _strip_code_fences(raw_text)
    obj = _try_json_loads(clean_text)
    if obj is None:
        return None

    try:
        return schema_model.model_validate(obj)
    except Exception:
        return None


def _repair_structured_response(llm, schema_model, raw_text):
    repair_messages = [
        {
            "role": "user",
            "content": (
                "Repair the following JSON so that it is valid and fully conforms to this JSON Schema. "
                "Output only the repaired JSON and nothing else.\n\n"
                "Schema:\n"
                f"{json.dumps(schema_model.model_json_schema(), ensure_ascii=False, indent=2)}\n\n"
                "JSON to repair:\n"
                f"{raw_text}"
            ),
        }
    ]
    repaired = llm.invoke(repair_messages)
    return _coerce_content_to_text(getattr(repaired, "content", repaired))


def _invoke_with_prompt_schema_fallback(llm, schema_model, messages):
    prompt_messages = _prepend_schema_instructions(messages, schema_model.model_json_schema())
    response = llm.invoke(prompt_messages)
    raw_text = _coerce_content_to_text(getattr(response, "content", response))

    parsed = _parse_structured_response(schema_model, raw_text)
    if parsed is not None:
        return parsed

    repaired_text = _repair_structured_response(llm, schema_model, raw_text)
    parsed = _parse_structured_response(schema_model, repaired_text)
    if parsed is not None:
        return parsed

    raise ValueError("Model did not return valid structured JSON")


def invoke_structured_output(llm, schema_model, messages):
    if _should_use_prompt_schema_fallback(llm):
        return _invoke_with_prompt_schema_fallback(llm, schema_model, messages)

    try:
        structured_llm = llm.with_structured_output(
            schema_model,
            method="json_schema",
            strict=True,
        )
        return structured_llm.invoke(messages)
    except Exception:
        return _invoke_with_prompt_schema_fallback(llm, schema_model, messages)
