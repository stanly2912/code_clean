# calculate_java_cc.py
import lizard
import sys
from pathlib import Path
from io import StringIO
import json
import numpy as np
import pandas as pd
        
        
import sys




sys.path.insert(0, "/home/wangbn/code_clean/parser_code/")
import cut



# 动态添加 human-eval 根目录到 sys.path
human_eval_root = "/home/wangbn/code_clean/human-eval"  # 改成你的实际路径
sys.path.insert(0, human_eval_root)

# 现在可以正常导入包
from human_eval.data import stream_jsonl


def calculate_java_cyclomatic_complexity(code: str, display_name: str = "<code>") -> None:
    """
    使用 lizard 分析 Java 程式碼字串的圈複雜度（修正版）
    """
    try:
        # 正確用法：analyze 返回 iterator，要轉成 list
        results = list(
            lizard.analyze(
                display_name,
                lambda name: StringIO(code)
            )
        )

        # 通常在這種調用下，results 應該只有一個 FileInfo
        if not results:
            print("分析結果為空，沒有偵測到任何程式碼結構")
            return

        # 取第一個（也通常是唯一一個）檔案資訊
        file_info = results[0]

        functions = file_info.function_list

        if not functions:
            print("沒有找到任何 function/method")
            return

        # 按複雜度降序排列
        sorted_functions = sorted(
            functions,
            key=lambda f: f.cyclomatic_complexity,
            reverse=True
        )

        total_cc = sum(f.cyclomatic_complexity for f in functions)
        count = len(functions)
        avg = total_cc / count if count > 0 else 0.0

        print(f"\n分析結果：{display_name}")
        print("═" * 70)
        print(f"總圈複雜度 : {total_cc:3d}")
        print(f"函數/方法數 : {count:3d}")
        print(f"平均複雜度  : {avg:.2f}")
        print()

        print("複雜度最高的前 8 個（或全部）：")
        print(" 複雜度   程式碼行數   起始行   函數名稱")
        print("-" * 60)

        for f in sorted_functions[:8]:
            print(f"{f.cyclomatic_complexity:>6d}      {f.nloc:>6d}      {f.start_line:>4d}   {f.name}")

        if len(sorted_functions) > 8:
            print(f"\n... 還有 {len(sorted_functions)-8} 個方法未顯示 ...")

    except Exception as e:
        print("分析失敗：", str(e))

def calc_java_atts(code):
    try:
        #print("[calc_java_atts] code",code)
        result = lizard.analyze_file.analyze_source_code("tmp.java", code)
        lizard_atts=result.function_list[0].__dict__
        #print("[calc_java_atts] lizard_atts",lizard_atts)
        
        ret={"cc":lizard_atts["cyclomatic_complexity"],
              "args":  len(lizard_atts["full_parameters"]),
              "rows":lizard_atts["end_line"]-lizard_atts["start_line"]}
              
              
              
        print("[calc_java_atts] success ret",ret,"lizard_atts",lizard_atts)
        return ret


    except Exception as e:
        print("[calc_java_atts] error", str(e),code)
        
        
        ret={"cc":1,
              "args":  1,
              "rows":1}
        return None
    
def calc_javas_atts(dics,KEYS):
    print("[calc_javas_atts]",len(dics))
    ret=[]
    for dic in dics:
        A={}
        for key in KEYS:
            code=dic[key]
            atts=calc_java_atts(code)
            if(atts is None):
                continue
            atts["code"]=code
            A[key]=atts
        ret.append(A)
    return ret

def solve_java():
    code_path=r"/home/wangbn/code_clean/llm_output/output75.json"
    
    output_path=r"/home/wangbn/code_clean/result75.csv"

    KEYS=["input","predict"]

    with open(code_path, "r",encoding='utf-8') as f:
        dics = json.load(f)
    result=calc_javas_atts(dics,KEYS)
    
    A={}
    for dic in result:
        for key in dic:
            if key not in A:
                A[key]={}
            for att_name in dic[key]:
                if att_name not in A[key]:
                    A[key][att_name]=[]
                A[key][att_name].append(dic[key][att_name])
                
    for key in KEYS:
        for att_name in A[key]:
            #print("!!",key,att_name,len(A[key][att_name]),A[key][att_name])
            try:
                value= np.nanmean(A[key][att_name]) 
            except:
                value=0
                
            A[key][att_name] = value


    
    pd.DataFrame(A).to_csv(output_path)
    

import ast
from radon.complexity import cc_visit


