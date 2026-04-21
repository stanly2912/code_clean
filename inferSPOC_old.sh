#!/bin/bash
# nohup bash /home/wangbn/code_clean/infClean.sh > /home/wangbn/code_clean/infclean_log.txt 2>&1 &
set -e

cleanup() {
    kill "${API_PID:-}" 2>/dev/null || true
    kill "${API_BASE_PID:-}" 2>/dev/null || true
}
trap cleanup EXIT

# 启动 6002 端口服务，并记录 PID
cd /home/wangbn/LLaMA-Factory || exit 1
API_BASE_LOG="api6002.log"
API_PORT=6002 CUDA_VISIBLE_DEVICES=0 nohup llamafactory-cli api /home/wangbn/code_clean/infer_scripts/inferQWcode.yaml > "${API_BASE_LOG}" 2>&1 &
API_BASE_PID=$!

# for model in QWcode25 QWcode50 QWcode75; do
for model in QWcode; do
    cd /home/wangbn/LLaMA-Factory || exit 1

    # 启动 7002 端口 API，并记录 PID
    API_TUNE_LOG="api7002_${model}.log"
    API_PORT=7002 CUDA_VISIBLE_DEVICES=0 nohup llamafactory-cli api /home/wangbn/code_clean/infer_scripts/infer${model}.yaml > "${API_TUNE_LOG}" 2>&1 &
    API_PID=$!

    echo "正在等待大模型加载进显存 (60秒)..."
    sleep 60

    # 进入 SPOC 评估目录
    cd /home/wangbn/code_clean/spoc/ || exit

    # 生成代码 (改为 SPOC 的推理命令)
    python ./infer.py --output ./tmp_codes${model}.json






    echo "评测完毕，清理后台大模型释放资源..."
    kill "${API_PID}" 2>/dev/null || true
    unset API_PID
    sleep 5
done