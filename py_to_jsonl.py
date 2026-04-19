import os
import json
import glob

# 我们要转换的三个文件夹路径
BASE_DIR = "/home/wangbn/apps_clean_code/Qwen2.5-Coder-7B-Instruct"
splits = ["introductory", "interview", "competition"]

for split in splits:
    folder_path = os.path.join(BASE_DIR, split)
    if not os.path.exists(folder_path):
        continue
        
    output_file = os.path.join(BASE_DIR, f"{split}_packed.jsonl")
    
    # 获取所有的 .py 文件
    py_files = glob.glob(os.path.join(folder_path, "*.py"))
    if not py_files:
        continue
        
    with open(output_file, 'w', encoding='utf-8') as f_out:
        for py_file in py_files:
            with open(py_file, 'r', encoding='utf-8') as f_in:
                code_text = f_in.read()
            
            # 【暴力破解格式】为了防止 calc_atts.py 找不到字段，我们把常见的键名全塞进去！
            data = {
                "task_id": os.path.basename(py_file),
                "code": code_text,
                "completion": code_text,
                "generation": code_text,
                "solution": code_text
            }
            f_out.write(json.dumps(data) + "\n")
            
    print(f"打包完成: {output_file} (共 {len(py_files)} 题)")

