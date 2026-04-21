#!/usr/bin/env bash
set -euo pipefail

files=(
    /home/wangbn/infer_results_hx/APPS_results/mis7b_API_420/online/introductory_pass5.jsonl
#    /home/wangbn/infer_results_hx/APPS_results/QW_coder_7B_instruct_jiekou420/online/introductory_pass5.jsonl
 #/home/wangbn/infer_results_hx/APPS_results/QWcode25_MAS/MAS/interview_pass5.jsonl
 #   /home/wangbn/infer_results_hx/APPS_results/QWcode25_MAS/MAS/introductory_pass5.jsonl
 #   /home/wangbn/infer_results_hx/APPS_results/QWcode25_MAS/MAS/competition_pass5.jsonl


#/home/wangbn/infer_results_hx/APPS_results/QWcode25_MAS/MAS/introductory_pass5.jsonl
    #/home/wangbn/infer_results_hx/APPS_results/QW_coder_7B_instruct/local/competition_pass5.jsonl
    #/home/wangbn/infer_results_hx/APPS_results/QW_coder_7B_Base/local/competition_pass5.jsonl
                
    
    #"/home/wangbn/infer_results_hx/APPS_results/deepseek-coder-6.7b-instruct/introductory_pass5.jsonl"

    #"/home/wangbn/infer_results_hx/APPS_results/dolphin-2.6-mistral-7b-dpo/competition_pass5.jsonl"
    #"/home/wangbn/infer_results_hx/APPS_results/dolphin-2.6-mistral-7b-dpo/interview_pass5.jsonl"
    #"/home/wangbn/infer_results_hx/APPS_results/dolphin-2.6-mistral-7b-dpo/introductory_pass5.jsonl"

    #"/home/wangbn/infer_results_hx/APPS_results/hunyuan-7b/online/competition_pass5.jsonl"
    #"/home/wangbn/infer_results_hx/APPS_results/hunyuan-7b/online/interview_pass5.jsonl"
    #"/home/wangbn/infer_results_hx/APPS_results/hunyuan-7b/online/introductory_pass5.jsonl"

   # "/home/wangbn/infer_results_hx/APPS_results/mis7b_API/online/competition_pass5.jsonl"
   # "/home/wangbn/infer_results_hx/APPS_results/mis7b_API/online/interview_pass5.jsonl"
  # "/home/wangbn/infer_results_hx/APPS_results/mis7b_API/online/introductory_pass5.jsonl"

  
  #"/home/wangbn/infer_results_hx/APPS_results/QW_coder_7B_Base/local/competition_pass5.jsonl"
  #"/home/wangbn/infer_results_hx/APPS_results/QW_coder_7B_Base/local/interview_pass5.jsonl"
  #"/home/wangbn/infer_results_hx/APPS_results/QW_coder_7B_Base/local/introductory_pass5.jsonl"

  #  "/home/wangbn/infer_results_hx/APPS_results/qwen3-8B_API/online/competition_pass5.jsonl"
# "/home/wangbn/infer_results_hx/APPS_results/qwen3-8B_API/online/interview_pass5.jsonl"
  #  "/home/wangbn/infer_results_hx/APPS_results/qwen3-8B_API/online/introductory_pass5.jsonl"
  
  # "/home/wangbn/infer_results_hx/APPS_results/hunyuan-7b/online/competition_pass5.jsonl"
  # "/home/wangbn/infer_results_hx/APPS_results/hunyuan-7b/online/interview_pass5.jsonl"
  # "/home/wangbn/infer_results_hx/APPS_results/hunyuan-7b/online/introductory_pass5.jsonl"

  #"/home/wangbn/infer_results_hx/APPS_results/QW_coder_7B_Base419/local/introductory_pass5.jsonl"
  #"/home/wangbn/infer_results_hx/APPS_results/QW_coder_7B_Base419/local/interview_pass5.jsonl"
  #"/home/wangbn/infer_results_hx/APPS_results/QW_coder_7B_Base419/local/competition_pass5.jsonl"

#"/home/wangbn/infer_results_hx/APPS_results/mis7b_API419/online/introductory_pass5.jsonl"
#"/home/wangbn/infer_results_hx/APPS_results/mis7b_API419/online/competition_pass5.jsonl"
#"/home/wangbn/infer_results_hx/APPS_results/mis7b_API419/online/interview_pass5.jsonl"

#"/home/wangbn/infer_results_hx/APPS_results/qwen3-8B_API419/online/introductory_pass5.jsonl"
#"/home/wangbn/infer_results_hx/APPS_results/qwen3-8B_API419/online/interview_pass5.jsonl"
#"/home/wangbn/infer_results_hx/APPS_results/qwen3-8B_API419/online/competition_pass5.jsonl"


    #"/home/wangbn/infer_results_hx/APPS_results/QW_coder_7B_Base/local/competition_pass5.jsonl"
    #"/home/wangbn/infer_results_hx/APPS_results/QW_coder_7B_Base/local/interview_pass5.jsonl"
    #"/home/wangbn/infer_results_hx/APPS_results/QW_coder_7B_Base/local/introductory_pass5.jsonl"

   #"/home/wangbn/infer_results_hx/APPS_results/deepseek-coder-6.7b-instruct/local/competition_pass5.jsonl"
   #"/home/wangbn/infer_results_hx/APPS_results/deepseek-coder-6.7b-instruct/local/interview_pass5.jsonl"
   #"/home/wangbn/infer_results_hx/APPS_results/deepseek-coder-6.7b-instruct/local/introductory_pass5.jsonl"

   #"/home/wangbn/infer_results_hx/APPS_results/mis7b_API/online/introductory_pass5.jsonl"
   #"/home/wangbn/infer_results_hx/APPS_results/mis7b_API/online/interview_pass5.jsonl"
   #"/home/wangbn/infer_results_hx/APPS_results/mis7b_API/online/competition_pass5.jsonl"

   #"/home/wangbn/infer_results_hx/APPS_results/qwen3-8B_API/online/interview_pass5.jsonl"
   #"/home/wangbn/infer_results_hx/APPS_results/qwen3-8B_API/online/introductory_pass5.jsonl"
   #"/home/wangbn/infer_results_hx/APPS_results/qwen3-8B_API/online/competition_pass5.jsonl"

    #"/home/wangbn/infer_results_hx/APPS_results/hunyuan-7b/online/competition_pass5.jsonl"
    #"/home/wangbn/infer_results_hx/APPS_results/hunyuan-7b/online/interview_pass5.jsonl"
    #"/home/wangbn/infer_results_hx/APPS_results/hunyuan-7b/online/introductory_pass5.jsonl"

    #"/home/wangbn/infer_results_hx/APPS_results/dolphin-2.6-mistral-7b-dpo/local/competition_pass5.jsonl"
    #"/home/wangbn/infer_results_hx/APPS_results/dolphin-2.6-mistral-7b-dpo/local/interview_pass5.jsonl"
    #"/home/wangbn/infer_results_hx/APPS_results/dolphin-2.6-mistral-7b-dpo/local/introductory_pass5.jsonl"
)


for file_path in "${files[@]}"; do
    echo "-------------start: ${file_path}"

    file_name="$(basename "$file_path")"
    level="${file_name%_pass5.jsonl}"


            last_lines=$(
           python /home/wangbn/code_clean/evalAPPS_hx.py \
        --file "$file_path" \
        --level "$level" 2>&1 | tail -n 10
    )

printf '%s\n' "$last_lines"
    echo "-------------finish: ${file_path}"
done