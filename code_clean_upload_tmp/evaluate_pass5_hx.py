import os
import json
import subprocess
import tempfile
from tqdm import tqdm

# ========= 你需要改 =========
BASE_DIR = "/home/wangbn/apps_our/MAS/interview_pass5.jsonl"
APPS_TEST_DIR = "/home/wangbn/APPS/test"
EXECUTION_TIMEOUT = 5
K = 5

# ========= 运行代码 =========
def run_code(code, input_str):
    if not code.strip():
        return None

    header = """import sys
sys.setrecursionlimit(10000)
"""

    full_code = header + code

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(full_code)
        path = f.name

    try:
        result = subprocess.run(
            ["python3", path],
            input=str(input_str),
            text=True,
            capture_output=True,
            timeout=EXECUTION_TIMEOUT
        )
        return result.stdout
    except:
        return None
    finally:
        os.remove(path)

# ========= 标准化 =========
def normalize(s):
    return " ".join(str(s).strip().split())

# ========= 评测单个代码 =========
def check_correct(code, inputs, outputs):
    for inp, out in zip(inputs, outputs):
        pred = run_code(code, inp)
        if pred is None:
            return False

        if normalize(pred) != normalize(out):
            return False

    return True

# ========= 评测一个难度 =========
def eval_split(split):
    split_path = os.path.join(BASE_DIR, split)

    if not os.path.exists(split_path):
        print(f"{split} 不存在")
        return 0, 0

    task_ids = [
    x for x in os.listdir(split_path)
    if x.isdigit() and os.path.isdir(os.path.join(split_path, x))
]
    task_ids = sorted(task_ids, key=lambda x: int(x))

    total = 0
    passed = 0

    for task_id in tqdm(task_ids, desc=split):
        task_path = os.path.join(split_path, task_id)

        io_path = os.path.join(APPS_TEST_DIR, task_id, "input_output.json")
        if not os.path.exists(io_path):
            continue

        with open(io_path) as f:
            io_data = json.load(f)

        inputs = io_data.get("inputs", [])
        outputs = io_data.get("outputs", [])

        if not inputs or len(inputs) != len(outputs):
            continue

        total += 1

        pass_flag = False

        # ====== 核心：5个结果 ======
        for i in range(K):
            file_path = os.path.join(task_path, f"{i}.json")

            if not os.path.exists(file_path):
                continue

            with open(file_path) as f:
                data = json.load(f)

            code = data.get("completion", "")

            if check_correct(code, inputs, outputs):
                pass_flag = True
                break

        if pass_flag:
            passed += 1

    return total, passed

# ========= 主函数 =========
def main():
    stats = {}

    print("🚀 开始评测 Pass@5...\n")

    for split in ["introductory", "interview", "competition"]:
        total, passed = eval_split(split)
        stats[split] = (total, passed)

    print("\n" + "="*50)
    print("🏆 Pass@5 结果 🏆")
    print("="*50)

    for split in ["introductory", "interview", "competition"]:
        total, passed = stats[split]
        rate = (passed / total * 100) if total > 0 else 0
        print(f"{split.ljust(15)}: {passed}/{total}  ->  {rate:.2f}%")

    print("="*50)

if __name__ == "__main__":
    main()