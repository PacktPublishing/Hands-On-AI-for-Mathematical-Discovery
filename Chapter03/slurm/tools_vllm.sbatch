#!/bin/bash
# Serve one open-weight model with tool calling and run the experiment.
#SBATCH --job-name=ch3-tools
#SBATCH --partition=gpu          # your GPU partition
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=128G
#SBATCH --time=04:00:00
#SBATCH --dependency=singleton    # one server at a time (port 8000)
#SBATCH --output=logs/%x-%j.out

set -euo pipefail
export PYTHONUNBUFFERED=1
MODEL=${MODEL:-openai/gpt-oss-120b}     # Hugging Face repository
NAME=${NAME:-gpt-oss-120b-vllm}         # entry in the config
CONFIG=${CONFIG:-configs/models.example.json}
# Extra vLLM arguments. gpt-oss: --tool-call-parser openai
# Qwen3: --tool-call-parser hermes --reasoning-parser qwen3
# Two GPUs: add --tensor-parallel-size 2 (and request two GPUs)
TOOL_ARGS=${TOOL_ARGS:---tool-call-parser openai}
EXP_ARGS=${EXP_ARGS:-}                  # e.g. --modes plain
PORT=${PORT:-8000}
RUN=${RUN:-runs/$(date +%Y-%m-%d)-$NAME}
mkdir -p logs "$RUN"

command -v vllm > /dev/null || {
    echo "vllm not found: activate your environment before sbatch"
    exit 1
}
python -c "import vllm; print(vllm.__version__)" > "$RUN/vllm-version.txt"
vllm serve "$MODEL" --port "$PORT" --seed 0 --max-model-len 40960 \
    --enable-auto-tool-choice $TOOL_ARGS \
    > "logs/vllm-$SLURM_JOB_ID.log" 2>&1 &
SERVER=$!
trap 'kill $SERVER' EXIT

until curl -sf "http://localhost:$PORT/v1/models" > /dev/null; do
    kill -0 $SERVER || { echo "vLLM exited, see logs/"; exit 1; }
    sleep 10
done

python -m mathtools.experiment --config "$CONFIG" --models "$NAME" \
    --samples 3 --workers 8 --out "$RUN" $EXP_ARGS
python -m mathtools.report "$RUN"
