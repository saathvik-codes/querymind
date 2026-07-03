"""
QueryMind FastAPI backend.
Run: uvicorn main:app --reload --port 8030
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import json

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from chain import answer, answer_stream, generate_example_questions, json_default
from schema import get_dataset, list_datasets, register_csv_dataset

app = FastAPI(title="QueryMind")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


class QuestionRequest(BaseModel):
    question: str
    dataset_id: str = "default"


def _dataset_summary(ds) -> dict:
    return {
        "dataset_id": ds.id,
        "name": ds.name,
        "row_count": ds.row_count,
        "columns": [{"name": c.name, "kind": c.kind} for c in ds.columns],
        "example_questions": generate_example_questions(ds),
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/schema")
def schema(dataset_id: str = "default"):
    try:
        ds = get_dataset(dataset_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown dataset")
    return {"schema": ds.schema_text}


@app.get("/datasets")
def datasets():
    return {"datasets": [_dataset_summary(ds) for ds in list_datasets()]}


@app.post("/datasets/upload")
async def upload_dataset(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported.")
    file_bytes = await file.read()
    try:
        ds = register_csv_dataset(file.filename, file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=400, detail="Could not parse that file as CSV.")
    return _dataset_summary(ds)


@app.post("/query")
def query(req: QuestionRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    try:
        get_dataset(req.dataset_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown dataset")
    result = answer(req.question, req.dataset_id)
    return result


@app.post("/query/stream")
def query_stream(req: QuestionRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    try:
        get_dataset(req.dataset_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown dataset")

    def event_source():
        for event in answer_stream(req.question, req.dataset_id):
            yield f"data: {json.dumps(event, default=json_default)}\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")


@app.get("/examples")
def examples(dataset_id: str = "default"):
    try:
        ds = get_dataset(dataset_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown dataset")
    return {"questions": generate_example_questions(ds)}
