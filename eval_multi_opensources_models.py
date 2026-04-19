import os
import json
import argparse
import sys
import subprocess
import tempfile
import ast
import io
import textwrap
import tokenize
import re
from tqdm import tqdm
from datasets import load_dataset
from radon.complexity import cc_visit

# ==========================================
# 0. 智能代码提取器 (核心修复：洗掉大模型的废话)
# ==========================================
def extract_clean_code(raw_text):
    """
    从大模型输出的混杂文本中，精准提取 Python 代码
    """
    if not raw_text or not isinstance(raw_text, str):
        return ""
    
    # 1. 尝试匹配 ```python ... ``` 格式
    pattern_python = re.compile(r'```(?:python|py)(.*?)```', re.IGNORECASE | re.DOTALL)
    match = pattern_python.search(raw_text)
    if match:
        return match.group(1).strip()
        
    # 2. 尝试匹配普通的 ``` ... ``` 格式
    pattern_generic = re.compile(r'```(.*?)```', re.DOTALL)
    match = pattern_generic.search(raw_text)
    if match:
        return match.group(1).strip()
        
    # 3. 兜底策略：如果连代码块都没有，尝试寻找 def 或 import 作为代码的开头
    lines = raw_text.split('\n')
    code_lines = []
    in_code = False
    for line in lines:
        if line.startswith('def ') or line.startswith('import ') or line.startswith('from '):
            in_code = True
        if in_code:
            code_lines.append(line)
            
    if code_lines:
        return '\n'.join(code_lines).strip()
        
    # 4. 如果实在找不到，说明这大概率是一堆废话，返回空字符串
    return ""

# ==========================================
# 1. 静态代码指标分析模块
# ==========================================
def calc_py_rows(code):
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
# 2. 动态沙盒测试模块
# ==========================================
def run_test_cases(code, test_cases_json):
    if not test_cases_json or not code.strip(): return False
    try:
        io_data = json.loads(test_cases_json)
        inputs, outputs = io_data.get("inputs", []), io_data.get("outputs", [])
    except: return False
    if not inputs or not outputs: return False

    with tempfile.NamedTemporaryFile(suffix='.py', delete=False, mode='w', encoding='utf-8') as f:
        f.write(code)
        temp_file = f.name
        
    passed = True
    try:
        for i in range(min(len(inputs), 5)):
            res = subprocess.run(
                [sys.executable, temp_file], 
                input=inputs[i], 
                capture_output=True, 
                text=True, 
                timeout=3
            )
            if res.returncode != 0 or res.stdout.strip() != outputs[i].strip():
                passed = False
                break
    except: passed = False
    finally:
        if os.path.exists(temp_file): os.remove(temp_file)
    return passed

# ==========================================
# 3. 万能主评测逻辑
# ==========================================
def evaluate_file(file_path, level):
    if not os.path.exists(file_path):
        print(f"❌ 找不到文件: {file_path}")
        return

    print(f"\n🚀 开始评测文件: {file_path} | 难度级别: {level}")
    
    # 加载测试用例数据集
    print("正在加载 APPS 官方数据集 (用于获取测试用例)...")
    try:
        dataset = load_dataset("codeparrot/apps", level, split="test", trust_remote_code=True)
    except Exception as e:
        print(f"❌ 数据集加载失败: {e}")
        return

    # 兼容 JSON 字典格式 (类似 {"0": ["code1", "code2"], "1": [...]})
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            tasks_dict = json.load(f)
        except Exception as e:
            print(f"❌ 读取 JSON 文件失败: {e}")
            return

    total_metrics = {"pass1": [], "pass5": [], "rows": [], "cc": [], "args": []}

    for task_id_str, raw_codes in tqdm(tasks_dict.items(), desc="Evaluating"):
        task_idx = int(task_id_str)
        if task_idx >= len(dataset): continue
            
        io_data = dataset[task_idx]["input_output"]
        
        is_first_correct = False
        is_any_correct = False
        
        # 遍历 K 个样本
        for i, raw_code in enumerate(raw_codes):
            # 💥 核心：提取纯净代码！
            clean_code = extract_clean_code(raw_code)
            
            # --- 静态指标分析 ---
            if clean_code:
                r, c, a = calculate_metrics(clean_code)
                total_metrics["rows"].append(r)
                total_metrics["cc"].append(c)
                total_metrics["args"].append(a)
            else:
                total_metrics["rows"].append(0)
                total_metrics["cc"].append(1)
                total_metrics["args"].append(0)
                
            # --- 动态沙盒测试 ---
            is_correct = False
            if clean_code:
                is_correct = run_test_cases(clean_code, io_data)
                
            # 记录第一个
            if i == 0: is_first_correct = is_correct
            # 记录整体
            if is_correct: is_any_correct = True
                
        if raw_codes:
            total_metrics["pass1"].append(1 if is_first_correct else 0)
            total_metrics["pass5"].append(1 if is_any_correct else 0)

    # 4. 输出最终报表
    if total_metrics["pass1"]:
        print("\n" + "="*50)
        print(f"📊 APPS 评测最终报告 - 难度: {level.upper()}")
        print(f"📄 数据源: {os.path.basename(file_path)}")
        print("-" * 50)
        print(f"🎯 Pass@1: {sum(total_metrics['pass1']) / len(total_metrics['pass1']):.2%}")
        print(f"🎯 Pass@5: {sum(total_metrics['pass5']) / len(total_metrics['pass5']):.2%}")
        print(f"📝 Avg Rows: {sum(total_metrics['rows']) / len(total_metrics['rows']):.2f}")
        print(f"🧠 Avg CC:   {sum(total_metrics['cc']) / len(total_metrics['cc']):.2f}")
        print(f"📌 Avg Args: {sum(total_metrics['args']) / len(total_metrics['args']):.2f}")
        print("="*50 + "\n")
    else:
        print("⚠️ 评测完成，但未收集到有效数据。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=str, required=True, help="你要评测的 .json 文件绝对路径")
    parser.add_argument("--level", type=str, required=True, choices=["introductory", "interview", "competition"], help="该文件对应的题目难度")
    args = parser.parse_args()
    evaluate_file(args.file, args.level)