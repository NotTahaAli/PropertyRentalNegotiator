import base64
import io
import os
import zipfile
import xml.etree.ElementTree as ET
from functools import lru_cache
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, create_model

from .auth import get_current_user_id
from .vertical import _TYPE_MAP, load_vertical

OPENAI_MODEL = "gpt-5.4-mini"
MAX_BYTES = 10 * 1024 * 1024
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
ALLOWED_MIMES = {"application/pdf", "image/png", "image/jpeg", DOCX_MIME}
KINDS = {"rent_agreement", "requirements"}

_WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

parse_router = APIRouter()


@lru_cache
def _client() -> OpenAI:
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def extract_docx_text(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            document = zf.read("word/document.xml")
        root = ET.fromstring(document)
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        raise ValueError("invalid docx") from exc
    return " ".join(el.text for el in root.iter(f"{_WORD_NS}t") if el.text)


@lru_cache
def build_parse_model() -> type[BaseModel]:
    config = load_vertical()
    fields = {"raw_text_preview": (str, ...)}
    for name, field in config.spec_schema.items():
        if field.type == "enum":
            from typing import Literal

            py_type = Literal[tuple(field.values)]
        else:
            py_type = _TYPE_MAP[field.type]
        fields[name] = (Optional[py_type], None)
    return create_model("ParsedSpec", __config__=ConfigDict(extra="forbid"), **fields)


def _system_prompt(kind: str) -> str:
    config = load_vertical()
    field_lines = "\n".join(
        f"- {name}: {field.prompt or field.type}" for name, field in config.spec_schema.items()
    )
    doc_desc = (
        "an existing rent agreement" if kind == "rent_agreement" else "a requirements document"
    )
    return (
        f"You are extracting a commercial shop rental job spec from {doc_desc}. "
        "Extract ONLY values the document explicitly states. Never infer, estimate, or guess. "
        "Leave any field the document does not clearly state as null. "
        "Dates must be ISO format (YYYY-MM-DD). "
        "Set raw_text_preview to the first ~200 characters of the document's text.\n"
        f"Fields:\n{field_lines}"
    )


@parse_router.post("/parse")
def parse_doc(
    file: UploadFile,
    kind: str = Form(...),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    if kind not in KINDS:
        raise HTTPException(status_code=422, detail="kind must be rent_agreement or requirements")
    if file.content_type not in ALLOWED_MIMES:
        raise HTTPException(status_code=415, detail="unsupported file type")
    data = file.file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="file too large (max 10 MB)")

    if file.content_type == DOCX_MIME:
        try:
            text = extract_docx_text(data)
        except ValueError:
            raise HTTPException(status_code=415, detail="invalid docx file")
        content = [{"type": "input_text", "text": text}]
    elif file.content_type == "application/pdf":
        b64 = base64.b64encode(data).decode()
        content = [
            {
                "type": "input_file",
                "filename": file.filename or "document.pdf",
                "file_data": f"data:application/pdf;base64,{b64}",
            }
        ]
    else:
        b64 = base64.b64encode(data).decode()
        content = [
            {
                "type": "input_image",
                "image_url": f"data:{file.content_type};base64,{b64}",
            }
        ]

    try:
        result = _client().responses.parse(
            model=OPENAI_MODEL,
            input=[
                {"role": "system", "content": _system_prompt(kind)},
                {"role": "user", "content": content},
            ],
            text_format=build_parse_model(),
        )
    except Exception:
        raise HTTPException(status_code=502, detail="parse upstream failed")

    parsed = result.output_parsed
    dump = parsed.model_dump()
    preview = dump.pop("raw_text_preview")
    partial_spec = {k: v for k, v in dump.items() if v is not None}
    return {"kind": kind, "partial_spec": partial_spec, "raw_text_preview": preview}