import ast
import io
import textwrap
import tokenize

def check_code(code):
    if not isinstance(code, str) or not code.strip():
        return False
    return True

def calc_py_rows(code):
    if check_code(code)==False:
        return np.inf

    code = textwrap.dedent(code)

    ignored_lines = set()

    # 去掉独立的字符串表达式：模块/函数/类 docstring，以及常见的三引号“多行注释”
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Expr)
                and isinstance(getattr(node, "value", None), ast.Constant)
                and isinstance(node.value.value, str)
            ):
                start = getattr(node, "lineno", None)
                end = getattr(node, "end_lineno", start)
                if start is not None and end is not None:
                    ignored_lines.update(range(start, end + 1))
    except SyntaxError:
        pass

    code_lines = set()

    try:
        for tok in tokenize.generate_tokens(io.StringIO(code).readline):
            if tok.type in {
                tokenize.COMMENT,
                tokenize.NL,
                tokenize.NEWLINE,
                tokenize.INDENT,
                tokenize.DEDENT,
                tokenize.ENDMARKER,
                tokenize.ENCODING,
            }:
                continue

            if tok.start[0] in ignored_lines:
                continue

            code_lines.add(tok.start[0])
    except tokenize.TokenError:
        # 兜底：如果 tokenize 失败，就退化成简单按行统计
        for lineno, line in enumerate(code.splitlines(), 1):
            s = line.strip()
            if s and not s.startswith("#"):
                code_lines.add(lineno)

    return len(code_lines)

def calc_py_atts(code):
    
    """
    计算Python代码属性：
    cc   : 圈复杂度
    args : 函数参数个数
    rows : 代码行数
    """


    # -----------------------
    # 1 代码行数
    # -----------------------
    rows = calc_py_rows(code)

    # -----------------------
    # 2 圈复杂度
    # -----------------------
    try:
        assert check_code(code)
        results = cc_visit(code)
        if len(results) > 0:
            cc = max(r.complexity for r in results)
        else:
            cc = 1
    except Exception:
        cc = np.inf

    # -----------------------
    # 3 参数个数
    # -----------------------
    args_num = 0
    try:
        assert check_code(code)
        tree = ast.parse(code)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                args_num = max(args_num, len(node.args.args))

    except Exception:
        args_num = np.inf

    # -----------------------
    # 返回结果
    # -----------------------
    if(1 and 1): 
        print("[calc_py_atts] code",code)
        print("[calc_py_atts] cc",cc)
        print("[calc_py_atts] rows",rows)
    ret = {
        "cc": cc,      # 圈复杂度
        "args": args_num,  # 参数个数
        "rows": rows       # 行数
    }

    return ret

    
def solve(codes,func_calc_atts):
    #func_calc_atts=calc_py_atts
    
    output_path = "/home/wangbn/code_clean/res_atts.csv"

    
    # 假设 codes 是 dict: {id/str: code_str}
    # 如果是 list，就改成 for item in codes: code = item["code"] 或 item 本身
    
    results = []
    
    for key, cs in codes.items():
        for code in cs[0:1]:
            if not isinstance(code, str):
                print(f"跳过非字符串代码：key={key}",code)
                continue
                
            atts = func_calc_atts(code)
            if atts:
                atts["key"] = key          # 保留原始 key，便于追溯
                results.append(atts)
    
    if not results:
        print("没有成功解析任何代码")
        return
    
    # 转 DataFrame 并计算平均值
    df = pd.DataFrame(results)
    
    
        # 计算平均值（只对数值列，跳过无效 inf 和 NaN）
    mean_row = (
        df.replace([np.inf, -np.inf], np.nan)
        .mean(numeric_only=True, skipna=True)
        .to_frame()
        .T
    )
    mean_row["key"] = "平均值"   # 可选：标记这一行
    
    # 也可以直接保存所有记录 + 最后加一行平均
    # df = pd.concat([df, mean_row], ignore_index=True)
    
    # 只保存平均值（看你需求）
    #mean_row.to_csv(output_path, index=False, encoding="utf-8-sig")
    # 或保存全部结果
    # df.to_csv(output_path, index=False, encoding="utf-8-sig")
    
    #print("code_path" ,code_path)
    print(f"已保存到：{output_path}")
    print("平均值：")
    print(mean_row)



