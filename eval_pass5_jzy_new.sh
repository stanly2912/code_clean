#!/bin/bash
set -euo pipefail

# 结果输出文件
OUTPUT_PATH="/home/wangbn/code_clean/res_spoc_pass5.log"

echo "start evaluation"

# 写入基本信息到日志
echo "===== SPOC Pass@5 Evaluation Started at $(date) =====" >> "$OUTPUT_PATH"
echo "OUTPUT_PATH=$OUTPUT_PATH" >> "$OUTPUT_PATH"

# ====================== 批量评测配置 ======================
# 格式： "BENCH|CODES_PATH"
codes=(
    "spoc|/home/wangbn/code_clean/infer_results_jzy/gpt-4.1_API/online/spoc_test_pass5_standard.json"
    # 如果还需要跑 HumanEval，可以取消下面这行的注释
    # "human|/home/wangbn/code_clean/human-eval/human_eval/cleancodesQWcode00_good.jsonl"
)

for entry in "${codes[@]}"; do
    BENCH="${entry%%|*}"
    CODES_PATH="${entry#*|}"

    echo "========================================" >> "$OUTPUT_PATH"
    echo "Starting evaluation: BENCH=$BENCH, CODES_PATH=$CODES_PATH" >> "$OUTPUT_PATH"
    echo "========================================" >> "$OUTPUT_PATH"

    # ====================== 评测逻辑 ======================
    if [ "$BENCH" = "human" ]; then
        # HumanEval 逻辑
        cd /home/wangbn/code_clean/human-eval/human_eval || exit 1
        source ~/miniconda3/etc/profile.d/conda.sh
        conda activate base
        
        echo "Running HumanEval with k=1,5..." >> "$OUTPUT_PATH"
        python ./evaluate_functional_correctness.py "$CODES_PATH" --k "1,5" >> "$OUTPUT_PATH" 2>&1

    elif [ "$BENCH" = "spoc" ]; then
        # 【新增】SPOC 评测逻辑
        source ~/miniconda3/etc/profile.d/conda.sh
        conda activate base

        # 切换到第一个脚本中定义的 SPOC 评测目录
        cd /home/wangbn/code_clean/spoc || exit 1

        echo "Running SPOC evaluation..." >> "$OUTPUT_PATH"
        
        # 调用 SPOC 评测脚本
        # 注意：如果 e.py 脚本支持 --k 参数，你可以像 HumanEval 那样加上 --k 1,5
        # 如果不支持，e.py 通常会根据 .jsonl 文件中的样本数量自动计算 pass@k
        python ./e.py "$CODES_PATH" --output "$OUTPUT_PATH" >> "$OUTPUT_PATH" 2>&1

    else
        echo "Unsupported BENCH: $BENCH" >> "$OUTPUT_PATH"
    fi
done

echo "Evaluation finished. Check results in $OUTPUT_PATH"