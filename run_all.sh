#!/bin/bash
set -e 

cd /home/wangbn/LLaMA-Factory

# 这里的 CUDA_VISIBLE_DEVICES=0 就是我们的“眼罩”
# 它会强制 LLaMA-Factory 只在 GPU 0 上运行，绝对不会去干扰 GPU 1 上的学长代码！

echo " 开始训练 py25 模型..."
CUDA_VISIBLE_DEVICES=0 llamafactory-cli train /home/wangbn/code_clean/sft_py25.yaml

echo " 开始训练 py50 模型..."
CUDA_VISIBLE_DEVICES=0 llamafactory-cli train /home/wangbn/code_clean/sft_py50.yaml

echo " 开始训练 py75 模型..."
CUDA_VISIBLE_DEVICES=0 llamafactory-cli train /home/wangbn/code_clean/sft_py75.yaml

echo " 所有模型训练完毕！"