import os
import json

INPUT_DIR = "/home/wangbn/code_clean/outputs"
OUT_FILE = "/home/wangbn/code_clean/apps_results.jsonl"

def convert():
    with open(OUT_FILE, "w") as out:
        for diff in ["introductory", "interview", "competition"]:
            folder = os.path.join(INPUT_DIR, diff)

            for file in os.listdir(folder):
                path = os.path.join(folder, file)

                with open(path) as f:
                    data = json.load(f)

                out.write(json.dumps(data) + "\n")

if __name__ == "__main__":
    convert()