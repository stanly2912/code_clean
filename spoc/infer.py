#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
infer.py : 从 SPoC testp 生成候选代码，并保存到一个统一的 codes.json
"""

import json
from pathlib import Path
import pandas as pd
from tqdm import tqdm
import argparse



from openai import OpenAI

# ===================== 配置 =====================
SPOC_ROOT = Path("/home/wangbn/code_clean/spoc")
TESTP_TSV = SPOC_ROOT / "test" / "spoc-testp.tsv"
OUTPUT_JSON = Path("codes.json")          # 最终输出文件


def dummy_generate(pseudocode: str, k: int = 10) -> list[dict]:
    """
    你需要替换成真实的模型调用
    返回格式： [{"raw": str, "cleaned": str}, ...] 共 k 条
    """
    # ------------------ 占位实现 ------------------
    dummy_code = """#include <stdio.h>
int main() {
    printf("This is a dummy generated program\\n");
    return 0;
}"""
    results = []
    for i in range(k):
        results.append({
            "cleaned": dummy_code
        })
    return results

    # 真实示例（请自行替换）：
    # from your_llm import generate_multiple
    # raw_outputs = generate_multiple(build_prompt(pseudocode), num=k, temp=0.75)
    # return [{"raw": r, "cleaned": clean_code(r)} for r in raw_outputs]




client_base = OpenAI(api_key="0", base_url="http://0.0.0.0:6002/v1")
client_tune = OpenAI(api_key="0", base_url="http://0.0.0.0:7002/v1")




import sys

sys.path.append("/home/wangbn/code_clean")
from infClean import solve

def infer_once_out(inp=""):
    global client_base, client_tune
    return solve(client_base, client_tune, model="default", user_prompt=inp)


def infer_once_demo(inp="User: Here is the original code. Please provide a cleaner, more concise version of this code following clean code principles\n@Override\n  public void close()\n  {\n    if (stringBufferMapper != null) {\n      stringBufferMapper.close();\n      deleteTempFile(stringDictionaryFile);\n    }\n    if (longBuffer != null) {\n      ByteBufferUtils.unmap(longBuffer);\n      deleteTempFile(longDictionaryFile);\n    }\n    if (doubleBuffer != null) {\n      ByteBufferUtils.unmap(doubleBuffer);\n      deleteTempFile(doubleDictionaryFile);\n    }\n    if (arrayBuffer != null) {\n      ByteBufferUtils.unmap(arrayBuffer);\n      deleteTempFile(arrayDictionaryFile);\n    }\n  }\n\nAssistant:"):
    
    instruction="please give the cpp code to solve the question directly, no more useless output,dont output your thinking proccess.\n"
    print("[infer_once]")
    messages = [{"role": "user", "content":  instruction+inp}
    #,{"role": "system", "content": "please give the python code to solve the question"}
    ]
    result = client.chat.completions.create(messages=messages, model="deepseek")
    ret=result.choices[0].message.content
    print("[infer_once]",messages,ret)
    return ret

def infer_once(inp="User: Here is the original code. Please provide a cleaner, more concise version of this code following clean code principles\n@Override\n  public void close()\n  {\n    if (stringBufferMapper != null) {\n      stringBufferMapper.close();\n      deleteTempFile(stringDictionaryFile);\n    }\n    if (longBuffer != null) {\n      ByteBufferUtils.unmap(longBuffer);\n      deleteTempFile(longDictionaryFile);\n    }\n    if (doubleBuffer != null) {\n      ByteBufferUtils.unmap(doubleBuffer);\n      deleteTempFile(doubleDictionaryFile);\n    }\n    if (arrayBuffer != null) {\n      ByteBufferUtils.unmap(arrayBuffer);\n      deleteTempFile(arrayDictionaryFile);\n    }\n  }\n\nAssistant:"):
    ret=infer_once_out(inp)
    return ret

def LLM_generate(pseudocode: str, k: int = 10) -> list[str]:
    base_code=infer_once(pseudocode)
    return [base_code] * k   # 故意写错，让它通不过



def generate_codes(pseudocode: str, k: int = 10) -> list[dict]:
    print("[generate_codes] pseudocode",pseudocode)
    return LLM_generate(pseudocode,k)

def clean_code(raw: str) -> str:
    """提取代码块 + 简单补全"""
    lines = raw.splitlines()
    code = []
    in_block = False
    for line in lines:
        s = line.strip()
        if s.startswith(("```c", "```cpp")):
            in_block = True
            continue
        if s == "```" and in_block:
            break
        if in_block or s.startswith(("#include", "int main", "return")):
            code.append(line.rstrip())
    
    cleaned = "\n".join(code).strip()
    if "main" in cleaned and "return 0;" not in cleaned[-400:]:
        if not cleaned.endswith("}"):
            cleaned += "\n    return 0;\n}"
        else:
            cleaned += "\n    return 0;"
    return cleaned


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--k", type=int, default=1, help="samples per problem")
    parser.add_argument("--output", type=str, default=str(OUTPUT_JSON))
    args = parser.parse_args()

    if not TESTP_TSV.exists():
        print(f"请先将 SPoC 数据集解压到 {SPOC_ROOT}")
        return

    df = pd.read_csv(TESTP_TSV, sep="\t", dtype=str)

    # 按 probid 去重，只取每个题目的一个代表性伪代码
    unique_problems = {}
    for _, row in df.iterrows():
        probid = str(row["probid"])
        if probid in unique_problems:
            continue
        group = df[df["probid"] == row["probid"]].sort_values("line")
        pseudo_lines = group["text"].fillna("").tolist()
        pseudocode = "\n".join(pseudo_lines)
        unique_problems[probid] = pseudocode

    print(f"找到 {len(unique_problems)} 个唯一 probid")

    all_results = []

    # 加上 list(...)[:10] 强制只取前 10 项
    for probid, pseudocode in tqdm(list(unique_problems.items())[:10], desc="Generating"):
        candidates = generate_codes(pseudocode, k=args.k)

        entry = {
            "probid": probid,
            "pseudocode": pseudocode,
            "candidates": candidates   # list of {"raw":..., "cleaned":...}
        }
        all_results.append(entry)
        
        #break

    # 保存为单一 JSON
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({
            "metadata": {
                "k": args.k,
                "generated_at": str(pd.Timestamp.now()),
                "total_problems": len(all_results)
            },
            "problems": all_results
        }, f, ensure_ascii=False, indent=2)

    print(f"\n生成完成，已保存 {len(all_results)} 个问题 × {args.k} 个候选")
    print(f"文件位置：{args.output}")


if __name__ == "__main__":
    main()