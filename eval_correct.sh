#!/bin/bash
set -euo pipefail

# 指定评测基准（仅作为默认值，批量模式下会以数组为准）
# 可选值：
#   - "human" : 使用 HumanEval 的评测脚本
#   - "spoc"  : 使用 SPOC 的评测脚本
#   - "apps"  : 使用 APPS 的评测脚本

# 单个评测路径（批量模式下此变量不再使用，仅作参考）
# CODES_PATH="/home/wangbn/code_clean/apps-main/eval/generate_bad/"

# 结果输出文件
OUTPUT_PATH="/home/wangbn/code_clean/res_correct_6.log"

echo "start"

# 先写入基本信息到日志
echo "===== Batch Evaluation Started at $(date) =====" >> "$OUTPUT_PATH"
echo "OUTPUT_PATH=$OUTPUT_PATH" >> "$OUTPUT_PATH"


# ====================== 批量评测配置 ======================
# 格式： "BENCH|CODES_PATH"
# 支持同时评测多个不同基准和不同路径
codes=(
    #"apps|/home/wangbn/code_clean/apps-main/eval/generate_bad/"
    #"apps|/home/wangbn/code_clean/apps-main/eval/generateQWcode/"
    #"apps|/home/wangbn/code_clean/apps-main/eval/generateQWcode_bad/"
    #"apps|/home/wangbn/code_clean/apps-main/eval/generateQWcode_good/"
    #"human|/home/wangbn/code_clean/human-eval/human_eval/cleanerQWcode25.jsonl"
    # 在这里添加更多评测任务，例如：
    # "apps|/home/wangbn/code_clean/apps-main/eval/generate25/0-10_codes.json"
    # "human|/home/wangbn/code_clean/human-eval/human_eval/best.jsonl"
    #"human|/home/wangbn/code_clean/human-eval/human_eval/tmp_QWcode25.jsonl"
     "spoc|/home/wangbn/code_clean/infer_results_jzy/gpt-4.1_API/online/spoc_test_pass5.jsonl"
   #"apps|/home/wangbn/apps_clean_code/Qwen2.5-Coder-7B-Instruct/competition_packed.jsonl"
    #  "human|/home/wangbn/code_clean/gpt4o_human_eval_result_fixed.jsonl"
    #  "apps|/home/wangbn/code_clean/gpt4o_human_eval_result_fixed.jsonl"
    #   "/home/wangbn/apps_our/MAS/competition_pass5.jsonl"
#/home/wangbn/code_clean/human-eval/human_eval/good_.jsonl_results.jsonl
#       /home/wangbn/apps_our/MAS/introductory_pass5.jsonl 
    
)

echo "Total tasks to evaluate: ${#codes[@]}" >> "$OUTPUT_PATH"
echo "========================================" >> "$OUTPUT_PATH"

# 开始批量执行
for item in "${codes[@]}"; do
    # 解析 BENCH 和 CODES_PATH
    BENCH="${item%%|*}"
    CODES_PATH="${item#*|}"

    echo "========================================" >> "$OUTPUT_PATH"
    echo "Starting evaluation: BENCH=$BENCH, CODES_PATH=$CODES_PATH" >> "$OUTPUT_PATH"
    echo "========================================" >> "$OUTPUT_PATH"

    # ====================== 评测逻辑 ======================
    if [ "$BENCH" = "human" ]; then

        cd /home/wangbn/code_clean/human-eval/human_eval || exit 1
        source ~/miniconda3/etc/profile.d/conda.sh
        conda activate base
        echo "Running HumanEval..." >> "$OUTPUT_PATH"
        python ./evaluate_functional_correctness.py "$CODES_PATH" >> "$OUTPUT_PATH" 2>&1

    elif [ "$BENCH" = "spoc" ]; then

        source ~/miniconda3/etc/profile.d/conda.sh
        conda activate base

        cd /home/wangbn/code_clean/spoc || exit 1

        echo "Running SPOC..." >> "$OUTPUT_PATH"
        python ./e.py "$CODES_PATH" --output "$OUTPUT_PATH" >> "$OUTPUT_PATH" 2>&1

    elif [ "$BENCH" = "apps" ]; then

        cd /home/wangbn/code_clean/apps-main/eval || exit 1

        echo "Running APPS..." >> "$OUTPUT_PATH"

        source ~/miniconda3/etc/profile.d/conda.sh
        conda activate py310

        python test_one_solution.py --save "$CODES_PATH" -s 0 -e 10 >> "$OUTPUT_PATH" 2>&1

    else
        echo "Unsupported BENCH: $BENCH" >&2
        echo "Unsupported BENCH: $BENCH" >> "$OUTPUT_PATH"
        # continue  # 继续执行其他任务，而不是直接退出
    fi

    echo "Completed: BENCH=$BENCH, CODES_PATH=$CODES_PATH" >> "$OUTPUT_PATH"
    echo "" >> "$OUTPUT_PATH"
done

echo "===== All batch evaluations finished at $(date) =====" >> "$OUTPUT_PATH"
echo "Batch evaluation completed!"