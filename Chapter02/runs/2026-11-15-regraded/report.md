# Report for runs/2026-11-15-regraded

prompt ch2-v1 (788fe6710cd9f084), tasks 1d125177c3fa34b9, samples 5

| model | acc@1 % [95% CI] | maj@k % | agreement | unparseable % | truncated % |
|---|---|---|---|---|---|
| gpt-oss-120b-vllm | 93.3 [87.7, 97.7] | 94.2 | 0.98 | 0.0 | 0.0 |
| qwen3-4b-vllm | 90.2 [84.2, 95.6] | 91.9 | 0.94 | 0.5 | 0.0 |
| qwen3-vllm | 92.1 [86.3, 97.0] | 93.0 | 0.96 | 0.0 | 0.0 |

## gpt-oss-120b-vllm

- tasks 86, samples 430, model errors 0
- by kind: antiderivative 100%, claim 100%, counterexample 100%, expression 100%, reference 42%, value 98%
- failure reasons: denied-existence 19, wrong-reference 7, arithmetic 3
- majority accuracy at agreement >= 0.8: (0.963855421686747, 83), below: (0.3333333333333333, 3)
- step chains behind right answers: {'checked': 35, 'invalid-step': 2, 'steps-not-expressions': 8}
- distractor gap (plain - distractor): (0.0, (0.0, 0.0))
- mean output tokens: 684

## qwen3-4b-vllm

- tasks 86, samples 430, model errors 0
- by kind: antiderivative 97%, claim 100%, counterexample 89%, expression 100%, reference 33%, value 97%
- failure reasons: wrong-reference 23, denied-existence 7, missed-counterexample 5, arithmetic 5
- majority accuracy at agreement >= 0.8: (0.975, 80), below: (0.16666666666666666, 6)
- step chains behind right answers: {'checked': 35, 'invalid-step': 1, 'steps-not-expressions': 33}
- distractor gap (plain - distractor): (0.04999999999999999, (0.0, 0.14999999999999997))
- mean output tokens: 1614

## qwen3-vllm

- tasks 86, samples 430, model errors 0
- by kind: antiderivative 100%, claim 100%, counterexample 96%, expression 100%, reference 33%, value 99%
- failure reasons: wrong-reference 19, denied-existence 11, false-counterexample 2, arithmetic 2
- majority accuracy at agreement >= 0.8: (0.975609756097561, 82), below: (0.0, 4)
- step chains behind right answers: {'checked': 35, 'invalid-step': 1, 'steps-not-expressions': 20}
- distractor gap (plain - distractor): (0.0, (0.0, 0.0))
- mean output tokens: 1517

gpt-oss-120b-vllm - qwen3-4b-vllm: +3.0 points, 95% CI [+0.2, +6.5]

gpt-oss-120b-vllm - qwen3-vllm: +1.2 points, 95% CI [-0.7, +3.7]

qwen3-4b-vllm - qwen3-vllm: -1.9 points, 95% CI [-4.4, +0.0]
