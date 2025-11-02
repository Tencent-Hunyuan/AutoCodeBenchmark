# export NCCL_DEBUG=INFO
# export VLLM_WORKER_MULTIPROC_METHOD=spawn
TASKS=(
autocodebench.jsonl
)

MODELS=(
Qwen2.5-Coder-32B-Instruct
)

for task in "${TASKS[@]}"; do
for model in "${MODELS[@]}"; do

    model_name=$(basename "$model")
    tp=8
    bs=512

    python3 vllm_offline.py \
        --task $task \
        --model_path $model \
        --output_file model_output.jsonl \
        --n 1 \
        --max_tokens 8192 \
        --batch_size $bs \
        --tp $tp

done
done

# enable_thinking
# python3 vllm_offline.py --task python --model_path Qwen/Qwen3-8B --output_file outputs/qwen3-8b-nothink/$task.jsonl --n 1 --max_tokens 8192 --batch_size 64 --enable_thinking

