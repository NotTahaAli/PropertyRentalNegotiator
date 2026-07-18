import io
import zipfile
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import parse
from app.auth import get_current_user_id
from app.main import app

client = TestClient(app)

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _as(user_id):
    app.dependency_overrides[get_current_user_id] = lambda: user_id


def teardown_function():
    app.dependency_overrides.clear()


def _make_docx(text: str) -> bytes:
    document = (
        '<?xml version="1.0"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", document)
    return buf.getvalue()


class _FakeResponses:
    def __init__(self, output_parsed=None, error=None):
        self.output_parsed = output_parsed
        self.error = error
        self.captured = {}

    def parse(self, **kwargs):
        self.captured.update(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(output_parsed=self.output_parsed)


def _fake_client(monkeypatch, output_parsed=None, error=None):
    fake = _FakeResponses(output_parsed=output_parsed, error=error)
    monkeypatch.setattr(parse, "_client", lambda: SimpleNamespace(responses=fake))
    return fake


def _parsed(**fields):
    model = parse.build_parse_model()
    return model(raw_text_preview="This Rent Agreement is made...", **fields)


def _post(content=b"%PDF-1.4 fake", mime="application/pdf", kind="rent_agreement", name="doc.pdf"):
    return client.post(
        "/parse",
        files={"file": (name, content, mime)},
        data={"kind": kind},
    )


# --- extract_docx_text ---


def test_extract_docx_text():
    data = _make_docx("Rent is 85000 per month")
    assert parse.extract_docx_text(data) == "Rent is 85000 per month"


def test_extract_docx_text_invalid_zip():
    with pytest.raises(ValueError):
        parse.extract_docx_text(b"not a zip")


# --- build_parse_model ---


def test_parse_model_all_fields_optional():
    model = parse.build_parse_model()
    instance = model(raw_text_preview="x")
    assert instance.raw_text_preview == "x"


def test_parse_model_enforces_enum():
    model = parse.build_parse_model()
    with pytest.raises(Exception):
        model(raw_text_preview="x", floor="rooftop")


# --- endpoint validation ---


def test_parse_requires_auth():
    assert _post().status_code == 401


def test_parse_rejects_bad_kind():
    _as("u1")
    assert _post(kind="poem").status_code == 422


def test_parse_rejects_bad_mime():
    _as("u1")
    assert _post(mime="text/plain", name="doc.txt").status_code == 415


def test_parse_rejects_oversized():
    _as("u1")
    big = b"x" * (parse.MAX_BYTES + 1)
    assert _post(content=big).status_code == 413


def test_parse_rejects_corrupt_docx():
    _as("u1")
    assert _post(content=b"junk", mime=DOCX_MIME, name="doc.docx").status_code == 415


# --- happy paths ---


def test_parse_pdf_uses_input_file(monkeypatch):
    _as("u1")
    fake = _fake_client(monkeypatch, output_parsed=_parsed(area_sqft=400))
    response = _post()
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "rent_agreement"
    assert body["partial_spec"] == {"area_sqft": 400}
    assert "raw_text_preview" in body
    content_parts = fake.captured["input"][-1]["content"]
    assert any(p.get("type") == "input_file" for p in content_parts)


def test_parse_image_uses_input_image(monkeypatch):
    _as("u1")
    fake = _fake_client(monkeypatch, output_parsed=_parsed(location="Gulberg III, Lahore"))
    response = _post(content=b"\x89PNG fake", mime="image/png", name="doc.png", kind="requirements")
    assert response.status_code == 200
    assert response.json()["partial_spec"] == {"location": "Gulberg III, Lahore"}
    content_parts = fake.captured["input"][-1]["content"]
    assert any(p.get("type") == "input_image" for p in content_parts)


def test_parse_docx_uses_extracted_text(monkeypatch):
    _as("u1")
    fake = _fake_client(monkeypatch, output_parsed=_parsed(lease_years=3))
    response = _post(content=_make_docx("lease of 3 years"), mime=DOCX_MIME, name="doc.docx")
    assert response.status_code == 200
    assert response.json()["partial_spec"] == {"lease_years": 3}
    content_parts = fake.captured["input"][-1]["content"]
    texts = [p for p in content_parts if p.get("type") == "input_text"]
    assert any("lease of 3 years" in p["text"] for p in texts)


def test_parse_drops_none_fields(monkeypatch):
    _as("u1")
    _fake_client(monkeypatch, output_parsed=_parsed(area_sqft=400, parking=None))
    body = _post().json()
    assert body["partial_spec"] == {"area_sqft": 400}


def test_parse_upstream_failure_returns_502(monkeypatch):
    _as("u1")
    _fake_client(monkeypatch, error=RuntimeError("boom"))
    assert _post().status_code == 502
