"""One gateway for all tool calls: validate, run, check, log."""

import json
import signal
import time
from contextlib import contextmanager
from .validate import ToolError, parse_arguments, validate

WITHHELD = "internal check failed; result withheld"


@contextmanager
def time_limit(seconds):
    """Abort slow tools (main thread, Unix only)."""

    def handler(signum, frame):
        raise TimeoutError

    if not hasattr(signal, "SIGALRM"):  # Windows: no time limit
        yield
        return
    try:
        old = signal.signal(signal.SIGALRM, handler)
    except ValueError:  # not in the main thread
        yield
        return
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


class Registry:
    def __init__(self, tools, timeout=20):
        self.tools, self.timeout, self.log = tools, timeout, []

    def schemas(self):
        """Tool descriptions in OpenAI function-calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": t["description"],
                    "parameters": {
                        "type": "object",
                        "properties": {
                            p: s.schema()
                            for p, s in t["params"].items()
                        },
                        "required": list(t["params"]),
                        "additionalProperties": False,
                    },
                },
            }
            for name, t in self.tools.items()
        ]

    def call(self, name, raw_arguments):
        """Run one tool call. Always returns a JSON string."""
        t0 = time.time()
        entry = {"tool": name, "arguments": raw_arguments}
        try:
            tool = self.tools.get(name)
            if tool is None:
                raise ToolError(
                    f"unknown tool {name!r}; "
                    f"available: {sorted(self.tools)}"
                )
            args = parse_arguments(raw_arguments)
            args = validate(tool["params"], args)
            with time_limit(self.timeout):
                result = tool["run"](**args)
            check = tool.get("verify")
            if check and not check(args, result):
                raise ToolError(WITHHELD)
            entry.update(ok=True, result=result)
        except ToolError as e:
            entry.update(ok=False, error=str(e))
        except TimeoutError:
            error = f"timed out after {self.timeout} s"
            entry.update(ok=False, error=error)
        except Exception as e:  # a bug in a tool: log it, go on
            error = f"tool failed: {type(e).__name__}: {e}"
            entry.update(ok=False, error=error)
        entry["seconds"] = round(time.time() - t0, 3)
        self.log.append(entry)
        if entry["ok"]:
            return json.dumps(entry["result"])
        return json.dumps({"error": entry["error"]})
