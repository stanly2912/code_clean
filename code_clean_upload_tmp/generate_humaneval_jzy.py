import os
import json
import re
import sys # 导入 sys 模块
from tqdm import tqdm
from datasets import load_dataset
from openai import OpenAI

# ==========================================
# 1. 配置信息 (保持不变)
# ==========================================
API_KEY = "sk_VrZ4jhQDLWUK2lyQj40u5yr6p5Uq1lLpnQ4Cxh_BnUY"
BASE_URL = "https://api.jiekou.ai/openai"
SAVE_PATH = "/home/wangbn/code_clean/gemini-3.1-pro-preview_multi_generations.jsonl"
N_SAMPLES = 5 

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

SYSTEM_PROMPT = r"""
You are an expert Python programmer. I will give you a function signature and a docstring.
Please provide the COMPLETE and WORKING Python implementation, including the original imports, function signature, and docstring.
Output ONLY the raw Python code. Do NOT wrap the code in markdown blocks (e.g., no ```python). Do NOT add explanations.
"""

def generate_multi_samples(model_name="gemini-3.1-pro-preview"):
    # 使用 flush=True 确保后台日志实时更新
    print(f"正在加载 HumanEval 数据集...", flush=True)
    dataset = load_dataset("openai_humaneval", split="test")
    
    results_list = []
    os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)

    print(f"开始生成 (每题 {N_SAMPLES} 个样本)，使用模型: {model_name}...", flush=True)

    # mininterval=10 可以让进度条每10秒才往日志写一次，避免日志文件被 \r 刷屏
    for item in tqdm(dataset, desc="Total Progress", mininterval=10):
        task_id = item["task_id"]
        prompt = item["prompt"]
        
        for i in range(N_SAMPLES):
            try:
                resp = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.8, 
                    max_tokens=1024
                )
                raw_code = resp.choices[0].message.content
                
                code = re.sub(r"^```[pP]ython\s*", "", raw_code)
                code = re.sub(r"```\s*$", "", code)
                code = code.strip()
                
                if not code.startswith("def ") and not code.startswith("import "):
                    code = prompt + "\n" + code
                    
                results_list.append({
                    "task_id": task_id,
                    "completion": code
                })

            except Exception as e:
                # 错误信息也要实时刷出来
                print(f"\n[API 错误] {task_id} Sample {i}: {e}", flush=True)
                results_list.append({"task_id": task_id, "completion": ""})

    print(f"\n正在保存结果到: {SAVE_PATH}", flush=True)
    with open(SAVE_PATH, 'w', encoding='utf-8') as f:
        for entry in results_list:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
            
    print(f"🎉 生成完毕！总计样本数: {len(results_list)}", flush=True)

if __name__ == "__main__":
    generate_multi_samples(model_name="gemini-3.1-pro-preview")