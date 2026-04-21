#!/bin/bash
set -euo pipefail

# ===== 国内 HuggingFace 镜像源 =====
export HF_ENDPOINT="https://hf-mirror.com"

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
            log "错误: 等待超时 (${timeout}s)。"
            return 1
        fi
        sleep "${interval}"
    done
}

# ==========================================
# 1. 环境清理配置
# ==========================================
PYTHON_SCRIPT="/home/wangbn/code_clean/inferHuman_hx.py"
BASE_RESULT_DIR="/home/wangbn/infer_results_hx/Human_results"

NUM_TEST=50 # 测试题数

# ==========================================
# 2. 启动 6001 Base 模型 (占用 GPU 1)
# ==========================================
log "启动 Base 模型服务 (Port 6001)..."
cd /home/wangbn/LLaMA-Factory || exit 1

API_BASE_LOG="/home/wangbn/api6001_human.log"
# 这里挂载在 GPU 1
API_PORT=6001 CUDA_VISIBLE_DEVICES=1 nohup \
    llamafactory-cli api /home/wangbn/code_clean/infer_scripts/inferQWcode.yaml \
    > "${API_BASE_LOG}" 2>&1 &
API_BASE_PID=$!

log "Base 模型 PID: ${API_BASE_PID}"
wait_for_port "127.0.0.1" 6001 "${API_BASE_PID}" "Base 模型服务"

# ==========================================
# 3. 模型配置列表
# ==========================================
MODELS=(
   
    #"MAS|QWcode25_MAS|inferQWcode25.yaml||${BASE_RESULT_DIR}/QW_coder_7B_Base/local/humaneval_pass5.jsonl"
    

    #"local|baichuan2-7b-base|/home/data/wangbn/7B_model/baichuan2-7b-base|||"
    #"local|Olmo-7b-base|/home/data/wangbn/7B_model/Olmo-7b-base|||"
    "online|QW_coder_7B_instruct_API|qwen/qwen2.5-7b-instruct|https://api.jiekou.ai/openai|sk_VrZ4jhQDLWUK2lyQj40u5yr6p5Uq1lLpnQ4Cxh_BnUY|"
    "local|deepseek-coder-6.7b-instruct|/home/data/wangbn/7B_model/deepseek-coder-6.7b-instruct|||"
    "local|dolphin-2.6-mistral-7b-dpo|/home/data/wangbn/7B_model/dolphin-2.6-mistral-7b-dpo|||"
    
    #"local|gamma-7b|/home/data/wangbn/7B_model/gamma-7b|||"



    #"online|qwen3-8B_API|qwen3-vl-8b-instruct|https://api.agicto.cn/v1|sk-88UT5OLYRw6so66EliV7rNFI4Y9oblR1Lns3dKNjwXABVtk7|"
    #"online|mis7b_API|open-mistral-7b|https://api.agicto.cn/v1|sk-88UT5OLYRw6so66EliV7rNFI4Y9oblR1Lns3dKNjwXABVtk7|"

    #"online|internlm2.5-7b-chat|internlm/internlm2_5-7b-chat|https://api.siliconflow.cn/v1|sk-dpgpkzrralqslyeibhmecrxuphylarytbstgsqbdrnoyykbb|"

    #"online|DSR1-7b|/home/data/wangbn/7B_model/DSR1-7b|https://api.siliconflow.cn/v1|sk-dpgpkzrralqslyeibhmecrxuphylarytbstgsqbdrnoyykbb|"

    #"online|hunyuan-7b|/home/data/wangbn/7B_model/hunyuan-7b|https://api.siliconflow.cn/v1|sk-dpgpkzrralqslyeibhmecrxuphylarytbstgsqbdrnoyykbb|"

    #"local|QW_coder_7B_Base|/home/data/wangbn/7B_model/Qwen2.5-Coder-7b-Base|||"
  
    #"local|LMA_7B_Base|/home/data/wangbn/7B_model/CodeLlama-7b-hf|||"
    
   

)

# ==========================================
# 4. 执行循环
# ==========================================
for config in "${MODELS[@]}"; do
    IFS='|' read -r MODE MODEL_NAME MODEL_ARG API_URL API_KEY MAS_HISTORY <<< "${config}"

    log "================================================="
    log "启动测试: [${MODEL_NAME}] 模式: [${MODE}]"
    log "================================================="

    OUT_DIR="${BASE_RESULT_DIR}/${MODEL_NAME}"

    CMD=(
        python "${PYTHON_SCRIPT}"
        --mode "${MODE}"
        --output_path "${OUT_DIR}"
        --limit "${NUM_TEST}"
    )

    if [[ "${MODE}" == "MAS" ]]; then
        cd /home/wangbn/LLaMA-Factory || exit 1
        API_TUNE_LOG="/home/wangbn/api7001_human_${MODEL_NAME}.log"

        # Tune API 也挂载在 GPU 1
        log "启动 MAS Tune API (Port 7001)..."
        API_PORT=7001 CUDA_VISIBLE_DEVICES=1 nohup \
            llamafactory-cli api "/home/wangbn/code_clean/infer_scripts/${MODEL_ARG}" \
            > "${API_TUNE_LOG}" 2>&1 &
        API_PID=$!

        wait_for_port "127.0.0.1" 7001 "${API_PID}" "MAS Tune API"

        if [[ -n "${MAS_HISTORY}" ]]; then
            CMD+=(--mas_history_file "${MAS_HISTORY}")
        fi

        log "执行 MAS 推理..."
        # MAS 模式下由于只请求 API，不加载本地模型，默认显卡即可
        CUDA_VISIBLE_DEVICES=0 "${CMD[@]}"

        log "清理 Tune API..."
        kill "${API_PID}" 2>/dev/null || true
        unset API_PID
        sleep 5

    elif [[ "${MODE}" == "local" ]]; then
        log "执行 Local 推理，模型: ${MODEL_ARG}"
        CMD+=(--model_path "${MODEL_ARG}")
        # ===== 关键修复：把 Local 模型严格限制在 GPU 0 =====
        CUDA_VISIBLE_DEVICES=0 "${CMD[@]}"

    elif [[ "${MODE}" == "online" ]]; then
        log "执行 Online 推理，模型: ${MODEL_ARG}"
        CMD+=(--online_model "${MODEL_ARG}")
        if [[ -n "${API_URL}" ]]; then
            CMD+=(--api_url "${API_URL}")
        fi
        if [[ -n "${API_KEY}" ]]; then
            CMD+=(--api_key "${API_KEY}")
        fi
        # Online不消耗显存，放GPU 0
        CUDA_VISIBLE_DEVICES=0 "${CMD[@]}"
    fi

    log "--- [${MODEL_NAME}] 测试完成 ---"
    echo
done

log "所有运行完毕！"