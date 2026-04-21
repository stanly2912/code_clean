cd /home/wangbn/LLaMA-Factory

python scripts/vllm_infer.py \
    --model_name_or_path /home/wangbn/DS-Qwen3-8B \
    --dataset tmp \
    --template deepseek \
    --adapter_name_or_path /home/wangbn/code_clean/sft_java25\
    --save_name /home/wangbn/code_clean/output.jsonl \



python scripts/vllm_infer.py \
    --model_name_or_path /home/wangbn/DS-Qwen3-8B \
    --dataset tmp \
    --template deepseek \
    --save_name /home/wangbn/code_clean/output.jsonl \
    --max_model_len 8192

llamafactory-cli chat /home/wangbn/code_clean/infer_scripts/inferQWcode25.yaml


API_PORT=7000 CUDA_VISIBLE_DEVICES=0 llamafactory-cli api /home/wangbn/code_clean/infer.yaml


API_PORT=7000 CUDA_VISIBLE_DEVICES=0  nohup llamafactory-cli api /home/wangbn/code_clean/infer.yaml > api7000.log 2>&1 &

API_PORT=8088 CUDA_VISIBLE_DEVICES=0   llamafactory-cli api /home/wangbn/code_clean/infer25.yaml 
python /home/wangbn/code_clean/infer.py
python /home/wangbn/code_clean/infer_swe.py

cd /home/wangbn/LLaMA-Factory

python scripts/vllm_infer.py \
    --model_name_or_path /home/wangbn/DS-Qwen3-8B \
    --dataset tmp \
    --template deepseek \
    --adapter_name_or_path /home/wangbn/code_clean/sft_java25\
    --save_name /home/wangbn/code_clean/output.jsonl \



python scripts/vllm_infer.py \
    --model_name_or_path /home/wangbn/DS-Qwen3-8B \
    --dataset tmp \
    --template deepseek \
    --save_name /home/wangbn/code_clean/output.jsonl \
    --max_model_len 8192

llamafactory-cli chat /home/wangbn/code_clean/infer.yaml


API_PORT=7000 CUDA_VISIBLE_DEVICES=0 llamafactory-cli api /home/wangbn/code_clean/infer.yaml


python /home/wangbn/code_clean/infer.py