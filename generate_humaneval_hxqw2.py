import os
import json
import re
from tqdm import tqdm
from datasets import load_dataset
from openai import OpenAI

# ==========================================
# 1. 配置信息
# ==========================================
API_KEY = "sk_VrZ4jhQDLWUK2lyQj40u5yr6p5Uq1lLpnQ4Cxh_BnUY"
BASE_URL = "https://api.jiekou.ai/openai"
# 建议保存为专门的 multi 文件，方便与之前的单次生成区分
SAVE_PATH = "/home/wangbn/code_clean/humanevalpass5/qwen2.5-8b-base.jsonl"

# 评测 pass@5 建议每题生成 5 个样本 (n=5)
# 如果你想更准，可以设为 n=10
N_SAMPLES = 5 

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

SYSTEM_PROMPT = r"""
You are an expert Python programmer. I will give you a function signature and a docstring.
Please provide the COMPLETE and WORKING Python implementation, including the original imports, function signature, and docstring.
Output ONLY the raw Python code. Do NOT wrap the code in markdown blocks (e.g., no ```python). Do NOT add explanations.
"""

def generate_multi_samples(model_name="qwen/qwen3-32b-fp8"):
    print(f"正在加载 HumanEval 数据集...")
    dataset = load_dataset("openai_humaneval", split="test")
    
    results_list = []
    os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)

    print(f"开始生成 (每题 {N_SAMPLES} 个样本)，使用模型: {model_name}...")

    # 遍历 164 道题
    for item in tqdm(dataset, desc="Total Progress"):
        task_id = item["task_id"]
        prompt = item["prompt"]
        
        # 每道题重复生成 n 次
        for i in range(N_SAMPLES):
            try:
                resp = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    # 注意：测 pass@k 时必须调高 temperature (建议 0.6-0.8)
                    # 否则 5 次生成的代码可能一模一样，那就没意义了
                    temperature=0.8, 
                    max_tokens=1024
                )
                raw_code = resp.choices[0].message.content
                
                # 清理代码
                code = re.sub(r"^```[pP]ython\s*", "", raw_code)
                code = re.sub(r"```\s*$", "", code)
                code = code.strip()
                
                if not code.startswith("def ") and not code.startswith("import "):
                    code = prompt + "\n" + code
                    
                # 存入列表
                results_list.append({
                    "task_id": task_id,
                    "completion": code
                })

            except Exception as e:
                print(f"\n[API 错误] {task_id} Sample {i}: {e}")
                results_list.append({"task_id": task_id, "completion": ""})

    # ==========================================
    # 2. 保存为 JSONL 格式（每行一个 JSON 对象）
    # ==========================================
    print(f"\n正在保存结果到: {SAVE_PATH}")
    with open(SAVE_PATH, 'w', encoding='utf-8') as f:
        for entry in results_list:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
            
    print(f"🎉 生成完毕！总计样本数: {len(results_list)}")
    print(f"请确保 eval_pass5.sh 中的路径指向: {SAVE_PATH}")

if __name__ == "__main__":
    generate_multi_samples(model_name="qwen/qwen3-32b-fp8")