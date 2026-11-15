"""One versioned prompt for all models and all tasks."""

import hashlib, json

PROMPT_VERSION = "ch2-v1"

SYSTEM = """You are a careful mathematician.
Reply with one JSON object and nothing else, with these keys:
  "assumptions": list of every assumption you add to the question,
  "steps": list of short reasoning steps,
  "final_answer": string in the answer format given in the question,
  "witness": string, only when a true/false question is false.
Do not use LaTeX inside final_answer or witness."""

FORMATS = {
    "value": "one exact expression in Python/SymPy syntax, such as "
    "pi**2/6, sqrt(2)/4, or 137; write diverges if the "
    "quantity does not exist.",
    "expression": "one expression in the given variables in "
    "Python/SymPy syntax, such as n*(n+1)/2 or Abs(x).",
    "antiderivative": "one antiderivative in Python/SymPy syntax, "
    "without the constant of integration.",
    "counterexample": "a single integer, or none if no such number "
    "is known.",
    "claim": "true or false. If false, give a counterexample in "
    "witness, in the form the question asks for.",
    "reference": "the identifier only, as arXiv:NNNN.NNNNN or "
    "doi:10.NNNN/..., or none if no such work exists.",
}

CHAIN = (
    "\nIn steps, write each step as one expression in the given "
    "variables, equal to the previous step on the stated domain."
)


def build_messages(task):
    user = (
        task["prompt"]
        + "\n\nAnswer format: "
        + FORMATS[task["kind"]]
    )
    if task.get("chain"):
        user += CHAIN
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user},
    ]


def prompt_sha():
    blob = SYSTEM + CHAIN + json.dumps(FORMATS, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]
