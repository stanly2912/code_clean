#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPoC testp 评估脚本示例（pass@1 / pass@k）
要求：
- 已下载并解压 SPoC 数据集到当前目录下的 spoc/
- 使用 GCC 5.5（或在 Docker 中使用 gcc-5）
- 只评估 testp（新题目）上的隐藏测试用例
"""

import os
import subprocess
import tempfile
import json
from pathlib import Path
from typing import List, Dict, Tuple
import pandas as pd
from tqdm import tqdm


from openai import OpenAI


# ===================== 配置区 =====================
SPOC_ROOT = Path("/home/wangbn/code_clean/spoc/")                  # 数据集根目录
TESTP_TSV = SPOC_ROOT / "test" / "spoc-testp.tsv"
TESTCASES_DIR = SPOC_ROOT / "testcases"

GCC_CMD = ["gcc-5", "-std=c99", "-lm", "-O2"]   # 根据你的环境调整（或用 g++）
MAX_SAMPLES_PER_PROBLEM = 1                    # 生成多少个候选（pass@10）
OUTPUT_JSONL = "spoc_eval_results.jsonl"        # 结果保存路径

# ===================== 工具函数 =====================

def load_testp_problems() -> List[Dict]:
    """读取 spoc-testp.tsv，按 probid + subid 分组，提取伪代码"""
    if not TESTP_TSV.exists():
        raise FileNotFoundError(f"{TESTP_TSV} not found. Please download SPoC dataset.")
    print("[load_testp_problems] TESTP_TSV",TESTP_TSV)
    df = pd.read_csv(TESTP_TSV, sep="\t", dtype=str)
    problems = []

    for (probid, subid), group in df.groupby(["probid", "subid"]):
        group = group.sort_values("line")
        pseudo_lines = group["text"].fillna("").tolist()
        code_lines = group["code"].tolist()           # 仅作参考，不用于评估
        indents = group["indent"].astype(int).tolist()

        # 拼接伪代码（保留空行）
        pseudocode = "\n".join(pseudo_lines)

        problems.append({
            "probid": str(probid),
            "subid": str(subid),
            "pseudocode": pseudocode,
            "reference_code": "\n".join(code_lines),  # 仅参考
            "indents": indents,
        })

    print(f"Loaded {len(problems)} submissions from testp "
          f"({len(set(p['probid'] for p in problems))} unique problems)")
    return problems


def clean_generated_code(raw_output: str) -> str:
    """清理模型生成的代码：只保留 C 代码部分"""
    lines = raw_output.strip().split("\n")
    code_lines = []
    in_code_block = False

    for line in lines:
        stripped = line.strip()
        if "```c" in stripped or "```cpp" in stripped:
            in_code_block = True
            continue
        if "```" in stripped and in_code_block:
            break
        if in_code_block or (stripped.startswith("#include") or stripped.startswith("int main")):
            code_lines.append(line.rstrip())  # 保留原始缩进

    code = "\n".join(code_lines).strip()

    # 简单补全常见缺失
    if "main" in code and "return 0;" not in code[-200:]:
        code += "\n    return 0;\n}"

    return code


def compile_and_run(probid: str, code: str) -> Tuple[bool, str]:
    """编译并运行隐藏测试用例，返回是否全部通过"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        source_path = tmpdir / "program.c"
        binary_path = tmpdir / "program"

        source_path.write_text(code)

        # 编译
        compile_cmd = GCC_CMD + ["-o", str(binary_path), str(source_path)]
        try:
            subprocess.run(compile_cmd, check=True, capture_output=True, timeout=10)
        except Exception as e:
            return False, f"Compilation failed: {e}"

        # 找到该 probid 的所有隐藏测试用例
        hidden_file = TESTCASES_DIR / f"{probid}_testcases_hidden.txt"
        if not hidden_file.exists():
            return False, f"Hidden testcases not found: {hidden_file}"

        # 解析测试用例文件（格式：输入\n---\n预期输出\n\n下一组...）
        cases = []
        current_input, current_output = [], []
        mode = None

        for line in hidden_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.rstrip()
            if line == "---":
                if current_input:
                    cases.append((current_input, current_output))
                current_input, current_output = [], []
                mode = "output"
                continue
            if line.strip() == "":
                continue
            if mode == "output":
                current_output.append(line)
            else:
                current_input.append(line)

        if current_input:
            cases.append((current_input, current_output))

        if not cases:
            return False, "No test cases found"

        # 逐个运行测试
        for idx, (inp_lines, exp_lines) in enumerate(cases, 1):
            input_str = "\n".join(inp_lines) + "\n"
            expected = "\n".join(exp_lines).strip()

            try:
                result = subprocess.run(
                    [str(binary_path)],
                    input=input_str.encode(),
                    capture_output=True,
                    timeout=5,
                    check=False
                )
                output = result.stdout.decode(errors="ignore").strip()

                if output != expected:
                    return False, f"Failed on test case {idx}: output mismatch"
            except Exception as e:
                return False, f"Runtime error on test case {idx}: {e}"

        return True, "All test cases passed"


