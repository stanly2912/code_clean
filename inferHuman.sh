#!/bin/bash

# 定义模型的范围,DS00,

#for model in DS00,QW00,LM00; do
for model in DS7B; do
#for model in 00; do
    # 进入LLaMA-Factory目录
    cd /home/wangbn/LLaMA-Factory || exit

    # 【核心：启动前杀掉 6000 端口，防止端口冲突】
    fuser -k -9 6000/tcp 2>/dev/null

    # 启动API (端口改为 6000)
    API_PORT=6000 CUDA_VISIBLE_DEVICES=0 nohup llamafactory-cli api /home/wangbn/code_clean/infer_scripts/infer${model}.yaml > api6000.log 2>&1 &
    
    # 记录进程号，并强制等待 60 秒
    API_PID=$! 
    echo "正在等待模型 ${model} 加载进显存 (60秒)..."
    sleep 60   


    # 进入 Human 评估目录
    cd ~/code_clean/human-eval/human_eval || exit

    # 生成代码 (改为 SPOC 的推理命令)
    python ./infer.py --output ./codes${model}.json

    # 做完题杀掉这个模型，释放 6000 端口
    echo "评测完毕，清理后台大模型释放资源..."
    kill -9 $API_PID 
    sleep 5
done












