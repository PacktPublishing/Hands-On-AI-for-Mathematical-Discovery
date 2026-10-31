"""Small helpers shared by the command-line entry points."""
import shutil
from pathlib import Path


def default_lean():
    """Lean on PATH, otherwise the newest toolchain installed by elan."""
    on_path = shutil.which("lean")
    if on_path:
        return on_path
    toolchains = sorted(
        (Path.home() / ".elan" / "toolchains").glob("*/bin/lean")
    )
    return str(toolchains[-1]) if toolchains else "lean"