def evaluate_model(generate_func, problems: List[Dict], k: int = 10):
    """主评估函数
    generate_func: 你的模型生成函数，输入 pseudocode → 返回 List[str] (k个代码候选)
    """
    results = []
    unique_problems = {p["probid"]: p for p in problems}  # 按 probid 去重
    prob_list = list(unique_problems.values())

    for prob in tqdm(prob_list, desc="Evaluating problems"):
        pseudocode = prob["pseudocode"]
        probid = prob["probid"]

        # 调用模型生成 k 个候选
        candidates = generate_func(pseudocode, k=k)   # 你需要自己实现这个函数

        pass_count = 0
        details = []

        for i, raw_code in enumerate(candidates):
            cleaned_code = clean_generated_code(raw_code)
            success, msg = compile_and_run(probid, cleaned_code)

            details.append({
                "sample_id": i,
                "raw": raw_code[:300] + "...",  # 截断保存
                "cleaned": cleaned_code[:500] + "...",
                "success": success,
                "message": msg
            })

            if success:
                pass_count += 1
        print("[evaluate_model] probid,pass_count=",probid,pass_count)
        results.append({
            "probid": probid,
            "pseudocode": pseudocode[:500] + "...",
            "pass_count": pass_count,
            "k": k,
            "pass": pass_count > 0,
            "details": details
        })

    # 计算 pass@k
    total = len(results)
    passed = sum(1 for r in results if r["pass"])
    pass_rate = passed / total if total > 0 else 0

    print(f"\nEvaluation completed:")
    print(f"Total unique problems: {total}")
    print(f"Passed (at least one success): {passed}")
    print(f"pass@{k}: {pass_rate:.4f} ({passed}/{total})")

    # 保存结果
    with open(OUTPUT_JSONL, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    return results


# ===================== 示例：模型生成函数（占位） =====================

def dummy_generate(pseudocode: str, k: int = 10) -> List[str]:
    """占位函数：请替换成你真实的模型调用（OpenAI / vLLM / transformers 等）"""
    # 这里只是演示，实际请调用你的模型
    base_code = """
#include <stdio.h>
int main() {
    printf("Hello from dummy generator\\n");
    return 0;
}
"""
    return [base_code] * k   # 故意写错，让它通不过


client = OpenAI(api_key="0", base_url="http://0.0.0.0:7000/v1")


def infer_once(inp="User: Here is the original code. Please provide a cleaner, more concise version of this code following clean code principles\n@Override\n  public void close()\n  {\n    if (stringBufferMapper != null) {\n      stringBufferMapper.close();\n      deleteTempFile(stringDictionaryFile);\n    }\n    if (longBuffer != null) {\n      ByteBufferUtils.unmap(longBuffer);\n      deleteTempFile(longDictionaryFile);\n    }\n    if (doubleBuffer != null) {\n      ByteBufferUtils.unmap(doubleBuffer);\n      deleteTempFile(doubleDictionaryFile);\n    }\n    if (arrayBuffer != null) {\n      ByteBufferUtils.unmap(arrayBuffer);\n      deleteTempFile(arrayDictionaryFile);\n    }\n  }\n\nAssistant:"):
    instruction="please give the cpp code to solve the question directly, no more useless output,dont output your thinking proccess.\n"
    messages = [{"role": "user", "content":instruction+  inp}
    #,{"role": "system", "content": "please give the python code to solve the question"}
    ]
    result = client.chat.completions.create(messages=messages, model="deepseek")
    ret=result.choices[0].message.content
    print("[infer_once]",messages,ret)
    return ret

def LLM_generate(pseudocode: str, k: int = 10) -> List[str]:
    infer_once(pseudocode)
    return [base_code] * k   # 故意写错，让它通不过



# ===================== 主程序 =====================

if __name__ == "__main__":
    problems = load_testp_problems()
    # 替换成你自己的生成函数，例如：
    # from your_model import generate_code
    # def my_generate(pseudo, k): return generate_code(pseudo, num_samples=k)

    evaluate_model(
        generate_func=dummy_generate,   # ← 替换这里 LLM_generate dummy_generate
        problems=problems,
        k=MAX_SAMPLES_PER_PROBLEM
    )