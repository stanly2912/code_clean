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
from tqdm import tqdm
from datasets import load_dataset
from radon.complexity import cc_visit

# ==========================================
# 静态指标计算: CC, Rows, Args
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
# 动态评测核心逻辑
# ==========================================
def run_apps_test_case(code, io_data):
    try:
        io_dict = json.loads(io_data)
    except Exception:
        return False
        
    inputs = io_dict.get("inputs", [])
    outputs = io_dict.get("outputs", [])
    
    if not inputs or not outputs:
        return False

    with tempfile.NamedTemporaryFile(suffix='.py', delete=False, mode='w', encoding='utf-8') as f:
        f.write(code)
        temp_file = f.name
        
    passed = True
    try:
        # 为了速度，默认运行前5个用例
        for inp, exp_out in zip(inputs[:5], outputs[:5]):
            res = subprocess.run(
                [sys.executable, temp_file], 
                input=inp, 
                text=True, 
                capture_output=True, 
                timeout=3
            )
            if res.returncode != 0 or res.stdout.strip() != exp_out.strip():
                passed = False
                break
    except Exception:
        passed = False
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)
            
    return passed

# ==========================================
# 评测主循环
# ==========================================
def evaluate_generated_file(file_path, level):
    if not os.path.exists(file_path):
        print(f"❌ 找不到文件: {file_path}")
        return

    print(f"\n🚀 正在评测文件: {file_path} | 级别: {level}")
    
    print("正在加载 APPS 数据集测试用例...")
    try:
        dataset = load_dataset("codeparrot/apps", level, split="test", trust_remote_code=True)
    except Exception as e:
        print(f"数据集加载失败: {e}")
        return

    total_metrics = {"pass1": [], "pass5": [], "rows": [], "cc": [], "args": []}

    with open(file_path, "r", encoding="utf-8") as f:
        for line in tqdm(f, desc="Evaluating"):
            item = json.loads(line)
            task_idx = int(item.get("task_id", 0))
            
            # 【关键修改】：这里改为获取 "codes"，对应你生成文件里的 Key
            codes = item.get("codes", [])
            
            if task_idx >= len(dataset):
                continue
                
            io_data = dataset[task_idx]["input_output"]
            
            is_first_correct = False
            is_any_correct = False
            
            for idx, code in enumerate(codes):
                if not code.strip():
                    continue
                
                # 计算静态指标 (Rows, CC, Args)
                r, c, a = calculate_metrics(code)
                total_metrics["rows"].append(r)
                total_metrics["cc"].append(c)
                total_metrics["args"].append(a)
                
                # 运行测试用例
                is_correct = run_apps_test_case(code, io_data)
                
                # 记录 Pass@1 (列表中的第一个代码)
                if idx == 0:
                    is_first_correct = is_correct
                
                # 记录 Pass@5 (只要有一个对就算对)
                if is_correct:
                    is_any_correct = True
                
            if codes:
                total_metrics["pass1"].append(1 if is_first_correct else 0)
                total_metrics["pass5"].append(1 if is_any_correct else 0)

    # 打印最终评测报告
    if total_metrics["pass1"]:
        print("\n" + "="*50)
        print(f"📊 APPS 评测报告 - 级别: {level}")
        print(f"📄 文件: {os.path.basename(file_path)}")
        print("-" * 50)
        print(f"✅ Pass@1:  {sum(total_metrics['pass1']) / len(total_metrics['pass1']):.2%} (基于第1个代码)")
        print(f"✅ Pass@5:  {sum(total_metrics['pass5']) / len(total_metrics['pass5']):.2%} (基于全部样本)")
        print(f"📝 Avg Rows: {sum(total_metrics['rows']) / len(total_metrics['rows']):.2f} (有效行数)")
        print(f"🧠 Avg CC:   {sum(total_metrics['cc']) / len(total_metrics['cc']):.2f} (圈复杂度)")
        print(f"📌 Avg Args: {sum(total_metrics['args']) / len(total_metrics['args']):.2f} (参数个数)")
        print("="*50 + "\n")
    else:
        print("⚠️ 未检测到有效数据，请检查 JSONL 文件内容格式。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="一键评测 APPS 生成结果")
    parser.add_argument("--file", type=str, required=True, help="生成的 .jsonl 文件路径")
    parser.add_argument("--level", type=str, required=True, choices=["introductory", "interview", "competition"], help="APPS 难度级别")
    
    args = parser.parse_args()
    evaluate_generated_file(args.file, args.level)