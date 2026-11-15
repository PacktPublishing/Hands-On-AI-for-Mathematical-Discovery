# Report for runs/2026-11-15-qwen3-4b-vllm

prompt ch2-v1 (788fe6710cd9f084), tasks 1d125177c3fa34b9, samples 5

| model | acc@1 % [95% CI] | maj@k % | agreement | unparseable % | truncated % |
|---|---|---|---|---|---|
| qwen3-4b-vllm | 83.7 [77.2, 90.0] | 89.5 | 0.87 | 8.1 | 0.0 |

## qwen3-4b-vllm

- tasks 86, samples 430, model errors 0
- by kind: antiderivative 97%, claim 100%, counterexample 89%, expression 100%, reference 33%, value 83%
- failure reasons: wrong-reference 30, arithmetic 5
- majority accuracy at agreement >= 0.8: (0.9714285714285714, 70), below: (0.5625, 16)
- right answer but broken step chain: (34, 35)
- distractor gap (plain - distractor): (0.09999999999999998, (0.0, 0.19999999999999996))
- mean output tokens: 1614
