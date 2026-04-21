#!/bin/bash
# nohup bash /home/wangbn/code_clean/infClean.sh > /home/wangbn/code_clean/infclean_log.txt 2>&1 &
set -e

# 先启动 6000 端口服务，并记录 PID
cd /home/wangbn/LLaMA-Factory || exit 1
API6000_LOG=api6000.log
API_PORT=6000 CUDA_VISIBLE_DEVICES=0 nohup llamafactory-cli api /home/wangbn/code_clean/infer_scripts/inferQWcode.yaml > "${API6000_LOG}" 2>&1 &
API6000_PID=$!

# for model in QWcode25 QWcode50 QWcode75; do
for model in QWcode25; do
    # 进入 LLaMA-Factory 目录
    cd /home/wangbn/LLaMA-Factory || exit 1

    # 启动 7000 端口 API，并记录 PID
    API7000_LOG="api7000_${model}.log"
    API_PORT=7000 CUDA_VISIBLE_DEVICES=0 nohup llamafactory-cli api /home/wangbn/code_clean/infer_scripts/infer${model}.yaml > "${API7000_LOG}" 2>&1 &
    API_PID=$!

    echo "正在等待大模型加载进显存 (60秒)..."
    sleep 60

    # 进入优化推理目录
    cd /home/wangbn/code_clean || exit 1

        #--input /home/wangbn/code_clean/human-eval/human_eval/codesQWcoder.jsonl \
        #--input /home/wangbn/code_clean/gpt4o_human_eval_result_fixed.jsonl\
    python -u ./infClean.py \
        --input /home/wangbn/code_clean/human-eval/human_eval/codesQWcoder.jsonl \
        --output /home/wangbn/code_clean/human-eval/human_eval/tmp_${model}.jsonl

    echo "优化完成，关闭 7000 端口模型进程: ${API_PID}"
    kill "${API_PID}" 2>/dev/null || true
    sleep 5
done

# 关闭 6000 端口模型进程
echo "关闭 6000 端口模型进程: ${API6000_PID}"
kill "${API6000_PID}" 2>/dev/null || true