"""
FastAPI backend — bridges the browser UI to the CodeReview Agent.
Run: uvicorn ui.server:app --reload --port 8000
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from src.agent import chat, review_file, reset_conversation, conversation_history

app = FastAPI(title="CodeReview Agent UI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (the index.html UI)
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
    response = chat(req.message)
    return {"response": response, "history_length": len(conversation_history)}


@app.post("/review-file")
def handle_file(req: FileRequest):
    try:
        response = review_file(req.path)
        return {"response": response, "history_length": len(conversation_history)}
    except FileNotFoundError:
        return {"error": f"File not found: {req.path}"}


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