import os
import json
import time
from tqdm import tqdm
from openai import OpenAI

# ============ 配置 ============
API_KEY = "sk_VrZ4jhQDLWUK2lyQj40u5yr6p5Uq1lLpnQ4Cxh_BnUY"
BASE_URL = "https://api.jiekou.ai/openai/v1"
MODEL = "deepseek/deepseek-ocr-2"

APPS_PATH = "/home/wangbn/APPS/test"
OUTPUT_PATH = "/home/wangbn/apps_pass5_DS"

# 每题生成数量（用于 pass@k）
NUM_SAMPLES = 5

# 划分数量
INTRO_NUM = 10
INTERVIEW_NUM = 30
COMP_NUM = 10

client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL
)

# ============ Prompt ============
def build_prompt(question):
    return f"""You are a competitive programming assistant.
Solve the following problem and output ONLY Python code.

Problem:
{question}

Requirements:
- Only output valid Python code
- No explanation
- No markdown
"""

# ============ 获取编号任务 ============
def load_all_tasks():
    all_ids = os.listdir(APPS_PATH)
    all_ids = [x for x in all_ids if x.isdigit()]
    all_ids = sorted(all_ids, key=lambda x: int(x))
    return all_ids

# ============ 划分 ============
def split_tasks(all_ids):
    intro = all_ids[:INTRO_NUM]
    interview = all_ids[INTRO_NUM:INTRO_NUM + INTERVIEW_NUM]
    competition = all_ids[INTRO_NUM + INTERVIEW_NUM:
                          INTRO_NUM + INTERVIEW_NUM + COMP_NUM]

    return {
        "introductory": intro,
        "interview": interview,
        "competition": competition
    }

# ============ 读取题目 ============
def load_question(task_id):
    path = os.path.join(APPS_PATH, task_id, "question.txt")
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return f.read()

# ============ 清理 ============
def clean_code(code):
    if "```" in code:
        parts = code.split("```")
        if len(parts) >= 2:
            code = parts[-2]
    return code.strip()

# ============ API ============
def generate_code(prompt, max_retries=5):
    for i in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "You are a coding assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,   # 🔥 保证多样性
                top_p=0.95,
                max_tokens=1024
            )
            return clean_code(response.choices[0].message.content)
        except Exception as e:
            print("API error:", e)
            time.sleep(2 ** i)
    return ""

# ============ 主生成 ============
def run_generation():
    all_ids = load_all_tasks()
    split = split_tasks(all_ids)

    for diff, task_ids in split.items():
        print(f"\nProcessing {diff} ({len(task_ids)})...")

        for task_id in tqdm(task_ids):

            # 👉 每个 task 一个文件夹
            task_dir = os.path.join(OUTPUT_PATH, diff, task_id)
            os.makedirs(task_dir, exist_ok=True)

            question = load_question(task_id)
            if question is None:
                continue

            prompt = build_prompt(question)

            generated_codes = set()  # 去重

            for i in range(NUM_SAMPLES):

                save_path = os.path.join(task_dir, f"{i}.json")

                # 断点续跑
                if os.path.exists(save_path):
                    continue

                code = generate_code(prompt)

                # 👉 简单去重（避免5个一样）
                retry = 0
                while code in generated_codes and retry < 3:
                    code = generate_code(prompt)
                    retry += 1

                generated_codes.add(code)

                result = {
                    "task_id": task_id,
                    "completion": code
                }

                with open(save_path, "w") as f:
                    json.dump(result, f)

                time.sleep(1.5)  # 防限流


if __name__ == "__main__":
    run_generation()