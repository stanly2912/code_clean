#!/usr/bin/env bash
set -eu

files=(
    #"/home/wangbn/code_clean/human-eval/human_eval/cleancodesQWcode00_good.jsonl"


    #"/home/wangbn/llm_code_robustness/llm_code_robustness/bigcode-evaluation-harness/result/
    #deepseek-coder-v2-lite-base/generations/humaneval_generate_python_robust_no_change/generations.json"
   # "/home/wangbn/llm_code_robustness/llm_code_robustness/bigcode-evaluation-harness/result/
   # qwen2.5-7b-base/generations/humaneval_generate_python_robust_no_change/generations.json"
   #/home/wangbn/apps_clean_codellma/competition.jsonl
    /home/wangbn/code_clean/gpt-4o_eval_generations.json
    #"/home/wangbn/code_clean/human-eval/human_eval/codesQWcoder.jsonl"

    
   #"/home/wangbn/code_clean/apps-main/eval/generate_bad/0-10_codes.json"
   # "/home/wangbn/code_clean/apps-main/eval/generateQWcode/0-10_codes.json"
   # "/home/wangbn/code_clean/apps-main/eval/generateQWcode_clean/0-10_codes.json"
)

for model in \
    qwen2.5-coder-7b-base \
    deepseek-coder-v2-lite-base \
    codellama-7b-base \
    llama3.1-8b-base \
    qwen2.5-7b-base
do
    break
    files+=("/home/wangbn/llm_code_robustness/llm_code_robustness/bigcode-evaluation-harness/result/$model/generations/humaneval_generate_python_robust_no_change/generations.json")
done

cd /home/wangbn/code_clean/parser_code/ || exit 1

for file_path in "${files[@]}"; do
    echo "-------------start"
    printf 'calc atts of: %s\n' "$file_path"
    python /home/wangbn/code_clean/calc_atts.py --codes_path "$file_path"
    echo "-------------finish"
done