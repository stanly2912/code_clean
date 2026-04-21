import os
import json
import re
import argparse
import sys
import time
import subprocess
import tempfile

# --- 环境配置 ---
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from openai import OpenAI
from tqdm import tqdm
from datasets import load_dataset

try:
    from radon.complexity import cc_visit
except ImportError:
    print("请安装 radon 库: pip install radon")
    exit()

# --- API 配置 ---
API_KEY = "sk_VrZ4jhQDLWUK2lyQj40u5yr6p5Uq1lLpnQ4Cxh_BnUY" 
BASE_URL = "https://api.jiekou.ai/openai/v1"
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

SYSTEM_PROMPT = r"""
You are an expert Python programmer. Solve the following programming problem.
1. Provide a clean, efficient, and correct Python solution.
2. Include necessary imports and read from standard input.
3. Output ONLY the code, no markdown blocks (```), no explanations.
"""

def calculate_metrics(code):
    """统计 Rows, CC, Args"""
    if not code.strip(): return 0, 1, 0
    lines = [l for l in code.split('\n') if l.strip() and not l.strip().startswith('#')]
    rows = len(lines)
    cc_total, arg_counts = 0, []
    try:
        blocks = cc_visit(code)
        for block in blocks:
            cc_total += block.complexity
            if hasattr(block, 'args'): arg_counts.append(len(block.args))
    except:
        cc_total = code.count('if ') + code.count('for ') + code.count('while ') + 1
    avg_args = sum(arg_counts) / len(arg_counts) if arg_counts else 0
    return rows, cc_total, avg_args

def run_test(code, test_cases):
    """
    参考 eval_correct.sh 逻辑：针对 APPS 的输入输出进行本地校验
    返回: True (通过所有测试用例), False (未通过)
    """
    if not test_cases: return False
    try:
        inputs_outputs = json.loads(test_cases)
        inputs = inputs_outputs.get("inputs", [])
        outputs = inputs_outputs.get("outputs", [])
    except:
        return False

    with tempfile.NamedTemporaryFile(suffix='.py', delete=False, mode='w') as f:
        f.write(code)
        temp_file = f.name

    passed = True
    try:
        # 只测试前几个用例以节省时间
        for i in range(min(len(inputs), 5)):
            try:
                process = subprocess.run(
                    [sys.executable, temp_file],
                    input=inputs[i],
                    capture_output=True,
                    text=True,
                    timeout=3 # 针对死循环的硬超时
                )
                actual_output = process.stdout.strip()
                expected_output = outputs[i].strip()
                if actual_output != expected_output:
                    passed = False
                    break
            except Exception:
                passed = False
                break
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)
    
    return passed

def get_gpt4_response(problem_description):
    for i in range(5):
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": SYSTEM_PROMPT},
                          {"role": "user", "content": f"Problem:\n{problem_description}\n\nSolution:"}],
                temperature=0.1,
            )
            return response.choices[0].message.content
        except:
            time.sleep(2 ** i)
    return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--level", type=str, choices=['introductory', 'interview', 'competition'], default='introductory')
    parser.add_argument("--num_samples", type=int, default=50)
    args = parser.parse_args()

    print(f"正在加载 APPS ({args.level})...")
    dataset = load_dataset("codeparrot/apps", args.level, split="test", trust_remote_code=True)
    
    output_file = f"gpt4o_apps_{args.level}_full_results.jsonl"
    all_res = []

    print(f"开始评测 {args.num_samples} 个样本 (含 Pass@1)...")
    with open(output_file, "w", encoding="utf-8") as f:
        for i in tqdm(range(min(len(dataset), args.num_samples))):
            item = dataset[i]
            description = item.get("question", "")
            test_cases = item.get("input_output", "")
            
            completion = get_gpt4_response(description)
            if completion is None: break

            code = re.sub(r"```python\s*", "", completion)
            code = re.sub(r"```\s*", "", code).strip()
            
            # 计算静态指标
            rows, cc, n_args = calculate_metrics(code)
            
            # 计算 Pass@1 (动态执行测试用例)
            is_correct = run_test(code, test_cases)
            
            res_entry = {
                "task_id": f"APPS/{args.level}/{i}",
                "rows": rows, "cc": cc, "args": n_args,
                "pass_at_1": 1 if is_correct else 0
            }
            
            all_res.append(res_entry)
            f.write(json.dumps(res_entry) + "\n")
            f.flush()

    if all_res:
        count = len(all_res)
        p1 = sum(m['pass_at_1'] for m in all_res) / count
        print(f"\n--- {args.level.upper()} 结果汇总 ---")
        print(f"Pass@1: {p1*100:.2f}%")
        print(f"平均 Rows: {sum(m['rows'] for m in all_res)/count:.2f}")
        print(f"平均 CC: {sum(m['cc'] for m in all_res)/count:.2f}")
        print(f"平均 Args: {sum(m['args'] for m in all_res)/count:.2f}")

if __name__ == "__main__":
    main()