"""Check tool arguments before any computation runs."""

import json
import re


class ToolError(ValueError):
    """An error message meant for the model, so it can retry."""


class Int:
    def __init__(self, lo, hi, odd=False, doc=""):
        self.lo, self.hi, self.odd, self.doc = lo, hi, odd, doc

    def schema(self):
        return {
            "type": "integer",
            "minimum": self.lo,
            "maximum": self.hi,
            "description": self.doc,
        }

    def check(self, name, value):
        if type(value) is not int:
            raise ToolError(
                f"{name} must be an integer, "
                f"got {type(value).__name__} {value!r:.40}"
            )
        if not self.lo <= value <= self.hi:
            raise ToolError(
                f"{name} must lie in [{self.lo}, {self.hi}], "
                f"got {value}"
            )
        if self.odd and value % 2 == 0:
            raise ToolError(f"{name} must be odd, got {value}")
        return value


class Bits:
    def __init__(self, max_len, doc=""):
        self.max_len, self.doc = max_len, doc

    def schema(self):
        return {
            "type": "string",
            "pattern": f"^[01]{{1,{self.max_len}}}$",
            "description": self.doc,
        }

    def check(self, name, value):
        if not isinstance(value, str) or not re.fullmatch(
            f"[01]{{1,{self.max_len}}}", value
        ):
            raise ToolError(
                f"{name} must be a string of 1 to "
                f"{self.max_len} characters 0 and 1, "
                f"got {type(value).__name__} {value!r:.40}"
            )
        return value


class Text:
    def __init__(self, max_len, doc=""):
        self.max_len, self.doc = max_len, doc

    def schema(self):
        return {
            "type": "string",
            "maxLength": self.max_len,
            "description": self.doc,
        }

    def check(self, name, value):
        if (
            not isinstance(value, str)
            or len(value) > self.max_len
        ):
            raise ToolError(
                f"{name} must be a string of at most "
                f"{self.max_len} characters"
            )
        return value


def parse_arguments(raw):
    """Tool arguments arrive as a JSON string from the model."""
    if isinstance(raw, dict):
        return raw
    try:
        args = json.loads(raw or "{}")
    except ValueError as e:
        raise ToolError(f"arguments are not valid JSON: {e}")
    if not isinstance(args, dict):
        raise ToolError("arguments must be a JSON object")
    return args


def validate(params, args):
    """Reject unknown and missing arguments; check every value."""
    unknown = set(args) - set(params)
    if unknown:
        raise ToolError(f"unknown argument(s): {sorted(unknown)}")
    missing = set(params) - set(args)
    if missing:
        raise ToolError(f"missing argument(s): {sorted(missing)}")
    return {
        name: spec.check(name, args[name])
        for name, spec in params.items()
    }
