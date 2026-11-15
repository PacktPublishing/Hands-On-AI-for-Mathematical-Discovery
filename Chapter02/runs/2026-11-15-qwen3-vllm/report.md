# Report for runs/2026-11-15-qwen3-vllm

prompt ch2-v1 (788fe6710cd9f084), tasks 1d125177c3fa34b9, samples 5

| model | acc@1 % [95% CI] | maj@k % | agreement | unparseable % | truncated % |
|---|---|---|---|---|---|
| qwen3-vllm | 86.0 [79.8, 91.9] | 91.9 | 0.90 | 6.0 | 0.0 |

## qwen3-vllm

- tasks 86, samples 430, model errors 0
- by kind: antiderivative 100%, claim 100%, counterexample 96%, expression 95%, reference 33%, value 88%
- failure reasons: wrong-reference 30, false-counterexample 2, arithmetic 2
- majority accuracy at agreement >= 0.8: (0.9733333333333334, 75), below: (0.5454545454545454, 11)
- right answer but broken step chain: (21, 35)
- distractor gap (plain - distractor): (0.15, (-0.10000000000000003, 0.4))
- mean output tokens: 1517
