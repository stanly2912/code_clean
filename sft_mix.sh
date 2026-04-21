#!/bin/bash
set -e 

cd /home/wangbn/LLaMA-Factory

# 25% 已经跑完了，我们加 # 把这行注释掉
CUDA_VISIBLE_DEVICES=1 llamafactory-cli train /home/wangbn/code_clean/sft_mix25.yaml

echo "🚀 开始训练 混合双打 50% (py+cpp) 模型..."
CUDA_VISIBLE_DEVICES=1 llamafactory-cli train /home/wangbn/code_clean/sft_mix50.yaml

echo "🚀 开始训练 混合双打 75% (py+cpp) 模型..."
CUDA_VISIBLE_DEVICES=1 llamafactory-cli train /home/wangbn/code_clean/sft_mix75.yaml

echo "🎉 所有混合模型训练完毕！"