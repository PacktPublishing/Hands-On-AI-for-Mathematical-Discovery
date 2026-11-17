# Report for runs/2026-11-16-gpt-oss-120b-vllm

| model | mode | accuracy % [95% CI] | orbit | word | census | tokens | seconds |
|---|---|---|---|---|---|---|---|
| gpt-oss-120b-vllm | plain | 59.5 [44.0, 73.8] | 63 | 50 | 67 | 3986 | 51.3 |
| gpt-oss-120b-vllm | tools | 98.8 [96.4, 100.0] | 100 | 97 | 100 | 411 | 5.6 |

## Tool use: gpt-oss-120b-vllm

{
  "calls": 119,
  "calls_per_task": 1.42,
  "rounds_per_task": 2.42,
  "rejected": 8,
  "conversations_with_rejection": 5,
  "of_which_correct": 5,
  "no_tool_used": 1,
  "budget_exhausted": 0,
  "truncated": 0,
  "by_tool": {
    "cycle_census": 41,
    "cycle_formula": 2,
    "cycle_survey": 8,
    "exact_eval": 6,
    "orbit": 35,
    "word_cycle": 27
  },
  "rejections": [
    "arguments are not valid JSON: Expecting ',' delimiter: line 1 column 492 (char 491)",
    "expression must be a string of at most 300 characters",
    "not a valid expression: invalid syntax (<unknown>, line 1)",
    "x_max must lie in [1, 10000], got 1000000",
    "max_len must lie in [1, 20], got 100",
    "x_max must lie in [1, 10000], got 100000",
    "max_len must lie in [1, 20], got 33",
    "max_len must lie in [1, 20], got 30"
  ]
}

tools - plain: +39.3 points, 95% CI [+25.0, +53.6]

model errors: 0
