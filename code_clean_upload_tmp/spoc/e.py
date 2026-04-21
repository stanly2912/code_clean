#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval.py : 读取 codes.json，评估所有生成的代码
"""

import subprocess
import tempfile
import json
from pathlib import Path
import argparse
from tqdm import tqdm
from datetime import datetime


# 配置
SPOC_ROOT = Path("/home/wangbn/code_clean/spoc/")
TESTCASES_DIR = SPOC_ROOT / "testcases"
GCC = ["g++", "-std=c99", "-lm", "-O2"]


def run_testcases(probid: str, binary: Path, timeout=5) -> tuple[bool, str]:
    hidden = TESTCASES_DIR / f"{probid}"/ f"{probid}_testcases_hidden.txt"
    print("[run_testcases] hidden", hidden)
    if not hidden.exists():
        return False, f"hidden testcases missing: {hidden.name}"

    content = hidden.read_text(encoding="utf-8", errors="ignore")
    cases = []
    cur_in, cur_out = [], []
    reading_out = False

    for line in content.splitlines():
        line = line.rstrip("\r\n")
        if line == "---":
            if cur_in:
                cases.append(("\n".join(cur_in)+"\n", "\n".join(cur_out).strip()))
            cur_in, cur_out = [], []
            reading_out = True
            continue
        if line.strip() == "": continue
        if reading_out:
            cur_out.append(line)
        else:
            cur_in.append(line)

    if cur_in:
        cases.append(("\n".join(cur_in)+"\n", "\n".join(cur_out).strip()))

    if not cases:
        return False, "no test cases"

    for i, (inp, exp) in enumerate(cases, 1):
        try:
            r = subprocess.run(
                [str(binary)], input=inp.encode(),
                capture_output=True, timeout=timeout, check=False
            )
            out = r.stdout.decode(errors="ignore").rstrip()
            if out != exp:
                return False, f"test {i} failed"
        except subprocess.TimeoutExpired:
            return False, f"test {i} timeout"
        except Exception as e:
            return False, f"test {i} error: {str(e)}"

    return True, f"pass ({len(cases)} tests)"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("codes_json", type=str, help="infer.py 生成的 codes.json 路径")
    parser.add_argument("--output", type=str, default="evaluation.json")
    args = parser.parse_args()

    codes_path = Path(args.codes_json)
    if not codes_path.exists():
        print(f"文件不存在：{codes_path}")
        return

    with open(codes_path, encoding="utf-8") as f:
        data = json.load(f)

    problems = data.get("problems", [])
    k = data["metadata"].get("k", "?")
    print(f"加载 {len(problems)} 个问题，每个 {k} 个候选")

    summary = []
    total_pass_any = 0

    for prob in tqdm(problems, desc="Evaluating"):
        probid = prob["probid"]
        pass_count = 0
        details = []

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            for idx, cand in enumerate(prob["candidates"], 1):
                code = cand#.get("cleaned", "")
                if not code.strip():
                    details.append({"idx": idx, "compile_ok": False, "pass": False, "msg": "empty code"})
                    continue

                src = tmp / f"p{idx}.c"
                binp = tmp / f"prog{idx}"
                src.write_text(code)

                try:
                    subprocess.run(GCC + ["-o", str(binp), str(src)], check=True, capture_output=True, timeout=10)
                    success, msg = run_testcases(probid, binp)
                    print("[main]",success,msg)
                    if success:
                        pass_count += 1
                except Exception as e:
                    success = False
                    msg = f"compile failed: {str(e)}"

                details.append({
                    "idx": idx,
                    "compile_ok": "compile_ok" in locals() and locals()["compile_ok"] != False,
                    "pass": success,
                    "msg": msg[:200]
                })

        pass_any = pass_count > 0
        if pass_any:
            total_pass_any += 1

        summary.append({
            "probid": probid,
            "total_candidates": len(prob["candidates"]),
            "pass_count": pass_count,
            "pass_any": pass_any,
            "details": details
        })

    total_problems = len(summary)
    pass_at_k = total_pass_any / total_problems if total_problems > 0 else 0

    result = {
        "metadata": {
            "evaluated_at": datetime.now().isoformat(),
            "codes_file": str(codes_path),
            "total_problems": total_problems,
            "pass_at_k": pass_at_k,
            "k": k,
            "gcc": " ".join(GCC)
        },
        "summary": summary
    }

    out_path = Path(args.output)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n评估完成")
    print(f"总题目数          : {total_problems}")
    print(f"至少通过1次的题目 : {total_pass_any}")
    print(f"pass@{k}          : {pass_at_k:.4f}")
    print(f"结果保存至        : {out_path}")


if __name__ == "__main__":
    main()