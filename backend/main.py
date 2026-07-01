"""
QueryMind FastAPI backend.
Run: uvicorn main:app --reload --port 8030
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from chain import answer
from schema import SCHEMA_TEXT, run_sql

app = FastAPI(title="QueryMind")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


class QuestionRequest(BaseModel):
    question: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/schema")
def schema():
    return {"schema": SCHEMA_TEXT}


@app.post("/query")
def query(req: QuestionRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    result = answer(req.question)
    return result


@app.get("/examples")
def examples():
    return {
        "questions": [
            "Which country generated the most revenue?",
            "What were the top 5 best-selling products by total revenue?",
            "How many unique customers made purchases each month in 2011?",
            "What is the average order value by country?",
            "Which month had the highest total revenue?",
            "How many customers made more than 10 purchases?",
        ]
    }
