#!/bin/bash
set -euo pipefail

# 结果输出文件（建议区分开，以免覆盖 pass@1 的日志）
OUTPUT_PATH="/home/wangbn/infer_results_hx/eval_Human/7Human2_416.log"

echo "start evaluation"

# 写入基本信息到日志
echo "===== Pass@5 Evaluation Started at $(date) =====" >> "$OUTPUT_PATH"
echo "OUTPUT_PATH=$OUTPUT_PATH" >> "$OUTPUT_PATH"

# ====================== 批量评测配置 ======================
# 格式： "BENCH|CODES_PATH"
# 注意：此处的 CODES_PATH 必须是你生成的包含多个样本（n>=5）的 .jsonl 文件
codes=(
    "human|/home/wangbn/infer_results_hx/Human_results/DS_7B_Base/local/humaneval_pass5.jsonl"
)

for entry in "${codes[@]}"; do
    BENCH="${entry%%|*}"
    CODES_PATH="${entry#*|}"

    echo "========================================" >> "$OUTPUT_PATH"
    echo "Starting evaluation: BENCH=$BENCH, CODES_PATH=$CODES_PATH" >> "$OUTPUT_PATH"
    echo "========================================" >> "$OUTPUT_PATH"

    # ====================== 评测逻辑 ======================
    if [ "$BENCH" = "human" ]; then

        cd /home/wangbn/code_clean/human-eval/human_eval || exit 1
        source ~/miniconda3/etc/profile.d/conda.sh
        conda activate base
        
        echo "Running HumanEval with k=1,5..." >> "$OUTPUT_PATH"
        
        # 【核心修改点】添加了 --k 1,5 参数
        # 这会让评测脚本统计并计算 pass@1 和 pass@5 的得分
        python ./evaluate_functional_correctness.py "$CODES_PATH" --k 1,5 >> "$OUTPUT_PATH" 2>&1

    else
        echo "Unsupported BENCH for pass@k: $BENCH" >> "$OUTPUT_PATH"
    fi
done

echo "Evaluation finished. Check results in $OUTPUT_PATH"