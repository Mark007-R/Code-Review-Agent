"""
Performance evaluation module for QuestAgent.

Scoring scale: 0 – 10,000 composite points.
Each dimension is scored 0–100, then weighted and scaled.
"""

import re
import time
import json
import statistics
from dataclasses import dataclass, field
from typing import Callable


# ── Scoring constants ─────────────────────────────────────────────────────────

WEIGHTS = {
    "accuracy":    0.35,   # Did it catch the planted bugs / vulns?
    "relevance":   0.20,   # Are findings actually about the code submitted?
    "specificity": 0.20,   # Does it cite line numbers & concrete fixes?
    "latency":     0.10,   # Inverse of response time (penalises slowness)
    "format":      0.10,   # Is the JSON schema valid and complete?
    "false_pos":   0.05,   # Penalty for hallucinated findings
}

MAX_SCORE = 10_000


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class TestCase:
    name: str
    code_snippet: str
    planted_issues: list[str]            # Known bugs/vulns we expect to be caught
    language: str = "python"


@dataclass
class EvalResult:
    test_case: TestCase
    raw_response: str
    latency_seconds: float
    dimension_scores: dict[str, float] = field(default_factory=dict)
    composite_score: float = 0.0


# ── Planted test suite ────────────────────────────────────────────────────────

TEST_SUITE: list[TestCase] = [
    TestCase(
        name="SQL Injection",
        language="python",
        planted_issues=["sql_injection", "no_parameterisation"],
        code_snippet="""
def get_user(username: str):
    query = f"SELECT * FROM users WHERE username = '{username}'"
    return db.execute(query)
""",
    ),
    TestCase(
        name="Hardcoded Secret",
        language="python",
        planted_issues=["hardcoded_api_key", "secret_in_source"],
        code_snippet="""
API_KEY = "sk-prod-abc123supersecretkey"

def call_service(payload):
    headers = {"Authorization": f"Bearer {API_KEY}"}
    return requests.post("https://api.example.com/v1/data", json=payload, headers=headers)
""",
    ),
    TestCase(
        name="Off-by-one Loop",
        language="python",
        planted_issues=["off_by_one", "index_out_of_range"],
        code_snippet="""
def sum_pairs(nums: list[int]) -> int:
    total = 0
    for i in range(len(nums)):      # should be range(len(nums) - 1)
        total += nums[i] + nums[i + 1]
    return total
""",
    ),
    TestCase(
        name="N+1 Query",
        language="python",
        planted_issues=["n_plus_1_query", "missing_prefetch"],
        code_snippet="""
def get_authors_with_books():
    authors = Author.objects.all()
    result = []
    for author in authors:
        books = Book.objects.filter(author=author)   # N+1
        result.append({"author": author.name, "books": list(books)})
    return result
""",
    ),
    TestCase(
        name="Race Condition",
        language="python",
        planted_issues=["race_condition", "non_atomic_check_then_act"],
        code_snippet="""
def withdraw(account_id: int, amount: float):
    balance = get_balance(account_id)      # read
    if balance >= amount:                  # check
        set_balance(account_id, balance - amount)   # act — race window here
        return True
    return False
""",
    ),
]


# ── Scoring functions ─────────────────────────────────────────────────────────

def score_accuracy(response: str, planted: list[str]) -> float:
    """Fraction of planted issues mentioned (keyword matching as proxy)."""
    lower = response.lower()
    keyword_map = {
        "sql_injection":            ["sql injection", "injection", "parameteris", "parameteriz"],
        "no_parameterisation":      ["parameteris", "parameteriz", "prepared statement", "bind"],
        "hardcoded_api_key":        ["hardcoded", "hard-coded", "api key", "secret"],
        "secret_in_source":         ["secret", "credential", "env var", "environment variable"],
        "off_by_one":               ["off-by-one", "off by one", "index error", "index out"],
        "index_out_of_range":       ["index out", "indexerror", "out of range", "bounds"],
        "n_plus_1_query":           ["n+1", "n plus 1", "select_related", "prefetch"],
        "missing_prefetch":         ["prefetch", "select_related", "eager load"],
        "race_condition":           ["race condition", "atomic", "concurren", "thread-safe"],
        "non_atomic_check_then_act":["atomic", "check-then-act", "toctou", "transaction"],
    }
    hits = sum(
        1 for issue in planted
        if any(kw in lower for kw in keyword_map.get(issue, [issue.replace("_", " ")]))
    )
    return hits / max(len(planted), 1)


def score_relevance(response: str, code: str) -> float:
    """Penalty if response discusses unrelated topics at length."""
    # Simple proxy: response must be < 5× the code length and focused
    if len(response) > len(code) * 10:
        return 0.5
    return 1.0


