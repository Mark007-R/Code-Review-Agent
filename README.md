# Code-Review-Agent

Code-Review-Agent is a specialized AI code review assistant built in Python.
It reviews pasted code or full files, returns structured findings, and can be used from both:

- A CLI chat loop
- A FastAPI web UI

The project also includes a benchmark module and a pytest test suite.

## What it does

- Detects common bug patterns (off-by-one, mutable defaults, race windows)
- Flags security issues (injection patterns, hardcoded secrets)
- Highlights performance risks (N+1-like access patterns)
- Provides style and test-related review guidance
- Returns responses in a structured JSON-friendly format (when prompted)

## Tech stack

- Python 3.11+
- Groq SDK (`groq`)
- FastAPI + Uvicorn (web backend/UI serving)
- python-dotenv (environment loading)
- pytest + pytest-mock (tests)

## Project structure

```text
Code-Review-Agent/
  src/
    agent.py          # Core chat/review logic (Groq client + conversation history)
    benchmark.py      # Evaluation suite with weighted scoring (0-10,000)
  ui/
    server.py         # FastAPI app bridging browser UI to the agent
    static/
      index.html      # Frontend UI
  tests/
    test_agent.py     # Unit tests for agent + benchmark behavior
  example/
    bad_code.py       # Intentionally vulnerable code sample
  requirements.txt
  .env.example
```

## Setup

1. Create and activate a virtual environment.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies.

```powershell
pip install -r requirements.txt
```

3. Configure environment variables.

- Copy `.env.example` to `.env`
- Set your own Groq API key

```powershell
Copy-Item .env.example .env
```

Expected variable:

```text
GROQ_API_KEY=your_groq_api_key
```

## Run the CLI agent

```powershell
python src/agent.py
```

CLI commands:

- `exit` -> quit
- `reset` -> clear conversation history
- `file <path>` -> review a file from disk

Example:

```text
You: file example/bad_code.py
You: Review this function: def divide(a, b): return a / b
```

## Run the web UI

Start backend:

```powershell
uvicorn ui.server:app --reload --port 8000
```

Open:

- http://localhost:8000

Main API routes:

- `GET /` -> serves UI
- `POST /chat` -> sends free-form message to agent
- `POST /review-file` -> reviews a local file path
- `POST /reset` -> clears conversation history
- `GET /history` -> returns in-memory chat history
- `GET /health` -> health/model/provider info

## Run benchmark

```powershell
python src/benchmark.py
```

Benchmark summary:

- Uses 5 planted test cases:
  - SQL Injection
  - Hardcoded Secret
  - Off-by-one Loop
  - N+1 Query
  - Race Condition
- Scores across weighted dimensions:
  - accuracy (35%)
  - relevance (20%)
  - specificity (20%)
  - latency (10%)
  - format (10%)
  - false positives (5%)
- Produces a composite score on a 0-10,000 scale

## Run tests

```powershell
pytest -q
```

## Core modules

### `src/agent.py`

- Initializes Groq client using `GROQ_API_KEY`
- Uses model: `llama-3.3-70b-versatile`
- Maintains in-memory `conversation_history`
- Exposes:
  - `chat(user_message: str) -> str`
  - `review_file(file_path: str) -> str`
  - `score_from_response(response_text: str) -> int | None`
  - `reset_conversation() -> None`

### `src/benchmark.py`

- Defines benchmark test suite and evaluation dataclasses
- Computes per-dimension and composite scores
- Exposes `run_benchmark(agent_fn)` to evaluate any compatible agent callable

### `ui/server.py`

- Loads the same core agent functions
- Serves static frontend
- Provides API endpoints for chat/file review/reset/history/health

## Notes

- Conversation history is in-memory only and resets when process restarts.
- File review uses local filesystem paths passed to the backend.
- Keep secrets in `.env`; do not commit real API keys.

## Quick troubleshooting

- `KeyError: GROQ_API_KEY`
  - Add `GROQ_API_KEY` in `.env` and restart the process.

- `ModuleNotFoundError`
  - Reinstall dependencies with `pip install -r requirements.txt` in the active environment.

- UI cannot connect to backend
  - Ensure Uvicorn is running on port 8000.
  - Check that requests go to `http://localhost:8000`.

## License

[MIT](LICENSE) © 2026 Mark Rodrigues