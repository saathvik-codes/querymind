"""
End-to-end checks through the HTTP API with the built-in engine (no AI key needed):
uploads in the encodings and delimiters people actually export, and every suggested question answered without errors.

    pip install pytest && python -m pytest tests -q
"""
import json
import os
import sys
from pathlib import Path

os.environ["LLM"] = "local"
os.environ.pop("API_KEY", None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import pytest
from fastapi.testclient import TestClient

import main  # noqa: E402

client = TestClient(main.app)
ROWS = "Country,Product,Revenue,Order Date\nUnited Kingdom,Mug £5,120.50,2024-01-03\nFrance,Plate,80.00,2024-01-05\nGermany,Bowl,95.25,2024-02-11\n"


def upload(data: bytes, name: str = "sales.csv"):
    return client.post("/datasets/upload", files={"file": (name, data, "text/csv")})


def ask(question: str, dataset_id: str) -> list[dict]:
    r = client.post("/query/stream", json={"question": question, "dataset_id": dataset_id})
    assert r.status_code == 200, r.text
    return [json.loads(line[5:]) for line in r.text.split("\n\n") if line.startswith("data:")]


@pytest.mark.parametrize("label,data", [
    ("utf-8", ROWS.encode("utf-8")),
    ("utf-8 with BOM (Excel 'CSV UTF-8')", ROWS.encode("utf-8-sig")),
    ("cp1252 with a non-breaking space (Excel on Windows)", ROWS.replace("Mug £5", "Mug\xa0£5").encode("cp1252")),
    ("latin-1", ROWS.encode("latin-1")),
    ("semicolon separated (European Excel)", ROWS.replace(",", ";").replace("120.50", "120,50").encode("utf-8")),
])
def test_upload_reads_common_exports(label, data):
    r = upload(data)
    assert r.status_code == 200, f"{label}: {r.text}"
    ds = r.json()
    assert len(ds["columns"]) == 4, f"{label}: {ds['columns']}"
    assert not ds["columns"][0]["name"].startswith("﻿")


@pytest.mark.parametrize("data,expected", [
    (b"", "empty"),
    (b"a,b\n1,2\n3,4,5,6\n", "same number of columns"),
])
def test_bad_files_get_a_readable_message(data, expected):
    r = upload(data)
    assert r.status_code == 400
    assert expected in r.json()["detail"]
    assert "codec" not in r.json()["detail"]


def _assert_answers_cleanly(dataset_id: str, questions: list[str]):
    for q in questions:
        events = ask(q, dataset_id)
        kinds = [e["type"] for e in events]
        assert "error" not in kinds, f"{q!r}: {events}"
        assert kinds[-1] == "done", f"{q!r}: {kinds}"


def test_every_suggested_question_on_an_uploaded_dataset():
    ds = upload(ROWS.replace("Mug £5", "Mug\xa0£5").encode("cp1252")).json()
    assert ds["example_questions"]
    _assert_answers_cleanly(ds["dataset_id"], ds["example_questions"])


def test_every_suggested_question_on_the_built_in_dataset():
    ds = client.get("/datasets").json()["datasets"][0]
    _assert_answers_cleanly(ds["dataset_id"], ds["example_questions"])


@pytest.mark.parametrize("question", ["?", "tell me a joke", "drop table orders", "revenue; DROP TABLE orders", "x" * 1900])
def test_odd_questions_never_crash(question):
    events = ask(question, "default")
    assert events, "no response"
    assert events[-1]["type"] in ("done", "error")


def test_uploaded_dataset_survives_a_restart():
    """Render's free plan sleeps; an uploaded dataset must come back from its saved Parquet file."""
    import schema
    ds = upload(ROWS.encode("utf-8")).json()
    schema._datasets.pop(ds["dataset_id"], None)          # what a restart does to the in-memory registry
    _assert_answers_cleanly(ds["dataset_id"], ds["example_questions"][:3])
