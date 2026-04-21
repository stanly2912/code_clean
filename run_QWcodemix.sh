#!/bin/bash
set -e 

cd /home/wangbn/LLaMA-Factory

echo "🚀 1/3: 开始训练 Coder 版本的 mix25 模型..."
CUDA_VISIBLE_DEVICES=0 llamafactory-cli train /home/wangbn/code_clean/sft_QWcodemix25.yaml

echo "🚀 2/3: 开始训练 Coder 版本的 mix50 模型..."
CUDA_VISIBLE_DEVICES=0 llamafactory-cli train /home/wangbn/code_clean/sft_QWcodemix50.yaml

echo "🚀 3/3: 开始训练 Coder 版本的 mix75 模型..."
CUDA_VISIBLE_DEVICES=0 llamafactory-cli train /home/wangbn/code_clean/sft_QWcodemix75.yaml

echo "🎉 所有 Qwen-Coder-Instruct 模型的微调全部完成！"