def score_specificity(response: str) -> float:
    """Rewards concrete findings: line numbers, code snippets, suggested fixes."""
    indicators = ["line", "```", "suggestion", "fix", "instead", "replace", "should be"]
    hits = sum(1 for ind in indicators if ind in response.lower())
    return min(hits / len(indicators), 1.0)


def score_latency(latency_seconds: float) -> float:
    """Score of 1.0 at ≤2 s, degrades linearly to 0.0 at 30 s."""
    if latency_seconds <= 2:
        return 1.0
    if latency_seconds >= 30:
        return 0.0
    return 1.0 - (latency_seconds - 2) / 28


def score_format(response: str) -> float:
    """Try to parse JSON; check required keys."""
    required_keys = {"summary", "score", "findings", "severity_breakdown"}
    try:
        data = json.loads(response)
        present = required_keys.intersection(data.keys())
        return len(present) / len(required_keys)
    except (json.JSONDecodeError, TypeError):
        # Partial credit if keys appear in text
        text_hits = sum(1 for k in required_keys if k in response.lower())
        return (text_hits / len(required_keys)) * 0.5


def score_false_positives(response: str, code: str) -> float:
    """Penalty for findings about symbols not in the code."""
    try:
        data = json.loads(response)
        findings = data.get("findings", [])
    except (json.JSONDecodeError, TypeError):
        return 1.0   # can't parse, skip penalty

    code_tokens = set(re.findall(r'\w+', code))
    penalty = 0
    for f in findings:
        desc = f.get("description", "") + f.get("title", "")
        # If the finding mentions symbols we can verify aren't in the code, penalise
        mentioned = set(re.findall(r'`(\w+)`', desc))
        hallucinated = mentioned - code_tokens
        if len(hallucinated) > 2:
            penalty += 1

    return max(0.0, 1.0 - penalty * 0.1)


# ── Composite scoring ─────────────────────────────────────────────────────────

def compute_composite(dim: dict[str, float]) -> float:
    """Weighted average of dimensions, scaled to MAX_SCORE."""
    raw = sum(dim[k] * WEIGHTS[k] for k in WEIGHTS)
    return round(raw * MAX_SCORE, 2)


# ── Benchmark runner ──────────────────────────────────────────────────────────

def run_benchmark(agent_fn: Callable[[str], str]) -> dict:
    """
    Run the full test suite against an agent function.

    agent_fn: callable that accepts a user message string and returns a response string.
    Returns a summary dict with per-test results and overall score.
    """
    results: list[EvalResult] = []

    for tc in TEST_SUITE:
        prompt = (
            f"Review the following {tc.language} code and return JSON per the schema:\n\n"
            f"```{tc.language}\n{tc.code_snippet}\n```"
        )
        t0 = time.perf_counter()
        response = agent_fn(prompt)
        latency = time.perf_counter() - t0

        dims = {
            "accuracy":   score_accuracy(response, tc.planted_issues),
            "relevance":  score_relevance(response, tc.code_snippet),
            "specificity": score_specificity(response),
            "latency":    score_latency(latency),
            "format":     score_format(response),
            "false_pos":  score_false_positives(response, tc.code_snippet),
        }
        composite = compute_composite(dims)

        results.append(EvalResult(
            test_case=tc,
            raw_response=response,
            latency_seconds=latency,
            dimension_scores=dims,
            composite_score=composite,
        ))

    # Aggregate
    all_scores = [r.composite_score for r in results]
    summary = {
        "total_tests": len(results),
        "mean_score":  round(statistics.mean(all_scores), 2),
        "median_score": round(statistics.median(all_scores), 2),
        "min_score":   round(min(all_scores), 2),
        "max_score":   round(max(all_scores), 2),
        "overall_score": round(statistics.mean(all_scores), 2),
        "per_test": [
            {
                "name": r.test_case.name,
                "composite": r.composite_score,
                "dimensions": {k: round(v * 100, 1) for k, v in r.dimension_scores.items()},
                "latency_s": round(r.latency_seconds, 2),
            }
            for r in results
        ],
    }
    return summary


if __name__ == "__main__":
    # Quick self-test with a mock agent
    def mock_agent(msg: str) -> str:
        return json.dumps({
            "summary": "Found issues",
            "score": 45,
            "severity_breakdown": {"critical": 1, "high": 0, "medium": 1, "low": 0},
            "findings": [
                {
                    "id": "FINDING-001",
                    "severity": "critical",
                    "category": "security",
                    "line": 2,
                    "title": "SQL Injection vulnerability",
                    "description": "Using string interpolation for SQL is vulnerable to SQL injection.",
                    "suggestion": "Use parameterised queries: `db.execute('SELECT * FROM users WHERE username = ?', [username])`"
                }
            ],
            "positive_notes": [],
            "refactor_priority": ["Fix SQL injection first"],
        })

    report = run_benchmark(mock_agent)
    print(json.dumps(report, indent=2))
