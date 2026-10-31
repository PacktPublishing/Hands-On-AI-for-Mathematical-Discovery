"""Use a local Ollama model to suggest a candidate for exact checking."""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from discovery_loop import run_demo


def parse_suggestion(content: str) -> tuple[int, str]:
    """Parse and validate the model's JSON candidate."""
    try:
        result = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError("Ollama response was not valid JSON") from error

    if not isinstance(result, dict):
        raise ValueError("Ollama response must be a JSON object")
    candidate = result.get("candidate_n")
    reason = result.get("reason", "")
    if isinstance(candidate, bool) or not isinstance(candidate, int):
        raise ValueError("Ollama response must contain integer candidate_n")
    if not isinstance(reason, str):
        raise ValueError("Ollama response field 'reason' must be text")
    return candidate, reason


def suggest_candidate(
    model: str,
    host: str = "http://localhost:11434",
    timeout: int = 120,
) -> tuple[int, str]:
    """Ask Ollama for a possible counterexample candidate."""
    prompt = (
        "We are testing the conjecture that n^2 + n + 5 is prime for every "
        "integer n >= 0. For n=0,1,2,3 the values are 5,7,11,17. "
        "Suggest one integer n from 4 through 100 whose value might be "
        "composite. Return only a JSON object with integer field "
        "'candidate_n' and short string field 'reason'. This is a search "
        "suggestion, not a proof."
    )
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": {
                "type": "object",
                "properties": {
                    "candidate_n": {"type": "integer"},
                    "reason": {"type": "string"},
                },
                "required": ["candidate_n", "reason"],
            },
            "options": {"temperature": 0},
        }
    ).encode("utf-8")
    request = Request(
        f"{host.rstrip('/')}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Ollama returned HTTP {error.code}: {detail}"
        ) from error
    except URLError as error:
        raise RuntimeError(
            f"Could not connect to Ollama at {host}: {error.reason}"
        ) from error

    try:
        content = payload["message"]["content"]
    except (KeyError, TypeError) as error:
        raise ValueError("Ollama response did not contain message content") from error
    if not isinstance(content, str):
        raise ValueError("Ollama message content must be text")
    return parse_suggestion(content)


def main() -> None:
    model = os.environ.get("OLLAMA_MODEL", "qwen3:0.6b")
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    suggested_candidate = suggest_candidate(model, host)
    print(f"MODEL: {model} at {host}")
    run_demo(suggested_candidate=suggested_candidate)


if __name__ == "__main__":
    main()
