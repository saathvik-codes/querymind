"""
QueryMind FastAPI backend.
Run: uvicorn main:app --reload --port 8030
"""
import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import json

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from chain import answer, answer_stream, generate_example_questions, json_default
from cleanup import periodic_cleanup_task, sweep_expired_uploads
from schema import get_dataset, list_datasets, register_csv_dataset
from security import enforce_rate_limit, require_api_key

MAX_QUESTION_LENGTH = 2000

_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    sweep_expired_uploads()
    cleanup_task = asyncio.create_task(periodic_cleanup_task())
    try:
        yield
    finally:
        cleanup_task.cancel()


app = FastAPI(title="QueryMind", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
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
def schema(dataset_id: str = "default", api_key: str = Depends(require_api_key)):
    try:
        ds = get_dataset(dataset_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown dataset")
    return {"schema": ds.schema_text}


@app.get("/datasets")
def datasets(api_key: str = Depends(require_api_key)):
    # Only ever surface the built-in default dataset here — listing every
    # persisted upload would let any caller enumerate other users'
    # dataset_ids (which are otherwise unguessable random tokens) just by
    # hitting this endpoint. A specific dataset is still reachable by anyone
    # who already knows/holds its id, via /schema, /query, /examples.
    return {"datasets": [_dataset_summary(ds) for ds in list_datasets() if ds.id == "default"]}


@app.post("/datasets/upload")
async def upload_dataset(file: UploadFile = File(...), api_key: str = Depends(require_api_key)):
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


def _validate_question(question: str) -> None:
    if not question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    if len(question) > MAX_QUESTION_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Question is too long — max {MAX_QUESTION_LENGTH} characters.",
        )


@app.post("/query")
def query(req: QuestionRequest, request: Request, api_key: str = Depends(require_api_key)):
    enforce_rate_limit(request, api_key)
    _validate_question(req.question)
    try:
        get_dataset(req.dataset_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown dataset")
    result = answer(req.question, req.dataset_id)
    return result


@app.post("/query/stream")
def query_stream(req: QuestionRequest, request: Request, api_key: str = Depends(require_api_key)):
    enforce_rate_limit(request, api_key)
    _validate_question(req.question)
    try:
        get_dataset(req.dataset_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown dataset")

    def event_source():
        for event in answer_stream(req.question, req.dataset_id):
            yield f"data: {json.dumps(event, default=json_default)}\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")


@app.get("/examples")
def examples(dataset_id: str = "default", api_key: str = Depends(require_api_key)):
    try:
        ds = get_dataset(dataset_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown dataset")
    return {"questions": generate_example_questions(ds)}
