"""
Tests for QuestAgent.
All Anthropic API calls are mocked — no real API keys needed.
"""

import json
import pytest
from unittest.mock import MagicMock, patch

# ── Fixtures ──────────────────────────────────────────────────────────────────

MOCK_REVIEW_JSON = {
    "summary": "Critical SQL injection vulnerability found.",
    "score": 30,
    "severity_breakdown": {"critical": 1, "high": 0, "medium": 0, "low": 1},
    "findings": [
        {
            "id": "FINDING-001",
            "severity": "critical",
            "category": "security",
            "line": 2,
            "title": "SQL Injection",
            "description": "String interpolation in SQL query enables SQL injection attacks.",
            "suggestion": "Use parameterised queries: `db.execute('SELECT * FROM users WHERE username = ?', [username])`",
        }
    ],
    "positive_notes": ["Function is short and easy to understand"],
    "refactor_priority": ["Fix SQL injection immediately"],
}

SQL_INJECTION_CODE = """
def get_user(username: str):
    query = f"SELECT * FROM users WHERE username = '{username}'"
    return db.execute(query)
"""


def _make_mock_response(text: str) -> MagicMock:
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    return msg


# ── Agent tests ───────────────────────────────────────────────────────────────

@patch("src.agent.client")
def test_chat_returns_string(mock_client):
    mock_client.messages.create.return_value = _make_mock_response("Hello!")
    from src.agent import chat, reset_conversation
    reset_conversation()
    result = chat("Hello")
    assert isinstance(result, str)
    assert result == "Hello!"


@patch("src.agent.client")
def test_chat_appends_history(mock_client):
    mock_client.messages.create.return_value = _make_mock_response("Got it.")
    from src.agent import chat, reset_conversation, conversation_history
    reset_conversation()
    chat("Review my code")
    assert len(conversation_history) == 2
    assert conversation_history[0]["role"] == "user"
    assert conversation_history[1]["role"] == "assistant"


@patch("src.agent.client")
def test_review_file_reads_and_submits(mock_client, tmp_path):
    mock_client.messages.create.return_value = _make_mock_response(
        json.dumps(MOCK_REVIEW_JSON)
    )
    from src.agent import review_file, reset_conversation
    reset_conversation()

    code_file = tmp_path / "bad_code.py"
    code_file.write_text(SQL_INJECTION_CODE)

    response = review_file(str(code_file))
    assert "sql injection" in response.lower() or "SQL" in response


def test_reset_conversation():
    from src.agent import chat, reset_conversation, conversation_history
    with patch("src.agent.client") as mock_client:
        mock_client.messages.create.return_value = _make_mock_response("Hi")
        reset_conversation()
        chat("test")
        assert len(conversation_history) > 0
        reset_conversation()
        assert len(conversation_history) == 0


def test_score_from_valid_json():
    from src.agent import score_from_response
    text = json.dumps({"score": 72, "summary": "Looks fine"})
    assert score_from_response(text) == 72


def test_score_from_malformed_json():
    from src.agent import score_from_response
    text = 'The code has issues. "score": 55 in my estimation.'
    assert score_from_response(text) == 55


def test_score_from_no_score():
    from src.agent import score_from_response
    assert score_from_response("No score here.") is None


# ── Benchmark tests ───────────────────────────────────────────────────────────

def test_score_accuracy_full_hit():
    from src.benchmark import score_accuracy
    response = "This code has sql injection via string interpolation. Use parameterised queries."
    score = score_accuracy(response, ["sql_injection", "no_parameterisation"])
    assert score == 1.0


def test_score_accuracy_miss():
    from src.benchmark import score_accuracy
    response = "The variable naming looks fine."
    score = score_accuracy(response, ["sql_injection", "no_parameterisation"])
    assert score == 0.0


def test_score_latency_fast():
    from src.benchmark import score_latency
    assert score_latency(1.0) == 1.0


def test_score_latency_slow():
    from src.benchmark import score_latency
    assert score_latency(30.0) == 0.0


def test_score_latency_mid():
    from src.benchmark import score_latency
    s = score_latency(16.0)
    assert 0.0 < s < 1.0


def test_score_format_valid_json():
    from src.benchmark import score_format
    text = json.dumps({
        "summary": "ok", "score": 80,
        "findings": [], "severity_breakdown": {}
    })
    assert score_format(text) == 1.0


def test_score_format_invalid_json():
    from src.benchmark import score_format
    text = "Here are some findings: summary, score mentioned."
    score = score_format(text)
    assert 0.0 <= score <= 1.0


def test_compute_composite_perfect():
    from src.benchmark import compute_composite, MAX_SCORE
    dims = {k: 1.0 for k in ["accuracy", "relevance", "specificity", "latency", "format", "false_pos"]}
    assert compute_composite(dims) == MAX_SCORE


def test_compute_composite_zero():
    from src.benchmark import compute_composite
    dims = {k: 0.0 for k in ["accuracy", "relevance", "specificity", "latency", "format", "false_pos"]}
    assert compute_composite(dims) == 0.0


def test_run_benchmark_structure():
    from src.benchmark import run_benchmark

    def dummy_agent(msg: str) -> str:
        return json.dumps({
            "summary": "ok",
            "score": 50,
            "severity_breakdown": {"critical": 0, "high": 0, "medium": 1, "low": 0},
            "findings": [
                {
                    "id": "F-001",
                    "severity": "medium",
                    "category": "security",
                    "line": 1,
                    "title": "SQL injection via string interpolation",
                    "description": "Parameterised queries prevent SQL injection.",
                    "suggestion": "Use `?` placeholders.",
                }
            ],
            "positive_notes": [],
            "refactor_priority": [],
        })

    report = run_benchmark(dummy_agent)
    assert "overall_score" in report
    assert "per_test" in report
    assert len(report["per_test"]) == 5
    assert 0 <= report["overall_score"] <= 10_000
