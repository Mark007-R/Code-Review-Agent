"""
FastAPI backend — bridges the browser UI to QuestAgent.
Run: uvicorn ui.server:app --reload --port 8000
"""

import os
import sys
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from src.agent import chat, review_file, reset_conversation, conversation_history, AgentError

app = FastAPI(title="QuestAgent UI")

# Base directory the /review-file endpoint is allowed to read from.
# Defaults to the project root; override with QUESTAGENT_FILE_ROOT for deployments.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
FILE_ROOT = Path(os.environ.get("QUESTAGENT_FILE_ROOT", _PROJECT_ROOT)).resolve()


def _resolve_safe_path(user_path: str) -> Path:
    """Resolve user_path under FILE_ROOT, rejecting traversal outside it."""
    candidate = (FILE_ROOT / user_path).resolve() if not Path(user_path).is_absolute() else Path(user_path).resolve()
    try:
        candidate.relative_to(FILE_ROOT)
    except ValueError:
        raise HTTPException(
            status_code=403,
            detail=f"Path is outside the allowed root ({FILE_ROOT}).",
        )
    return candidate

# CORS_ALLOW_ORIGINS env var lets deployments override; default is local dev only.
_default_origins = "http://localhost:8000,http://127.0.0.1:8000"
_allowed_origins = [o.strip() for o in os.environ.get("CORS_ALLOW_ORIGINS", _default_origins).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


class ChatRequest(BaseModel):
    message: str


class FileRequest(BaseModel):
    path: str


@app.get("/")
def root():
    return FileResponse(os.path.join(static_dir, "index.html"))


@app.post("/chat")
def handle_chat(req: ChatRequest):
    try:
        response = chat(req.message)
    except AgentError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"response": response, "history_length": len(conversation_history)}


@app.post("/review-file")
def handle_file(req: FileRequest):
    safe_path = _resolve_safe_path(req.path)
    try:
        response = review_file(str(safe_path))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {req.path}")
    except AgentError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"response": response, "history_length": len(conversation_history)}


@app.post("/reset")
def handle_reset():
    reset_conversation()
    return {"status": "ok", "message": "Conversation reset."}


@app.get("/history")
def get_history():
    return {"history": conversation_history}


@app.get("/health")
def health():
    return {"status": "ok", "model": "llama-3.3-70b-versatile", "provider": "groq"}