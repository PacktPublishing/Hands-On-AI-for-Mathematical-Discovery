"""An OpenAI-compatible chat client with tool support
(vLLM, Ollama, hosted APIs)."""

import json
import os
import time
import urllib.error
import urllib.request


class ModelError(RuntimeError):
    pass


def _post(url, body, headers, timeout, retries=3):
    data = json.dumps(body).encode()
    for attempt in range(retries + 1):
        req = urllib.request.Request(
            url, data=data, headers=headers
        )
        try:
            with urllib.request.urlopen(
                req, timeout=timeout
            ) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if (
                e.code in (429, 500, 502, 503)
                and attempt < retries
            ):
                time.sleep(2**attempt)
                continue
            raise ModelError(f"HTTP {e.code}: {e.read()[:300]!r}")
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < retries:
                time.sleep(2**attempt)
                continue
            raise ModelError(str(e))


class ChatClient:
    def __init__(
        self,
        name,
        base_url,
        model,
        api_key_env=None,
        params=None,
        per_sample_seed=False,
        timeout=600,
        note=None,
    ):
        self.name, self.model = name, model
        self.base_url = base_url.rstrip("/")
        self.key = (
            os.environ.get(api_key_env, "") if api_key_env else ""
        )
        self.params, self.timeout = params or {}, timeout
        self.per_sample_seed = per_sample_seed

    def chat(self, messages, tools=None, seed=None):
        """One chat completion: the message and its metadata."""
        body = {
            "model": self.model,
            "messages": messages,
            **self.params,
        }
        if tools:
            body["tools"], body["tool_choice"] = tools, "auto"
        if seed is not None:
            body["seed"] = seed
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"
        t0 = time.time()
        out = _post(
            self.base_url + "/chat/completions",
            body,
            headers,
            self.timeout,
        )
        choice = out["choices"][0]
        return {
            "message": choice["message"],
            "finish": choice.get("finish_reason") or "",
            "usage": out.get("usage") or {},
            "seconds": round(time.time() - t0, 2),
        }
