# export NCCL_DEBUG=INFO
# export VLLM_WORKER_MULTIPROC_METHOD=spawn
TASKS=(
autocodebench_completion_3shot.jsonl

)

MODELS=(
Qwen/Qwen2.5-Coder-7B
Qwen/Qwen3-8B-Base

)

for task in "${TASKS[@]}"; do
for model in "${MODELS[@]}"; do

    model_name=$(basename "$model")
    tp=8
    bs=256

    # 为特定模型设置tp=8
    if [[ "$model_name" == "DeepSeek-V3-Base" ]] || 
       [[ "$model_name" == "Kimi-K2-Base" ]]; then
        tp=8
        bs=6
    fi

    python3 vllm_offline.py \
        --task $task \
        --model_path $model \
        --output_file $model_name.jsonl \
        --n 1 \
        --max_tokens 16384 \
        --batch_size $bs \
        --tp $tp \
        --greedy

done
done

# enable_thinking
# python3 vllm_offline.py --task python --model_path /apdcephfs_jn/share_302867151/yeszhou/llms/Qwen/Qwen3-8B --output_file outputs/qwen3-8b-nothink/$task.jsonl --n 1 --max_tokens 8192 --batch_size 64 --enable_thinking

