"""Model clients: one interface for vLLM, Ollama, and hosted
APIs."""

import hashlib, json, os, time, urllib.error, urllib.request
from dataclasses import dataclass, field


@dataclass
class Completion:
    text: str
    model: str
    reasoning: str = ""
    finish: str = ""
    usage: dict = field(default_factory=dict)
    seconds: float = 0.0


class ModelError(RuntimeError):
    pass


def request_key(model_name, messages, seed):
    blob = json.dumps(
        [model_name, messages, seed], sort_keys=True
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


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


class OpenAICompatible:
    """vLLM, SGLang, Ollama (/v1), OpenAI, and compatibles."""

    def __init__(
        self,
        name,
        base_url,
        model,
        api_key_env=None,
        params=None,
        per_sample_seed=False,
        timeout=600,
    ):
        self.name, self.model = name, model
        self.base_url = base_url.rstrip("/")
        self.key = (
            os.environ.get(api_key_env, "") if api_key_env else ""
        )
        self.params, self.timeout = params or {}, timeout
        self.per_sample_seed = per_sample_seed

    def _headers(self):
        h = {"Content-Type": "application/json"}
        if self.key:
            h["Authorization"] = f"Bearer {self.key}"
        return h

    def complete(self, messages, seed=None):
        body = {
            "model": self.model,
            "messages": messages,
            **self.params,
        }
        if seed is not None:
            body["seed"] = seed
        t0 = time.time()
        out = _post(
            self.base_url + "/chat/completions",
            body,
            self._headers(),
            self.timeout,
        )
        choice = out["choices"][0]
        msg = choice["message"]
        return Completion(
            text=msg.get("content") or "",
            model=out.get("model", self.model),
            reasoning=(
                msg.get("reasoning_content")
                or msg.get("reasoning")
                or ""
            ),
            finish=choice.get("finish_reason") or "",
            usage=out.get("usage") or {},
            seconds=round(time.time() - t0, 2),
        )

    def describe(self):
        """What the endpoint says it serves, for the manifest."""
        try:
            req = urllib.request.Request(
                self.base_url + "/models", headers=self._headers()
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                listing = json.loads(r.read()).get("data", [])
            return next(
                (m for m in listing if m.get("id") == self.model),
                {"listed": [m.get("id") for m in listing][:20]},
            )
        except Exception as e:  # recorded, never fatal
            return {"error": str(e)[:200]}


class AnthropicMessages:
    """Anthropic Messages API. It has no seed parameter."""

    URL = "https://api.anthropic.com/v1/messages"

    def __init__(
        self,
        name,
        model,
        api_key_env="ANTHROPIC_API_KEY",
        params=None,
        per_sample_seed=False,
        timeout=600,
    ):
        self.name, self.model = name, model
        self.key = os.environ.get(api_key_env, "")
        self.params, self.timeout = params or {}, timeout
        self.per_sample_seed = False

    def complete(self, messages, seed=None):
        system = "\n".join(
            m["content"]
            for m in messages
            if m["role"] == "system"
        )
        body = {
            "model": self.model,
            "max_tokens": 8192,
            "messages": [
                m for m in messages if m["role"] != "system"
            ],
            **self.params,
        }
        if system:
            body["system"] = system
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.key,
            "anthropic-version": "2023-06-01",
        }
        t0 = time.time()
        out = _post(self.URL, body, headers, self.timeout)
        blocks = out.get("content", [])
        return Completion(
            text="".join(
                b.get("text", "")
                for b in blocks
                if b.get("type") == "text"
            ),
            model=out.get("model", self.model),
            reasoning="".join(
                b.get("thinking", "")
                for b in blocks
                if b.get("type") == "thinking"
            ),
            finish=out.get("stop_reason") or "",
            usage=out.get("usage") or {},
            seconds=round(time.time() - t0, 2),
        )

    def describe(self):
        return {}


def make_client(cfg):
    """Build a client from one entry of configs/models.json."""
    kw = {
        k: v
        for k, v in cfg.items()
        if k not in ("backend", "note")
    }
    backend = cfg.get("backend", "openai")
    if backend == "openai":
        return OpenAICompatible(**kw)
    if backend == "anthropic":
        return AnthropicMessages(**kw)
    raise ValueError(f"unknown backend {backend!r}")
