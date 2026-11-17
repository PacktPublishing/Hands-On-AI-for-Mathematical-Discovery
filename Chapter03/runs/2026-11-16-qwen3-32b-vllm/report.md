# Report for runs/2026-11-16-qwen3-32b-vllm

| model | mode | accuracy % [95% CI] | orbit | word | census | tokens | seconds |
|---|---|---|---|---|---|---|---|
| qwen3-32b-vllm | plain | 29.8 [17.9, 42.9] | 67 | 17 | 0 | 7216 | 377.5 |
| qwen3-32b-vllm | tools | 100.0 [100.0, 100.0] | 100 | 100 | 100 | 1437 | 74.9 |

## Tool use: qwen3-32b-vllm

{
  "calls": 83,
  "calls_per_task": 0.99,
  "rounds_per_task": 1.99,
  "rejected": 0,
  "conversations_with_rejection": 0,
  "of_which_correct": 0,
  "no_tool_used": 1,
  "budget_exhausted": 0,
  "truncated": 0,
  "by_tool": {
    "cycle_census": 24,
    "orbit": 30,
    "word_cycle": 29
  },
  "rejections": []
}

tools - plain: +70.2 points, 95% CI [+58.3, +82.1]

model errors: 0
