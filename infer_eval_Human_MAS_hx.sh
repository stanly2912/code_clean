#!/bin/bash
set -euo pipefail


#========================配置==============================


# ===== 国内 HuggingFace 镜像源 =====
export HF_ENDPOINT="https://hf-mirror.com"


# ==========================================
# 1. 基础配置
# ==========================================
INFER_SCRIPT="/home/wangbn/code_clean/inferHuman_hx.py"
EVAL_SCRIPT="/home/wangbn/code_clean/evalHuman_hx.py"  # 评测脚本路径
BASE_RESULT_DIR="/home/wangbn/infer_results_hx/Human_results"

# 测试题数 (测试时用 2，全集跑用 164)
NUM_TEST=1

#K_SAMPLES=1
#--k_samples 1

# 3. MAS 架构配置列表
MAS_CONFIGS=(
    # 示例配置 1 (你需要根据实际 yaml 名字修改)
    "solver_old|inferQWcode25.yaml|/home/wangbn/code_clean/human-eval/human_eval/codesQWcoder.jsonl"
    "solver_A|inferQWcode25.yaml|/home/wangbn/code_clean/human-eval/human_eval/codesQWcoder.jsonl"
    "solver_B|inferQWcode25.yaml|/home/wangbn/code_clean/human-eval/human_eval/codesQWcoder.jsonl"
    "solver_C|inferQWcode25.yaml|/home/wangbn/code_clean/human-eval/human_eval/codesQWcoder.jsonl"
    
    # 示例配置 2 (如果没有历史文件，可以留空第三个参数，只写两个竖线)
    # "MAS_Solver_B|inferQWcode25_v2.yaml|"
    
    # 示例配置 3
    # "MAS_Solver_C|inferQWcode25_v3.yaml|${BASE_RESULT_DIR}/QW_coder_7B_Base/local/humaneval_pass5.jsonl"
)

#========================配置结束==============================



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
# 2. 启动 6001 Base 模型 (用于所有 MAS 底座)
# ==========================================
log "启动 MAS Base 模型服务 (Port 6001)..."
cd /home/wangbn/LLaMA-Factory || exit 1

API_BASE_LOG="/home/wangbn/api6001_human_MAS.log"
API_PORT=6001 CUDA_VISIBLE_DEVICES=1 nohup \
    llamafactory-cli api /home/wangbn/code_clean/infer_scripts/inferQWcode.yaml \
    > "${API_BASE_LOG}" 2>&1 &
API_BASE_PID=$!

wait_for_port "127.0.0.1" 6001 "${API_BASE_PID}" "MAS Base 模型"

# ==========================================
# 4. 执行循环 (推理 + 评测)
# ==========================================
for config in "${MAS_CONFIGS[@]}"; do
    IFS='|' read -r MAS_FILE TUNE_YAML MAS_HISTORY <<< "${config}"

    log "================================================="
    log "🚀 开始测试 MAS 架构: [${MAS_FILE}]"
    log "================================================="
    export MAS_FILE=${MAS_FILE}
    OUT_DIR="${BASE_RESULT_DIR}/${MAS_FILE}"
    # 生成的 JSONL 文件的绝对路径 (依据 inferHuman_hx.py 的保存逻辑)
    GENERATED_JSONL="${OUT_DIR}/MAS/humaneval_pass5.jsonl"

    # ---------------- 步骤 A: 启动 7001 Tune ----------------
    cd /home/wangbn/LLaMA-Factory || exit 1
    API_TUNE_LOG="/home/wangbn/api7001_human_${MAS_FILE}.log"

    log "启动 MAS Tune API (Port 7001) 使用配置: ${TUNE_YAML}"
    API_PORT=7001 CUDA_VISIBLE_DEVICES=1 nohup \
        llamafactory-cli api "/home/wangbn/code_clean/infer_scripts/${TUNE_YAML}" \
        > "${API_TUNE_LOG}" 2>&1 &
    API_PID=$!

    wait_for_port "127.0.0.1" 7001 "${API_PID}" "MAS Tune API"

    # ---------------- 步骤 B: 运行推理 ----------------
    INFER_CMD=(
        python "${INFER_SCRIPT}"
        --mode "MAS"
        --output_path "${OUT_DIR}"
        --limit "${NUM_TEST}"
    )

    if [[ -n "${MAS_HISTORY}" ]]; then
        log "注入历史代码结果: ${MAS_HISTORY}"
        INFER_CMD+=(--mas_history_file "${MAS_HISTORY}")
    fi

    log "🧠 执行 MAS 代码生成推理..."
    CUDA_VISIBLE_DEVICES=0 "${INFER_CMD[@]}"

    # ---------------- 步骤 C: 运行评测 ----------------
    log "📊 代码生成完毕，立即启动自动评测..."
    # 传参告诉评测脚本，只评测刚刚生成的这个文件
    python "${EVAL_SCRIPT}" --target_file "${GENERATED_JSONL}"
    log "✅ [${MAS_FILE}] 架构评测完成！"

    # ---------------- 步骤 D: 清理 7001 ----------------
    log "清理当前 MAS Tune API，准备切换下一个架构..."
    kill "${API_PID}" 2>/dev/null || true
    unset API_PID
    sleep 5
    echo
done

log "🎉 所有 MAS 架构测试和评测流水线全部运行完毕！"