"""
Tests for the FastAPI HTTP layer in ui/server.py.

Covers status-code contracts: happy path, 404 for missing files,
403 for path traversal, 502 for upstream Groq failures, 422 for
empty/oversized payloads.
"""

import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def _mock_groq_response(text: str) -> MagicMock:
    response = MagicMock()
    choice = MagicMock()
    choice.message.content = text
    response.choices = [choice]
    return response


def _client() -> TestClient:
    from ui.server import app
    from src.agent import reset_conversation
    reset_conversation()
    return TestClient(app)


@patch("src.agent.client")
def test_chat_happy_path(mock_client):
    mock_client.chat.completions.create.return_value = _mock_groq_response("hi back")
    res = _client().post("/chat", json={"message": "hi"})
    assert res.status_code == 200
    assert res.json()["response"] == "hi back"


def test_chat_rejects_empty_message():
    res = _client().post("/chat", json={"message": ""})
    assert res.status_code == 422


@patch("src.agent.client")
def test_chat_returns_502_on_agent_error(mock_client):
    mock_client.chat.completions.create.side_effect = RuntimeError("boom")
    res = _client().post("/chat", json={"message": "hi"})
    assert res.status_code == 502
    assert "Groq API call failed" in res.json()["detail"]


def test_review_file_returns_404_for_missing_file():
    res = _client().post("/review-file", json={"path": "does_not_exist_xyz.py"})
    assert res.status_code == 404
    assert "File not found" in res.json()["detail"]


def test_review_file_blocks_path_traversal():
    res = _client().post("/review-file", json={"path": "../../../../etc/passwd"})
    assert res.status_code == 403
    assert "outside the allowed root" in res.json()["detail"]


def test_review_file_rejects_empty_path():
    res = _client().post("/review-file", json={"path": ""})
    assert res.status_code == 422


def test_reset_endpoint():
    res = _client().post("/reset")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_health_endpoint():
    res = _client().get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["provider"] == "groq"
