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
# 1. 统一 API 配置
# ==========================================
API_KEY = "sk_VrZ4jhQDLWUK2lyQj40u5yr6p5Uq1lLpnQ4Cxh_BnUY"
BASE_URL = "https://api.jiekou.ai/openai"
SAVE_DIR = "/home/wangbn/code_clean"

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

SYSTEM_PROMPT = r"""
You are an expert Python programmer. I will give you a function signature and a docstring.
Please provide the COMPLETE and WORKING Python implementation, including the necessary imports, function signature, and docstring.
Output ONLY the raw Python code. Do NOT wrap the code in markdown blocks (e.g., no ```python). Do NOT add explanations.
"""

# ==========================================
# 2. 静态指标计算逻辑 (完美复用你的 calc_atts.py)
# ==========================================
def calc_py_rows(code):
    if not isinstance(code, str) or not code.strip():
        return 0

    code = textwrap.dedent(code)
    ignored_lines = set()

    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if (isinstance(node, ast.Expr) and 
                isinstance(getattr(node, "value", None), ast.Constant) and 
                isinstance(node.value.value, str)):
                start = getattr(node, "lineno", None)
                end = getattr(node, "end_lineno", start)
                if start is not None and end is not None:
                    ignored_lines.update(range(start, end + 1))
    except SyntaxError:
        pass

    code_lines = set()

    try:
        for tok in tokenize.generate_tokens(io.StringIO(code).readline):
            if tok.type in {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, 
                            tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER, tokenize.ENCODING}:
                continue
            if tok.start[0] in ignored_lines:
                continue
            code_lines.add(tok.start[0])
    except tokenize.TokenError:
        for lineno, line in enumerate(code.splitlines(), 1):
            s = line.strip()
            if s and not s.startswith("#"):
                code_lines.add(lineno)

    return len(code_lines)

def calculate_metrics(code):
    rows = calc_py_rows(code)
    try:
        results = cc_visit(code)
        cc = max((r.complexity for r in results), default=1)
    except Exception:
        cc = 1
        
    args_num = 0
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                args_num = max(args_num, len(node.args.args))
    except Exception:
        args_num = 0

    return rows, cc, args_num

# ==========================================
# 3. HumanEval 沙箱执行逻辑
# ==========================================
def run_humaneval_test(generated_code, test_code, entry_point):
    """
    将模型生成的代码、HumanEval自带的测试用例代码，以及执行入口拼接起来，
    放入临时文件中运行，通过判断 returncode 是否为 0 来确认正确性。
    """
    # 拼接验证代码
    full_code = f"{generated_code}\n\n{test_code}\n\ncheck({entry_point})\n"
    
    with tempfile.NamedTemporaryFile(suffix='.py', delete=False, mode='w', encoding='utf-8') as f:
        f.write(full_code)
        temp_file = f.name
        
    passed = True
    try:
        # 给 5 秒超时，防止死循环
        res = subprocess.run([sys.executable, temp_file], capture_output=True, text=True, timeout=5)
        if res.returncode != 0:
            passed = False
    except Exception:
        passed = False
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)
            
    return passed

# ==========================================
# 4. 单个模型评测主流程
# ==========================================
def evaluate_humaneval_model(model_name, k=5):
    safe_name = model_name.replace("/", "_")
    save_path = os.path.join(SAVE_DIR, f"{safe_name}_eval_generations.json")
    
    print(f"\n🚀 开始评测模型: {model_name} | 样本数(K): {k}")
    
    try:
        dataset = load_dataset("openai_humaneval", split="test")
    except Exception as e:
        print(f"数据集加载失败: {e}")
        return

    generations_only = {}
    total_metrics = {"pass1": [], "passk": [], "rows": [], "cc": [], "args": []}

    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)

    for item in tqdm(dataset, desc=f"Evaluating {model_name}"):
        task_id = item["task_id"]
        prompt = item["prompt"]
        test_code = item["test"]
        entry_point = item["entry_point"]
        
        codes = []
        correct_count = 0
        
        for _ in range(k):
            try:
                # 使用 0.7 temperature 保证采样的多样性以计算 pass@5
                resp = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=1024
                )
                raw_code = resp.choices[0].message.content
                
                # 代码清理
                code = re.sub(r"^```[pP]ython\s*", "", raw_code)
                code = re.sub(r"```\s*$", "", code)
                code = code.strip()
                
                if not code.startswith("def ") and not code.startswith("import "):
                    code = prompt + "\n" + code
                    
                codes.append(code)
                
                # 1. 静态指标统计
                r, c, a = calculate_metrics(code)
                total_metrics["rows"].append(r)
                total_metrics["cc"].append(c)
                total_metrics["args"].append(a)
                
                # 2. 沙箱动态测试
                is_correct = run_humaneval_test(code, test_code, entry_point)
                if is_correct:
                    correct_count += 1
                    
            except Exception as e:
                # 异常容错处理
                codes.append("")
                total_metrics["rows"].append(0)
                total_metrics["cc"].append(1)
                total_metrics["args"].append(0)

        # 记录纯净代码字典
        generations_only[task_id] = codes
        
        # 计算该题目的 Pass@1 的期望值 (correct_count / K)
        total_metrics["pass1"].append(correct_count / k)
        # 计算该题目的 Pass@K (只要有1个对即算对)
        total_metrics["passk"].append(1 if correct_count > 0 else 0)

    # 1. 保存纯净的生成代码 JSON
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(generations_only, f, indent=4, ensure_ascii=False)

    # 2. 在终端输出结构化的评测结果报表
    print("\n" + "="*50)
    print(f"📊 HumanEval 评测报告 - {model_name}")
    print("-" * 50)
    print(f"✅ Pass@1:  {sum(total_metrics['pass1']) / len(total_metrics['pass1']):.2%}")
    print(f"✅ Pass@{k}:  {sum(total_metrics['passk']) / len(total_metrics['passk']):.2%}")
    print(f"📝 Avg Rows: {sum(total_metrics['rows']) / len(total_metrics['rows']):.2f} (精确有效行数)")
    print(f"🧠 Avg CC:   {sum(total_metrics['cc']) / len(total_metrics['cc']):.2f}")
    print(f"📌 Avg Args: {sum(total_metrics['args']) / len(total_metrics['args']):.2f}")
    print("-" * 50)
    print(f"📂 生成代码文件已保存至: {save_path}")
    print("="*50 + "\n")


if __name__ == "__main__":
    # 你指定的三个模型（修正了 claude 的名字为 claude-sonnct-4-6）
    models_to_run = [
        "gemini-3.1-pro-preview",
        "claude-sonnet-4-6",
        "deepseek/deepseek-v3.1"
    ]

    for model in models_to_run:
        evaluate_humaneval_model(model, k=5)