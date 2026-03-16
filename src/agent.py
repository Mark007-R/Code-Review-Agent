"""
QuestAgent — Specialized AI agent for automated, opinionated code analysis.
Detects bugs, security vulnerabilities, performance anti-patterns, and style drift.
Powered by Groq (free tier at console.groq.com).
"""

import os
import json
import re
from typing import Any
from groq import Groq
from dotenv import load_dotenv
load_dotenv()  # loads .env before reading os.environ

# ── Client ────────────────────────────────────────────────────────────────────
client = Groq(api_key=os.environ["GROQ_API_KEY"])
MODEL = "llama-3.3-70b-versatile"   # fast + free on Groq

# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are QuestAgent — an expert AI software quality reviewer with deep knowledge of
software engineering best practices, security vulnerabilities, and performance optimization.

Your specialization:
1. BUG DETECTION   — logic errors, off-by-ones, null dereferences, race conditions
2. SECURITY AUDIT  — injection, auth bypass, secret leakage, dependency CVEs
3. PERFORMANCE     — O(n^2) loops, N+1 queries, memory leaks, unnecessary re-renders
4. STYLE/DESIGN    — naming conventions, SOLID violations, code duplication
5. TEST COVERAGE   — untested edge cases, missing assertions, brittle fixtures

Output format (always JSON-parseable when asked):
{
  "summary": "One-line verdict",
  "score": <0-100 quality score>,
  "severity_breakdown": { "critical": n, "high": n, "medium": n, "low": n },
  "findings": [
    {
      "id": "FINDING-001",
      "severity": "critical|high|medium|low",
      "category": "bug|security|performance|style|test",
      "line": <line number or null>,
      "title": "Short title",
      "description": "What is wrong and why it matters",
      "suggestion": "Concrete fix with code snippet if helpful"
    }
  ],
  "positive_notes": ["Things done well"],
  "refactor_priority": ["Top 3 things to fix first"]
}

Be direct, specific, and constructive. Never be vague. Cite line numbers when possible.
When no code is provided, ask the user to paste code or describe what they want reviewed."""

# ── Conversation memory ───────────────────────────────────────────────────────
conversation_history: list[dict[str, Any]] = []

# ── Core agent loop ───────────────────────────────────────────────────────────

def chat(user_message: str) -> str:
    """Send a message and get a response, maintaining conversation history."""
    conversation_history.append({"role": "user", "content": user_message})

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=8096,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history,
    )

    assistant_message = response.choices[0].message.content
    conversation_history.append({"role": "assistant", "content": assistant_message})
    return assistant_message


def review_file(file_path: str) -> str:
    """Load a file from disk and submit it for review."""
    with open(file_path, "r", encoding="utf-8") as fh:
        code = fh.read()
    language = _detect_language(file_path)
    prompt = (
        f"Please review the following {language} file (`{file_path}`).\n"
        f"Return your response as valid JSON matching the schema in your system prompt.\n\n"
        f"```{language}\n{code}\n```"
    )
    return chat(prompt)


def score_from_response(response_text: str) -> int | None:
    """Extract the numeric quality score from an agent response, if present."""
    try:
        data = json.loads(response_text)
        return data.get("score")
    except json.JSONDecodeError:
        pass
    match = re.search(r'"score"\s*:\s*(\d+)', response_text)
    return int(match.group(1)) if match else None


def reset_conversation() -> None:
    """Clear the conversation history to start a fresh review session."""
    conversation_history.clear()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _detect_language(path: str) -> str:
    ext_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".jsx": "jsx", ".tsx": "tsx", ".go": "go", ".rs": "rust",
        ".java": "java", ".kt": "kotlin", ".rb": "ruby", ".php": "php",
        ".cs": "csharp", ".cpp": "cpp", ".c": "c", ".swift": "swift",
        ".sh": "bash", ".sql": "sql", ".yaml": "yaml", ".yml": "yaml",
        ".json": "json", ".tf": "hcl",
    }
    ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return ext_map.get(ext, "text")


# ── CLI entry point ───────────────────────────────────────────────────────────

def main() -> None:
    print("╔══════════════════════════════════════════╗")
    print("║         QuestAgent  v1.0.0               ║")
    print("║  Paste code · Drop a file path · Chat    ║")
    print("╚══════════════════════════════════════════╝")
    print('Type "exit" to quit | "reset" to clear history | "file <path>" to review a file\n')

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() == "exit":
            print("Goodbye!")
            break
        if user_input.lower() == "reset":
            reset_conversation()
            print("Agent: Conversation reset. Ready for a fresh review.\n")
            continue
        if user_input.lower().startswith("file "):
            path = user_input[5:].strip()
            try:
                response = review_file(path)
            except FileNotFoundError:
                print(f"Agent: File not found: {path}\n")
                continue
        else:
            response = chat(user_input)

        print(f"\nAgent: {response}\n")


if __name__ == "__main__":
    main()