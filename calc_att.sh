#!/usr/bin/env bash
set -eu

only_function="1"

files=(
    #"/home/wangbn/code_clean/human-eval/human_eval/codesQWcoder.jsonl"
   # "/home/wangbn/llm_code_robustness/llm_code_robustness/bigcode-evaluation-harness/result/
   # deepseek-coder-v2-lite-base/generations/humaneval_generate_python_robust_no_change/generations.json"
   # "/home/wangbn/llm_code_robustness/llm_code_robustness/bigcode-evaluation-harness/result/
   # qwen2.5-7b-base/generations/humaneval_generate_python_robust_no_change/generations.json"
    #  /home/wangbn/apps_clean_code/Qwen2.5-Coder-7B-Instruct/competition_packed.jsonl
    #"/home/wangbn/code_clean/gpt-4o_eval_generations.json"
   #"/home/wangbn/apps_clean_codellma17/introductory.jsonl"
   #"/home/wangbn/code_clean/human-eval/human_eval/cleanerQWcode25.jsonl"
   #"/home/wangbn/code_clean/gpt4o_table_ready_v2.jsonl"
   #/home/wangbn/code_clean/gpt4o_human_eval_result_fixed.jsonl
   # /home/wangbn/apps_our/MAS/interview_pass5.jsonl
   #"/home/wangbn/code_clean/apps-main/eval/generate_bad/0-10_codes.json"
   # "/home/wangbn/code_clean/apps-main/eval/generateQWcode/0-10_codes.json"
   # "/home/wangbn/code_clean/apps-main/eval/generateQWcode_clean/0-10_codes.json"
#   "/home/wangbn/infer_results_hx/Human_results/mis7b_API/online/humaneval_pass5.jsonl"
#   "/home/wangbn/infer_results_hx/Human_results/qwen3-8B_API/online/humaneval_pass5.jsonl"
#    "/home/wangbn/infer_results_hx/Human_results/dolphin-2.6-mistral-7b-dpo/local/humaneval_pass5.jsonl"
#   "/home/wangbn/infer_results_hx/Human_results/deepseek-coder-6.7b-instruct/local/humaneval_pass5.jsonl"
#   "/home/wangbn/infer_results_hx/Human_results/hunyuan-7b/online/humaneval_pass5.jsonl"
#   "/home/wangbn/infer_results_hx/Human_results/QW_coder_7B_Base/local/humaneval_pass5.jsonl"

   
#/home/wangbn/infer_results_hx/Human_results/solver_old_0418/MAS/humaneval_pass5_eval.jsonl

/home/wangbn/infer_results_hx/APPS_results/QWcode25_MAS/MAS/introductory_pass5.jsonl
/home/wangbn/infer_results_hx/APPS_results/QWcode25_MAS/MAS/interview_pass5.jsonl
/home/wangbn/infer_results_hx/APPS_results/QWcode25_MAS/MAS/competition_pass5.jsonl

#/home/wangbn/infer_results_hx/APPS_results/QW_coder_7B_Base/local/introductory_pass5.jsonl
#/home/wangbn/infer_results_hx/APPS_results/QW_coder_7B_Base/local/interview_pass5.jsonl
#/home/wangbn/infer_results_hx/APPS_results/QW_coder_7B_Base/local/competition_pass5.jsonl


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




tot_results=""

for file_path in "${files[@]}"; do
    echo "-------------start"
    printf 'calc atts of: %s\n' "$file_path"

    last_10_lines=$(
        python /home/wangbn/code_clean/calc_atts.py --codes_path "$file_path" --only_function "$only_function" 2>&1 | tail -n 4
    )

    tot_results+=$'\n-------------start\n'
    tot_results+=$'calc atts of: '"$file_path"$'\n'
    tot_results+="$last_10_lines"
    tot_results+=$'\n-------------finish\n'

    echo "-------------finish"
done

printf '%s\n' "$tot_results"