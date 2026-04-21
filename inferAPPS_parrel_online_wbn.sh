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
    # 如果未来需要清理子进程，可以在这里扩展
    true
}
trap cleanup EXIT

# ==========================================
# 1. 环境配置
# ==========================================
PYTHON_SCRIPT="/home/wangbn/code_clean/inferAPPS_wbn.py"
BASE_RESULT_DIR="/home/wangbn/code_clean/infer_results_hx/APPS_results"

# 测试题目数量 (统一配置，方便修改)
NUM_INTRO=100
NUM_INTERVIEW=100
NUM_COMP=100

# ==========================================
# 2. 模型配置列表 (格式: 模式|标识名|模型路径或名称|API_URL|API_KEY)
# ==========================================
MODELS=(
    "online|QW_coder_7B_instruct_jiekou420|qwen/qwen2.5-7b-instruct|https://api.jiekou.ai/openai|sk_VrZ4jhQDLWUK2lyQj40u5yr6p5Uq1lLpnQ4Cxh_BnUY"
    #"online|QW_coder_7B_instruct_sillcon_1954|Qwen/Qwen2.5-7B-Instruct|https://api.siliconflow.cn/v1|sk-dpgpkzrralqslyeibhmecrxuphylarytbstgsqbdrnoyykbb"
    "online|mis7b_API_420|open-mistral-7b|https://api.agicto.cn/v1|sk-88UT5OLYRw6so66EliV7rNFI4Y9oblR1Lns3dKNjwXABVtk7"
    "online|qwen3-8B_API_420|qwen3-vl-8b-instruct|https://api.agicto.cn/v1|sk-88UT5OLYRw6so66EliV7rNFI4Y9oblR1Lns3dKNjwXABVtk7"


    "online|hunyuan-7b_420|tencent/Hunyuan-MT-7B|https://api.siliconflow.cn/v1|sk-dpgpkzrralqslyeibhmecrxuphylarytbstgsqbdrnoyykbb"

    "online|DSR1-7b_420|deepseek-ai/DeepSeek-R1-Distill-Qwen-7B|https://api.siliconflow.cn/v1|sk-dpgpkzrralqslyeibhmecrxuphylarytbstgsqbdrnoyykbb"

     "online|internlm2.5_420|internlm/internlm2_5-7b-chat|https://api.siliconflow.cn/v1|sk-dpgpkzrralqslyeibhmecrxuphylarytbstgsqbdrnoyykbb"
   
)

# ==========================================
# 3. 并行执行函数
# ==========================================
run_model() {
    local config="$1"
    local MODE MODEL_NAME MODEL_ARG API_URL API_KEY

    IFS='|' read -r MODE MODEL_NAME MODEL_ARG API_URL API_KEY <<< "${config}"

    log "================================================="
    log "🚀 启动并行测试: [${MODEL_NAME}]"
    log "================================================="

    local OUT_DIR="${BASE_RESULT_DIR}/${MODEL_NAME}"

    local CMD=(
        python "${PYTHON_SCRIPT}"
        --mode "${MODE}"
        --output_path "${OUT_DIR}"
        --introductory "${NUM_INTRO}"
        --interview "${NUM_INTERVIEW}"
        --competition "${NUM_COMP}"
    )

    # Online 模式参数
    if [[ "${MODE}" == "online" ]]; then
        log "执行 Online 推理，模型: ${MODEL_ARG}"
        CMD+=(--online_model "${MODEL_ARG}")

        [[ -n "${API_URL}" ]] && CMD+=(--api_url "${API_URL}")
        [[ -n "${API_KEY}" ]] && CMD+=(--api_key "${API_KEY}")
    fi

    # 执行命令
    "${CMD[@]}"

    log "✅ [${MODEL_NAME}] 测试完成"
    echo "--------------------------------------------------"
}

# ==========================================
# 4. 主程序 - 并行启动
# ==========================================
log "开始并行运行所有模型测试...（共 ${#MODELS[@]} 个任务）"

PIDS=()

for config in "${MODELS[@]}"; do
    run_model "${config}" &
    PIDS+=($!)
    # 适当间隔启动，避免同时请求过多
    sleep 2
done

log "所有 ${#MODELS[@]} 个模型已后台启动，等待全部完成..."

# 等待所有子进程结束
for pid in "${PIDS[@]}"; do
    wait "${pid}" || log "⚠️  警告: 进程 ${pid} 异常退出"
done

log "🎉 所有配置并行运行完毕！"