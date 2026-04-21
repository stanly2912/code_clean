#!/usr/bin/env sh
set -eu

tmp_file="/home/wangbn/code_clean/tmp.txt"
harness_dir="/home/wangbn/llm_code_robustness/llm_code_robustness/bigcode-evaluation-harness"

#qwen2.5-coder-7b-instruct
#for model in qwen2.5-coder-7b-base deepseek-coder-v2-lite-base codellama-7b-base llama3.1-8b-base qwen2.5-7b-base; do
for model in qwen2.5-coder-7b-base; do
    {
        printf 'start a model: %s\n' "$model"
    } 

    cp \
        "$harness_dir/result/$model/generations/humaneval_generate_python_robust_no_change/generations.json" \
        "$tmp_file"

    cd /home/wangbn/code_clean/parser_code/ || exit 1

    python ./cut.py \
        --input_path "$tmp_file" \
        --output_path "/home/wangbn/code_clean/human-eval/human_eval/tmp.jsonl"

    python /home/wangbn/code_clean/calc_atts.py --codes_path "$tmp_file"

    {
        cat "$harness_dir/result/$model/evaluation_results/humaneval_generate_python_robust_no_change/evaluation_results.json"
        printf '\n\n%s\n\n' '-------------------------finish a model-------------------------'
    }
done