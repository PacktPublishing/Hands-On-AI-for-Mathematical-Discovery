"""Tool calls as a model might write them, and the answers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mathtools.registry import Registry
from mathtools.tools import TOOLS

calls = [
    ("word_cycle", '{"q": 3, "c": -1, "word": "110"}'),
    ("word_cycle", '{"q": 3, "c": -1, "word": 110}'),
    ("orbit", '{"q": 3, "c": 2, "x": 7, "max_steps": 100}'),
    ("cycle_census", '{"q": 3, "c": 13, "max_len": 40}'),
    ("orbit", '{"q": 3, "c": 1, "x": 27}'),
    ("exact_eval", '{"expression": "__import__(\'os\')"}'),
    ("exact_eval", '{"expression": "2**(2**20)"}'),
    ("collatz", "{}"),
]
registry = Registry(TOOLS)
for name, arguments in calls:
    print(
        f"{name} {arguments}\n  -> {registry.call(name, arguments)}"
    )
