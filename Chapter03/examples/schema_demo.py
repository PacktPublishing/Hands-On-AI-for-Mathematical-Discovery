"""What the model sees of one tool: name, purpose, schema."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mathtools.registry import Registry
from mathtools.tools import TOOLS

for schema in Registry(TOOLS).schemas():
    if schema["function"]["name"] == "word_cycle":
        print(json.dumps(schema, indent=2))
