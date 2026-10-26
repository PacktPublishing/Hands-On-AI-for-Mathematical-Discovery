"""Tool gateway: every tool call goes through one registry that logs it."""

import shutil, subprocess, tempfile, os


class ToolGateway:
    def __init__(self, ledger):
        self.ledger, self.tools = ledger, {}

    def register(self, name, fn, description):
        self.tools[name] = (fn, description)

    def call(self, name, caller, claim_id=None, **kwargs):
        fn, _ = self.tools[name]
        result = fn(**kwargs)
        self.ledger.record(
            caller,
            f"tool:{name}",
            claim_id,
            args=kwargs,
            result=result,
        )
        return result


def lean_check(source, lean_cmd="lean", timeout=300):
    """Compile a Lean file and report what it really established."""
    exe = shutil.which(lean_cmd) or (
        lean_cmd if os.path.exists(lean_cmd) else None
    )
    if exe is None:
        return {"status": "unavailable"}
    with tempfile.NamedTemporaryFile(
        "w", suffix=".lean", delete=False
    ) as f:
        f.write(source)
        path = f.name
    try:
        out = subprocess.run(
            [exe, path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    finally:
        os.unlink(path)
    log = out.stdout + out.stderr
    uses_sorry = "sorry" in log
    bad_axioms = "sorryAx" in log
    ok = out.returncode == 0 and not uses_sorry and not bad_axioms
    return {
        "status": "checked" if ok else "failed",
        "log": log.strip()[:2000],
    }
