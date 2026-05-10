"""
Test-suite configuration.

Set a dummy GROQ_API_KEY before src.agent is imported so a clean
checkout (no .env, no shell variable) can still run `pytest` without
hitting the import-time RuntimeError. Tests mock the Groq client, so
the value is never used to make a real API call.
"""

import os

os.environ.setdefault("GROQ_API_KEY", "test-key-not-used-for-real-calls")