def calc_cpp_atts(code):
    import lizard
    import tempfile
    import os

    cc = 0
    args_num = 0
    rows = 0

    # 写入临时 cpp 文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=".cpp", mode="w", encoding="utf-8") as f:
        f.write(code)
        tmp_path = f.name

    try:
        analysis = lizard.analyze_file(tmp_path)

        # 统计所有函数信息
        for func in analysis.function_list:
            cc = max(cc, func.cyclomatic_complexity)  # 取最大圈复杂度
            args_num = max(args_num, len(func.parameters))  # 最大参数个数
            rows += func.nloc  # 累加函数代码行数

        # 如果没有识别到函数，则按文本行数统计
        if rows == 0:
            rows = len(code.strip().split("\n"))

    finally:
        os.remove(tmp_path)

    ret = {
        "cc": cc,           # 圈复杂度
        "args": args_num,   # 参数个数
        "rows": rows        # 行数
    }

    return ret

def calc_cpp_cc(code):
    """
    Calculate cyclomatic complexity of C++ code using lizard.
    Returns the total cyclomatic complexity.
    """
    import lizard
    import tempfile
    import os

    # 写入临时cpp文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=".cpp", mode="w", encoding="utf-8") as f:
        f.write(code)
        tmp_path = f.name

    try:
        analysis = lizard.analyze_file(tmp_path)

        # 统计所有函数的圈复杂度
        total_cc = 0
        func_details = []

        for func in analysis.function_list:
            total_cc += func.cyclomatic_complexity
            func_details.append({
                "name": func.name,
                "cc": func.cyclomatic_complexity,
                "nloc": func.nloc
            })

        return {
            "total_cc": total_cc,
            "functions": func_details
        }

    finally:
        os.remove(tmp_path)

def load_spoc_codes(code_path):
    
    try:
        with open(code_path, encoding="utf-8") as f:
            dic = json.load(f)
    except Exception as e:
        print(f"无法读取 {code_path} : {e}")
    

    A=dic["problems"]
    ret={dic["probid"]:dic["candidates"][0] for dic in A}
    return ret

def load():
    
    
    code_path = "/home/wangbn/code_clean/apps-main/eval/generate75/0-10_codes.json"
    
    # 1. 读取 json 文件
    try:
        with open(code_path, encoding="utf-8") as f:
            codes = json.load(f)
    except Exception as e:
        print(f"无法读取 {code_path} : {e}")



import argparse
if __name__ == "__main__":

    if(0):
        content = '''
    def main(a, b): 
        \'\'\'
        a
        a
        a
        \'\'\'

        \"\"\"
        a
        a
        a
        \"\"\"
        
        # hello
        # hello
        # hello
        # hello
        # hello
        # hello
        # hello
        # hello
        # hello
        # hello
        for _ in range(10):
            if (a > b and a < b) or (a == b):
                print(1)
                return
            elif a > b:
                print(2)
            else:
                print(2)
            b = a if a > b else b
            for _ in range(10):
                print(a)
        for _ in range(10):
            for _ in range(10):
                print(a)
    def main1(a, b):
        for _ in range(10):
            for _ in range(10):
                print(a)
        for _ in range(10):
            for _ in range(10):
                print(a)
    '''
        calc_py_atts(content)
        exit()




    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--codes_path",
        type=str,
        default=r"/home/wangbn/code_clean/human-eval/human_eval/best.jsonl",
        help="Path to the input code file",
    )
    parser.add_argument(
        "--only_function",
        type=str,
        choices=["0", "1"],
        default="0",
        help="Whether to load only function bodies: 1 for True, 0 for False",
    )

    args = parser.parse_args()

    # codes = load_spoc_codes(r"/home/wangbn/code_clean/spoc/codes25.json")
    # solve(codes, calc_cpp_atts)

    codes = cut.load_codes(args.codes_path, ONLY_FUNCTION=(args.only_function == "1"))
    solve(codes, calc_py_atts)

    print("args.codes_path:", args.codes_path)
    print("args.only_function:", args.only_function)

"""

python /home/wangbn/code_clean/calc_atts.py --codes_path /home/wangbn/code_clean/human-eval/human_eval/best.jsonl


python /home/wangbn/code_clean/calc_atts.py --codes_path /home/wangbn/code_clean/human-eval/human_eval/codesQWcoder.jsonl


python /home/wangbn/code_clean/calc_atts.py --codes_path /home/wangbn/code_clean/human-eval/human_eval/best.jsonl > ~/tmp.txt; python /home/wangbn/code_clean/calc_atts.py --codes_path /home/wangbn/code_clean/human-eval/human_eval/codesQWcoder.jsonl >> ~/tmp.txt;




"""