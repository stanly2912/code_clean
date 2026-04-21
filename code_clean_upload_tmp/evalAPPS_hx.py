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
from radon.complexity import cc_visit


sys.path.insert(0, "./parser_code/")
import cut

#APPS 测试集路径 
APPS_LOCAL_PATH = "/home/wangbn/APPS/test"

# ==========================================
# CC, Rows, Args
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
# Pass@k
# ==========================================
def run_apps_test_case(code, io_dict):
    """
    轻量级 APPS 评测沙箱：直接接收解析好的 IO 字典
    """
    if not io_dict or not isinstance(io_dict, dict):
        return False
        
    inputs = io_dict.get("inputs", [])
    outputs = io_dict.get("outputs", [])
    
    if not inputs or not outputs:
        return False

    with tempfile.NamedTemporaryFile(suffix='.py', delete=False, mode='w', encoding='utf-8') as f:
        f.write(code)
        temp_file = f.name
        
    passed = True
    
    print("[run_apps_test_case] code=",code)
    
    try:
        # 可以取前 k 个测试用例
        for inp, exp_out in zip(inputs[:1], outputs[:1]):
            res = subprocess.run(
                [sys.executable, temp_file], 
                input=inp, 
                text=True, 
                capture_output=True, 
                timeout=3  # 超时时间 3 秒
            )
            print("[run_apps_test_case] inp=",inp)
            print("[run_apps_test_case] exp_out=",exp_out)
            print("[run_apps_test_case] res.stdout=",res.stdout)
            passed=(res.returncode == 0 and res.stdout.strip() == exp_out.strip())
            print("[run_apps_test_case] passed=",passed)
            # 如果报错，或者输出不匹配，则判错
            if not passed:
                print("[run_apps_test_case] res=",res)
                break
    except Exception:
        passed = False
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)
    
    print("[run_apps_test_case] last passed=",passed)
    return passed

# ==========================================
#  核心评测主流程
# ==========================================
def evaluate_generated_file(file_path, level):
    if not os.path.exists(file_path):
        print(f"❌ 找不到文件: {file_path}")
        return

    print(f"\n🚀 开始评测文件: {file_path} | 级别: {level}")
    
    # 解析 JSONL 文件
    generations = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                generations.append(json.loads(line))

    if not generations:
        print("❌ 文件为空或格式错误！")
        return

    total_metrics = {"pass1": [], "pass5": [], "rows": [], "cc": [], "args": []}

    for item in tqdm(generations, desc="Evaluating codes"):
        task_id = str(item["task_id"]) # 例如 "3000"
        codes = item.get("completions", [])
        
        # 直接从本地读取该题目的测试用例！
        io_file_path = os.path.join(APPS_LOCAL_PATH, task_id, "input_output.json")
        
        if not os.path.exists(io_file_path):
            # 如果本地找不到测试用例文件，跳过这题
            continue
            
        with open(io_file_path, "r", encoding="utf-8") as f:
            io_data_str = f.read()
            try:
                io_dict = json.loads(io_data_str)
            except Exception:
                continue
        
        is_first_correct = False
        is_any_correct = False
        
        # 遍历生成的多个代码样本 (k=5)
        for i, code_ in enumerate(codes):
            code=cut.fix_code(code_)

            if(1):          
                r, c, a = calculate_metrics(code)
                total_metrics["rows"].append(r)
                total_metrics["cc"].append(c)
                total_metrics["args"].append(a)
                
      
            is_correct = False
            if code.strip():
                is_correct = run_apps_test_case(code, io_dict)
                
            # 记录第一个代码的结果作为 Pass@1
            if i == 0:
                is_first_correct = is_correct
                
            # 记录整体 Pass@5 是否有任何一个通过
            if is_correct:
                is_any_correct = True
                
        # 保存该题最终指标
        if codes:
            total_metrics["pass1"].append(1 if is_first_correct else 0)
            total_metrics["pass5"].append(1 if is_any_correct else 0)

    # 打印最终评测报告
    if total_metrics["pass1"]:
        print("total_metrics=",total_metrics)
        print("\n" + "="*50)
        print(f"📊 APPS 评测报告 - 级别: {level}")
        print(f"📄 文件: {os.path.basename(file_path)}")
        print("-" * 50)
        print(f"✅ Pass@1:  {sum(total_metrics['pass1']) / len(total_metrics['pass1']):.2%} (基于每个题目的第1个代码)")
        print(f"✅ Pass@5:  {sum(total_metrics['pass5']) / len(total_metrics['pass5']):.2%} (基于每个题目的全部5个代码)")
        print(f"📝 Avg Rows: {sum(total_metrics['rows']) / len(total_metrics['rows']):.2f} (有效行数)")
        print(f"🧠 Avg CC:   {sum(total_metrics['cc']) / len(total_metrics['cc']):.2f} (圈复杂度)")
        print(f"📌 Avg Args: {sum(total_metrics['args']) / len(total_metrics['args']):.2f} (参数个数)")
        print("="*50 + "\n")
    else:
        print("⚠️ 评测完成，但未收集到有效数据 (可能是测试用例路径不对)。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="一键评测 APPS 生成代码 (JSONL 格式)")
    parser.add_argument("--file", type=str, required=True, help="生成的 JSONL 文件路径")
    parser.add_argument("--level", type=str, required=True, choices=["introductory", "interview", "competition"], help="APPS 难度级别")
    
    args = parser.parse_args()
    evaluate_generated_file(args.file, args.level)