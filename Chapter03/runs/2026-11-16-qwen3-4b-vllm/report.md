# Report for runs/2026-11-16-qwen3-4b-vllm

| model | mode | accuracy % [95% CI] | orbit | word | census | tokens | seconds |
|---|---|---|---|---|---|---|---|
| qwen3-4b-vllm | plain | 25.0 [13.1, 39.3] | 43 | 20 | 8 | 7133 | 71.8 |
| qwen3-4b-vllm | tools | 100.0 [100.0, 100.0] | 100 | 100 | 100 | 918 | 9.2 |

## Tool use: qwen3-4b-vllm

{
  "calls": 84,
  "calls_per_task": 1.0,
  "rounds_per_task": 2.0,
  "rejected": 0,
  "conversations_with_rejection": 0,
  "of_which_correct": 0,
  "no_tool_used": 0,
  "budget_exhausted": 0,
  "truncated": 0,
  "by_tool": {
    "cycle_census": 24,
    "orbit": 30,
    "word_cycle": 30
  },
  "rejections": []
}

tools - plain: +75.0 points, 95% CI [+61.9, +88.1]

model errors: 0
