import os
import json
import re
import argparse
import sys
import subprocess
import tempfile
import ast
import io
import textwrap
import tokenize
from tqdm import tqdm
from datasets import load_dataset
from openai import OpenAI
from radon.complexity import cc_visit

# ==========================================
# 1. 配置信息
# ==========================================
API_KEY = "sk_VrZ4jhQDLWUK2lyQj40u5yr6p5Uq1lLpnQ4Cxh_BnUY"
BASE_URL = "https://api.jiekou.ai/openai"
SAVE_DIR = "/home/wangbn/code_clean"

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

SYSTEM_PROMPT = r"""
You are an expert Python programmer. Solve the following programming problem.
1. Wrap your core logic into a function with descriptive arguments.
2. Read from standard input (sys.stdin) and pass the data to your function.
3. Provide a clean, efficient, and correct Python solution.
4. Output ONLY the code, no markdown blocks (```), no explanations.
"""

# ==========================================
# 2. 统计逻辑 (基于你的 calc_atts.py)
# ==========================================
def calc_py_rows(code):
    """精确计算有效代码行数"""
    if not isinstance(code, str) or not code.strip(): return 0
    code = textwrap.dedent(code)
    ignored_lines = set()
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant):
                start = getattr(node, "lineno", None)
                end = getattr(node, "end_lineno", start)
                if start is not None and end is not None:
                    ignored_lines.update(range(start, end + 1))
    except SyntaxError: pass
    code_lines = set()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(code).readline):
            if tok.type in {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, 
                            tokenize.DEDENT, tokenize.ENDMARKER, tokenize.ENCODING}: continue
            if tok.start[0] in ignored_lines: continue
            code_lines.add(tok.start[0])
    except:
        for lineno, line in enumerate(code.splitlines(), 1):
            if line.strip() and not line.strip().startswith("#"): code_lines.add(lineno)
    return len(code_lines)

def calculate_metrics(code):
    rows = calc_py_rows(code)
    try:
        results = cc_visit(code)
        cc = max((r.complexity for r in results), default=1)
    except: cc = 1
    args_num = 0
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                args_num = max(args_num, len(node.args.args))
    except: args_num = 0
    return rows, cc, args_num

# ==========================================
# 3. 评测沙箱
# ==========================================
def run_test_cases(code, test_cases_json):
    if not test_cases_json: return False
    try:
        io_data = json.loads(test_cases_json)
        inputs, outputs = io_data.get("inputs", []), io_data.get("outputs", [])
    except: return False
    with tempfile.NamedTemporaryFile(suffix='.py', delete=False, mode='w') as f:
        f.write(code)
        temp_file = f.name
    passed = True
    try:
        for i in range(len(inputs)):
            res = subprocess.run([sys.executable, temp_file], input=inputs[i], 
                                capture_output=True, text=True, timeout=5)
            if res.stdout.strip() != outputs[i].strip():
                passed = False; break
    except: passed = False
    finally:
        if os.path.exists(temp_file): os.remove(temp_file)
    return passed

# ==========================================
# 4. 主运行逻辑
# ==========================================
def evaluate_model(model_name, level, num_problems, k):
    safe_name = model_name.replace("/", "_")
    save_path = os.path.join(SAVE_DIR, f"{safe_name}_{level}.json")
    
    dataset = load_dataset("codeparrot/apps", level, split="test", trust_remote_code=True)
    
    generations_only = {}
    total_metrics = {"pass1": [], "passk": [], "rows": [], "cc": [], "args": []}

    print(f"\n🚀 开始评测: {model_name} | 级别: {level} | 样本数: {k}")

    for i in tqdm(range(min(len(dataset), num_problems))):
        item = dataset[i]
        prob_id = str(i)
        codes = []
        correct_count = 0
        
        for s in range(k):
            try:
                resp = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "system", "content": SYSTEM_PROMPT},
                              {"role": "user", "content": item["question"]}],
                    temperature=0.7 
                )
                code = re.sub(r"```[pP]ython\s*|```", "", resp.choices[0].message.content).strip()
                codes.append(code)
                
                # 计算指标并记录
                r, c, a = calculate_metrics(code)
                total_metrics["rows"].append(r)
                total_metrics["cc"].append(c)
                total_metrics["args"].append(a)
                
                # 跑测试
                if run_test_cases(code, item["input_output"]):
                    correct_count += 1
            except Exception as e:
                print(f"Error: {e}")

        generations_only[prob_id] = codes
        total_metrics["pass1"].append(correct_count / k)
        total_metrics["passk"].append(1 if correct_count > 0 else 0)

    # 1. 仅保存代码文件
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(generations_only, f, indent=4, ensure_ascii=False)

    # 2. 终端打印统计报表
    print("\n" + "="*50)
    print(f"📊 评测报告 - {model_name} ({level})")
    print("-" * 50)
    print(f"✅ Pass@1: {sum(total_metrics['pass1'])/len(total_metrics['pass1']):.2%}")
    print(f"✅ Pass@{k}: {sum(total_metrics['passk'])/len(total_metrics['passk']):.2%}")
    print(f"📝 Avg Rows (Precise): {sum(total_metrics['rows'])/len(total_metrics['rows']):.2f}")
    print(f"复杂 Avg CC: {sum(total_metrics['cc'])/len(total_metrics['cc']):.2f}")
    print(f"参数 Avg Args: {sum(total_metrics['args'])/len(total_metrics['args']):.2f}")
    print("-" * 50)
    print(f"📂 生成文件已保存至: {save_path}")
    print("="*50 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--level", type=str, choices=['introductory', 'interview', 'competition'], default="introductory")
    parser.add_argument("--num", type=int, default=10)
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()

    if not os.path.exists(SAVE_DIR): os.makedirs(SAVE_DIR)
    for model in args.models:
        evaluate_model(model, args.level, args.num, args.k)