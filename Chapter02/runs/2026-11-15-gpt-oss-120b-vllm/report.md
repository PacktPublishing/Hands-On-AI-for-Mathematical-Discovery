# Report for runs/2026-11-15-gpt-oss-120b-vllm

prompt ch2-v1 (788fe6710cd9f084), tasks 1d125177c3fa34b9, samples 5

| model | acc@1 % [95% CI] | maj@k % | agreement | unparseable % | truncated % |
|---|---|---|---|---|---|
| gpt-oss-120b-vllm | 93.3 [87.7, 97.7] | 94.2 | 0.98 | 0.0 | 0.0 |

## gpt-oss-120b-vllm

- tasks 86, samples 430, model errors 0
- by kind: antiderivative 100%, claim 100%, counterexample 100%, expression 100%, reference 42%, value 98%
- failure reasons: wrong-reference 26, arithmetic 3
- majority accuracy at agreement >= 0.8: (0.963855421686747, 83), below: (0.3333333333333333, 3)
- right answer but broken step chain: (10, 35)
- distractor gap (plain - distractor): (0.0, (0.0, 0.0))
- mean output tokens: 684

## Cited identifiers that did not match

- gpt-oss-120b-vllm ref-alphatensor: none -> not-an-identifier
- gpt-oss-120b-vllm ref-alphatensor: none -> not-an-identifier
- gpt-oss-120b-vllm ref-alphatensor: none -> not-an-identifier
- gpt-oss-120b-vllm ref-alphatensor: doi:10.1038/s41586-022-04540-5 -> not-found
- gpt-oss-120b-vllm ref-alphatensor: none -> not-an-identifier
- gpt-oss-120b-vllm ref-gsm: none -> not-an-identifier
- gpt-oss-120b-vllm ref-gsm: none -> not-an-identifier
- gpt-oss-120b-vllm ref-gsm: none -> not-an-identifier
- gpt-oss-120b-vllm ref-gsm: none -> not-an-identifier
- gpt-oss-120b-vllm ref-gsm: none -> not-an-identifier
- gpt-oss-120b-vllm ref-platt: arXiv:1909.04118 -> exists
- gpt-oss-120b-vllm ref-platt: none -> not-an-identifier
- gpt-oss-120b-vllm ref-platt: none -> not-an-identifier
- gpt-oss-120b-vllm ref-platt: arXiv:1908.05853 -> exists
- gpt-oss-120b-vllm ref-platt: arXiv:2008.07225 -> exists
- gpt-oss-120b-vllm ref-selfcons: arXiv:2209.11171 -> exists
- gpt-oss-120b-vllm ref-wagner: none -> not-an-identifier
- gpt-oss-120b-vllm ref-wagner: none -> not-an-identifier
- gpt-oss-120b-vllm ref-wagner: none -> not-an-identifier
- gpt-oss-120b-vllm ref-wagner: arXiv:2105.08421 -> exists
- gpt-oss-120b-vllm ref-wagner: arXiv:2105.01585 -> exists
- gpt-oss-120b-vllm ref-walters: none -> not-an-identifier
- gpt-oss-120b-vllm ref-walters: none -> not-an-identifier
- gpt-oss-120b-vllm ref-walters: none -> not-an-identifier
- gpt-oss-120b-vllm ref-walters: none -> not-an-identifier
- gpt-oss-120b-vllm ref-walters: none -> not-an-identifier
