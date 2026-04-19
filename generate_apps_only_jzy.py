import os
import json
import re
import argparse
from tqdm import tqdm
from datasets import load_dataset
from openai import OpenAI

# ==========================================
# 1. 统一 API 配置
# ==========================================
API_KEY = "sk_VrZ4jhQDLWUK2lyQj40u5yr6p5Uq1lLpnQ4Cxh_BnUY"
BASE_URL = "https://api.jiekou.ai/openai"
SAVE_DIR = "/home/wangbn/code_clean"

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# APPS 专用 System Prompt
SYSTEM_PROMPT = r"""
You are an expert Python programmer. Solve the following programming problem.
1. Wrap your core logic into a function or clear script structure.
2. Read from standard input (sys.stdin) as required by the problem.
3. Output ONLY the raw Python code. Do NOT wrap in markdown blocks (```). No explanations.
"""

def generate_apps(model_name, levels, num_problems, k):
    """
    针对不同难度级别生成 APPS 代码，并保存为 .jsonl 格式
    """
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)

    for level in levels:
        print(f"\n🌟 正在生成级别: {level} | 模型: {model_name}")
        
        # 加载 APPS 数据集对应级别
        try:
            dataset = load_dataset("codeparrot/apps", level, split="test", trust_remote_code=True)
        except Exception as e:
            print(f"数据集 {level} 加载失败: {e}")
            continue

        # 修改后缀为 .jsonl
        save_path = os.path.join(SAVE_DIR, f"{model_name}_{level}_apps_generations.jsonl")
        
        # 限制题目数量
        max_idx = min(len(dataset), num_problems)

        # 以 'w' 模式打开，确保每次运行是新的开始；如果想断点续传可以改用 'a'
        with open(save_path, "w", encoding="utf-8") as f:
            for i in tqdm(range(max_idx), desc=f"Progress ({level})"):
                item = dataset[i]
                prob_id = str(i)
                question = item["question"]
                
                codes = []
                for _ in range(k):
                    try:
                        resp = client.chat.completions.create(
                            model=model_name,
                            messages=[
                                {"role": "system", "content": SYSTEM_PROMPT},
                                {"role": "user", "content": question}
                            ],
                            temperature=0.7,
                            max_tokens=2048
                        )
                        content = resp.choices[0].message.content
                        
                        # 清理可能存在的 Markdown 标签
                        code = re.sub(r"```[pP]ython\s*|```", "", content).strip()
                        codes.append(code)
                    except Exception as e:
                        # 如果报错（如余额不足），存入空字符串并打印错误
                        print(f"\n[API 错误] 题目 {i}: {e}")
                        codes.append("")

                # 构建 JSONL 的一行数据：{"task_id": "0", "codes": ["...", "..."]}
                line_data = {
                    "task_id": prob_id,
                    "codes": codes
                }
                
                # 核心改动：即时写入一行并刷新缓存
                f.write(json.dumps(line_data, ensure_ascii=False) + "\n")
                f.flush() 

        print(f"✅ {level} 级别生成完毕，保存至: {save_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=[
        "gemini-3.1-pro-preview", 
        "claude-sonnct-4-6", 
        "deepseek-v3.1"
    ])
    parser.add_argument("--levels", nargs="+", default=['introductory', 'interview', 'competition'])
    parser.add_argument("--num", type=int, default=10)
    parser.add_argument("--k", type=int, default=5)
    
    args = parser.parse_args()

    for model in args.models:
        generate_apps(model, args.levels, args.num, args.k)

    print("\n" + "="*50)
    print(f"所有任务已完成！JSONL 文件已存入 {SAVE_DIR}")
    print("="*50)