import argparse
import json
import re
import sys


import sys

sys.path.insert(0, "./parser_code")

try:
    from parser_python import parse_code
except ImportError as e:
    print(f"ERR: parse_code import failed: {e}")
    

def k2taskid(k):
    return f"HumanEval/{k}"


def fix_code(raw_code):
    #print("[fix_code] raw_code",raw_code)
    if not isinstance(raw_code, str):
        return ""

    # 1. 移除首尾空白
    ret = raw_code.strip()

    # 2. 保留你原来的特殊替换逻辑
    ret = ("!" + ret).replace(
        "!program language: python",
        '!""""program language: python'
    )[1:]

    # 3. 替换特殊空格
    ret = ret.replace("\u00a0", " ")
    ret = ret.replace("return''", "return ' '")
    
    m = re.search(r"```(?:python)?\s*(.*?)```", ret, re.DOTALL | re.IGNORECASE)
    ret = m.group(1) if m else ret


    # 5. 保留原来的结构检查逻辑
    lines = ret.split("\n")
    if lines:
        content_lines = [l for l in lines if l.strip()]
        if content_lines:
            first_line = content_lines[0]
            indent_match = re.match(r"^\s*", first_line)
            if indent_match:
                pass

    import_code="import sys\n"
    ret=import_code+ret
    ret =ret.replace("\n import", "\nimport")
    
    return ret


def load_input_file(path):
    """
    兼容两种格式：
    1. 整体是一个 JSON 数组/对象
    2. JSONL（每行一个 JSON）
    """
    clean_path = path.replace("\n", "").replace(" ", "")
    with open(clean_path, "r", encoding="utf-8") as f:
        text = f.read().strip()

    if not text:
        return []

    # 先尝试按普通 JSON 读取
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 再按 JSONL 读取
    data = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            data.append(json.loads(line))
        except json.JSONDecodeError as e:
            print(f"[WARN] 第 {line_no} 行不是合法 JSON，已跳过: {e}")
    return data


def extract_codes(item,ONLY_FUNCTION=True):
    """
    根据输入项类型提取代码：
    - str: 用 parse_code 解析
    - dict: 取 refined 字段
    """
    #print("[extract_codes] item=",item)
    ret=None
    if isinstance(item, str):
        ret=item
    elif isinstance(item, list):
        ret=item[0]
    elif isinstance(item, dict):
        for key in ["refined","completion","completions"]:
            if key in item:
                ret=item[key]
                break
    else:
        pass

    if isinstance(ret, str):
        codes=[ret]
    else:
        codes=ret
    
    if not ONLY_FUNCTION:
        return codes
    
    try:
        ret=[]
        for code in codes:
            # 原代码这里写成了 c[0]，那只会取第一个字符，明显有问题
            results = parse_code(code)
            
        #print("[extract_code] results=",results)
            if not results:
                s=""
            else:
                first_value = next(iter(results.values()))
                s=fix_code(first_value.get("function_content", ""))
            ret.append(s)
        return ret
    except:
        print("[extract_codes] ERR:parse_code")


def load_codes(code_path,k2taskid=lambda i:i,ONLY_FUNCTION=True):
    print("[load_codes] code_path",code_path)
    codes = load_input_file(code_path.strip())
    

    #print("[load_codes] codes",codes)
    if isinstance(codes,list):
        ret={k2taskid(k):extract_codes(item,ONLY_FUNCTION) for k,item in enumerate(codes)}
    else:
        ret={k2taskid(k):extract_codes(codes[k],ONLY_FUNCTION) for k in codes}
    print("[load_codes]",len(ret))
    return ret


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input_path",
        default="/home/wangbn/code_clean/cleancodesQWcode25.json",
        help="输入文件路径（支持 JSON / JSONL）"
    )
    parser.add_argument(
        "--output_path",
        default="/home/wangbn/code_clean/human-eval/human_eval/tmp25.jsonl",
        help="输出 JSONL 文件路径"
    )
    args = parser.parse_args()

    content = load_input_file(args.input_path)

    # 如果输入是单个 dict，而不是 list，包一层
    if isinstance(content, dict):
        content = [content]

    results_list = []
    print("!!", len(content))

    for i, c in enumerate(content):
        
        print(i, type(c), "!!")
        code = extract_code(c)

        #print(code, "!!")

        item = {
            "task_id": k2taskid(i),
            "completion": code
        }
        results_list.append(item)

    with open(args.output_path, "w", encoding="utf-8") as f:
        for item in results_list:
            json.dump(item, f, ensure_ascii=False, separators=(",", ":"))
            f.write("\n")


if __name__ == "__main__":
    main()

# 用法示例：
# python /home/wangbn/code_clean/parser_code/cut.py --input_path /home/wangbn/code_clean/cleancodesQWcode25.json --output_path /home/wangbn/code_clean/human-eval/human_eval/tmp25.jsonl


"""
cd /home/wangbn/code_clean/parser_code/
python /home/wangbn/code_clean/parser_code/cut.py --input_path /home/wangbn/code_clean/cleancodesQWcode.json --output_path /home/wangbn/code_clean/human-eval/human_eval/tmp.jsonl
cd /home/wangbn/code_clean/human-eval/human_eval
python ./evaluate_functional_correctness.py  /home/wangbn/code_clean/human-eval/human_eval/tmp.jsonl 


cd /home/wangbn/code_clean/parser_code/ && \
python cut.py \
    --input_path /home/wangbn/code_clean/cleancodesQWcode.json \
    --output_path ../human-eval/human_eval/tmp.jsonl && \
cd /home/wangbn/code_clean/human-eval/human_eval && \
python ./evaluate_functional_correctness.py best.jsonl
"""