#!/bin/bash
# Serve one open-weight model with vLLM and benchmark it.
#SBATCH --job-name=ch2-bench
#SBATCH --partition=gpu          # your GPU partition
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=08:00:00
#SBATCH --output=logs/%x-%j.out

set -euo pipefail
MODEL=${MODEL:-openai/gpt-oss-120b}     # Hugging Face repository
NAME=${NAME:-gpt-oss-120b-vllm}         # entry in configs/models.json
PORT=${PORT:-8000}
RUN=${RUN:-runs/$(date +%Y-%m-%d)-$NAME}
mkdir -p logs "$RUN"

python -c "import vllm; print(vllm.__version__)" > "$RUN/vllm-version.txt"
vllm serve "$MODEL" --port "$PORT" --seed 0 --max-model-len 32768 \
    > "logs/vllm-$SLURM_JOB_ID.log" 2>&1 &
SERVER=$!
trap 'kill $SERVER' EXIT

until curl -sf "http://localhost:$PORT/v1/models" > /dev/null; do
    kill -0 $SERVER || { echo "vLLM exited, see logs/"; exit 1; }
    sleep 10
done

python -m harness.run --config configs/models.json --models "$NAME" \
    --samples 5 --workers 16 --out "$RUN"
python -m harness.report "$RUN"
