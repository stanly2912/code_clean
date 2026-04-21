import os
import json

BASE_DIR = "/home/wangbn/apps_pass5_DS/competition"

SPLITS = ["0040", "0041", "0042", "0043", "0044", "0045", "0046", "0047", "0048", "0049"]


def merge_folder(split):
    input_dir = os.path.join(BASE_DIR, split)
    output_file = os.path.join(BASE_DIR, f"{split}.jsonl")

    print(f"\n处理 {split} ...")

    files = [f for f in os.listdir(input_dir) if f.endswith(".json")]
    files.sort()  # 保证顺序稳定

    count = 0

    with open(output_file, "w", encoding="utf-8") as out:
        for file in files:
            path = os.path.join(input_dir, file)

            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # ✅ 保证字段存在
                task_id = data.get("task_id", file.replace(".json", ""))
                completion = data.get("completion", "")

                if not completion.strip():
                    continue

                record = {
                    "task_id": task_id,
                    "completion": completion
                }

                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1

            except Exception as e:
                print(f"跳过 {file}: {e}")

    print(f"{split} 完成，共写入 {count} 条")


if __name__ == "__main__":
    for split in SPLITS:
        merge_folder(split)

    print("\n全部完成 ✅")