#!/usr/bin/env bash
set -eu

files=(
    "/home/wangbn/code_clean/human-eval/human_eval/cleancodesQWcode00_good.jsonl"
    "/home/wangbn/code_clean/human-eval/human_eval/codesQWcoder.jsonl"
)



cd /home/wangbn/code_clean/parser_code/ || exit 1

for file_path in "${files[@]}"; do
    echo "-------------start"


    printf 'calc atts of: %s\n' "$file_path"
    python /home/wangbn/code_clean/calc_atts.py --codes_path "$file_path"




    

    cd /home/wangbn/code_clean/human-eval/human_eval || exit 1
    source ~/miniconda3/etc/profile.d/conda.sh
    conda activate base
    python ./evaluate_functional_correctness.py "$file_path"


    echo "-------------finish"
done