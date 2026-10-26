"""Evidence ledger: an append-only, hash-chained record."""

import hashlib, json, time
from enum import IntEnum


class Evidence(IntEnum):
    REFUTED = -1  # a verified counterexample exists
    PROPOSED = 0  # stated, no evidence yet
    SUPPORTED = 1  # consistent with the motivating examples
    SURVIVED_SEARCH = 2  # no counterexample within a stated budget
    VALIDATED = 3  # numerical validation against known cases
    CERTIFIED = 4  # exact or certified computation
    FORMALLY_VERIFIED = 5  # machine-checked proof, no extra axioms


class Ledger:
    def __init__(self, path):
        self.path, self.prev = path, "0" * 64
        open(path, "w").close()

    def record(self, actor, action, claim_id=None, **payload):
        entry = {
            "t": time.time(),
            "actor": actor,
            "action": action,
            "claim": claim_id,
            "payload": payload,
            "prev": self.prev,
        }
        line = json.dumps(entry, sort_keys=True, default=str)
        self.prev = hashlib.sha256(line.encode()).hexdigest()
        with open(self.path, "a") as f:
            f.write(line + "\n")
        return self.prev
