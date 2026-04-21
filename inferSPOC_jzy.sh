#!/bin/bash
set -euo pipefail

# ==========================================
# 0. 通用函数
# ==========================================
timestamp() {
    date '+%F %T'
}

log() {
    echo "[$(timestamp)] $*"
}

cleanup() {
    log "清理后台 API 进程..."
    [[ -n "${API_PID:-}" ]] && kill "${API_PID}" 2>/dev/null || true
    [[ -n "${API_BASE_PID:-}" ]] && kill "${API_BASE_PID}" 2>/dev/null || true
}
trap cleanup EXIT

wait_for_port() {
    local host="$1"
    local port="$2"
    local pid="${3:-}"
    local service_name="$4"
    local timeout="${5:-1800}"
    local interval="${6:-2}"

    local start_ts now_ts elapsed
    start_ts=$(date +%s)
    log "等待 ${service_name} 就绪: ${host}:${port} (超时 ${timeout}s)"

    while true; do
        if (echo > "/dev/tcp/${host}/${port}") >/dev/null 2>&1; then
            now_ts=$(date +%s)
            elapsed=$((now_ts - start_ts))
            log "${service_name} 已就绪，端口 ${port} 已开启，耗时 ${elapsed}s"
            return 0
        fi

        if [[ -n "${pid}" ]] && ! kill -0 "${pid}" 2>/dev/null; then
            log "错误: ${service_name} 进程已退出，启动失败。"
            return 1
        fi

        now_ts=$(date +%s)
        elapsed=$((now_ts - start_ts))

        if (( elapsed >= timeout )); then
            log "错误: 等待 ${service_name} 超时 (${timeout}s)，端口 ${port} 仍未开启。"
            return 1
        fi

        if (( elapsed == 0 || elapsed % 10 == 0 )); then
            log "${service_name} 仍在启动中... 已等待 ${elapsed}s"
        fi
        sleep "${interval}"
    done
}

# ==========================================
# 1. 环境清理配置
# ==========================================
PYTHON_SCRIPT="/home/wangbn/code_clean/inferSpoc_jzy.py"
BASE_RESULT_DIR="/home/wangbn/code_clean/infer_results_jzy"
SPOC_DATA_DIR="/home/wangbn/code_clean/spoc"

# 测试题目数量
NUM_TEST=2

# ==========================================
# 2. 启动 6001 Base 模型 (供 API 模式使用)
# ==========================================
log "启动 Base 模型服务 (Port 6001)..."
cd /home/wangbn/LLaMA-Factory || exit 1

API_BASE_LOG="/home/wangbn/api6001_spoc.log"
API_PORT=6001 CUDA_VISIBLE_DEVICES=1 nohup \
    llamafactory-cli api /home/wangbn/code_clean/infer_scripts/inferQWcode.yaml \
    > "${API_BASE_LOG}" 2>&1 &
API_BASE_PID=$!

log "Base 模型 PID: ${API_BASE_PID}"
wait_for_port "127.0.0.1" 6001 "${API_BASE_PID}" "Base 模型服务"

# ==========================================
# 3. 模型配置列表 (格式: 模式|标识名|模型路径或名称|额外API_URL)
# ==========================================
# MAS 配置：智能体名|配置文件|历史代码(可选)
MAS_CONFIGS=(
    "solver_A|inferQWcode25.yaml|/home/wangbn/code_clean/human-eval/human_eval/codesQWcoder.jsonl"
)
MODELS=(
    # --- API 模式 (双模型交互) ---
    #"API|QWcode25_API|inferQWcode25.yaml|"
    
    # --- Local 本地模型 ---
   # "local|QW_coder_7B_instruct|/home/wangbn/7B_model/Qwen2_5-Coder-7B-instruct|"
    "local|deepseek-coder-6.7b-instruct|/home/data/wangbn/7B_model/deepseek-coder-6.7b-instruct|"

    # --- Online 线上模型 ---
    #"online|gpt-4.1_API|gpt-4.1|https://api.agicto.cn/v1"
    #"MAS|solver_A|inferQWcode25.yaml|/home/wangbn/code_clean/human-eval/human_eval/codesQWcoder.jsonl"  # 模式是 MAS
)

# ==========================================
# 4. 执行循环
# ==========================================
for config in "${MODELS[@]}"; do
    IFS='|' read -r MODE MODEL_NAME MODEL_ARG API_URL <<< "${config}"

    log "================================================="
    log "启动测试: [${MODEL_NAME}] 模式: [${MODE}]"
    log "================================================="

    OUT_DIR="${BASE_RESULT_DIR}/${MODEL_NAME}"

    CMD=(
        python "${PYTHON_SCRIPT}"
        --mode "${MODE}"
        --output_path "${OUT_DIR}"
        --test_limit "${NUM_TEST}"
        --spoc_path "${SPOC_DATA_DIR}"  # 新增此行，将路径传递给 Python 脚本
    )

    if [[ "${MODE}" == "API" ]]; then
        cd /home/wangbn/LLaMA-Factory || exit 1
        API_TUNE_LOG="/home/wangbn/api7001_spoc_${MODEL_NAME}.log"

        log "启动 Tune API (Port 7001)，配置: ${MODEL_ARG}"
        API_PORT=7001 CUDA_VISIBLE_DEVICES=1 nohup \
            llamafactory-cli api "/home/wangbn/code_clean/infer_scripts/${MODEL_ARG}" \
            > "${API_TUNE_LOG}" 2>&1 &
        API_PID=$!

        log "Tune API PID: ${API_PID}"
        wait_for_port "127.0.0.1" 7001 "${API_PID}" "Tune API"

        log "执行 API 模式推理..."
        "${CMD[@]}"

        log "清理 Tune API..."
        kill "${API_PID}" 2>/dev/null || true
        unset API_PID
        sleep 5
    elif [[ "${MODE}" == "MAS" ]]; then
        # 新增的 MAS 处理逻辑
        export MAS_FILE="${MODEL_NAME}"  # 传递智能体标识
        
        cd /home/wangbn/LLaMA-Factory || exit 1
        API_TUNE_LOG="/home/wangbn/api7001_spoc_MAS_${MODEL_NAME}.log"

        log "启动 MAS Tune API (Port 7001) 使用配置: ${MODEL_ARG}"
        API_PORT=7001 CUDA_VISIBLE_DEVICES=1 nohup \
            llamafactory-cli api "/home/wangbn/code_clean/infer_scripts/${MODEL_ARG}" \
            > "${API_TUNE_LOG}" 2>&1 &
        API_PID=$!

        wait_for_port "127.0.0.1" 7001 "${API_PID}" "MAS Tune API"

        log "执行 MAS 模式推理..."
        # 如果有历史代码，可以在这里 CMD+=(--mas_history_file "路径")
        "${CMD[@]}"

        log "清理 MAS Tune API..."
        kill "${API_PID}" 2>/dev/null || true
        unset API_PID
        sleep 5

    elif [[ "${MODE}" == "local" ]]; then
        log "执行 Local 推理，模型: ${MODEL_ARG}"
        CMD+=(--model_path "${MODEL_ARG}")
        "${CMD[@]}"

    elif [[ "${MODE}" == "online" ]]; then
        log "执行 Online 推理，模型: ${MODEL_ARG}"
        CMD+=(--online_model "${MODEL_ARG}")
        if [[ -n "${API_URL}" ]]; then
            CMD+=(--api_url "${API_URL}")
        fi
        "${CMD[@]}"
    fi

    log "--- [${MODEL_NAME}] 测试完成 ---"
    echo
done

log "所有配置运行完毕！"