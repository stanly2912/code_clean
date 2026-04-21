import os
import json
from datasets import Dataset
from typing import Dict, List
from openai import OpenAI

def load_apps_per_folder(
    split: str = "test",
    root_dir: str = "/home/wangbn/APPS",   # ← 你的 APPS 根目录
    verbose: bool = True
) -> Dataset:
    """
    加载每个问题一个文件夹的 APPS 数据集格式
    
    每个样本最终结构（dict）示例：
    {
        'question': str,                # 从 question.txt 读取
        'solutions': List[str],         # 从 solutions.json 读取
        'input_output': dict,           # 从 input_output.json 读取
        'metadata': dict,               # 从 metadata.json 读取
        'problem_id': str,              # 如 '0000'
        'difficulty': str               # 从 metadata 提取
    }
    """
    split_dir = os.path.join(os.path.expanduser(root_dir), split)
    if not os.path.isdir(split_dir):
        raise FileNotFoundError(f"split 目录不存在: {split_dir}")

    all_samples: List[Dict] = []
    problem_folders = [f for f in os.listdir(split_dir) 
                       if os.path.isdir(os.path.join(split_dir, f)) and f.isdigit()]

    if verbose:
        print(f"[load_apps_per_folder][{split}] 找到 {len(problem_folders)} 个问题文件夹")

    for prob_id in sorted(problem_folders):  # 按数字排序，便于复现
        folder = os.path.join(split_dir, prob_id)
        
        sample = {'problem_id': prob_id,"solutions":"[]","input_output":"\{\}",
                  "starter_code":""}
        
        # 1. question.txt
        q_path = os.path.join(folder, 'question.txt')
        if os.path.isfile(q_path):
            with open(q_path, 'r', encoding='utf-8') as f:
                sample['question'] = f.read().strip()
        else:
            print(f"警告: {folder} 缺少 question.txt")
            continue
        
        # 2. solutions.json
        sol_path = os.path.join(folder, 'solutions.json')
        if os.path.isfile(sol_path):
            with open(sol_path, 'r', encoding='utf-8') as f:
                sample['solutions'] = f.read()
        
        # 3. input_output.json
        io_path = os.path.join(folder, 'input_output.json')
        if os.path.isfile(io_path):
            with open(io_path, 'r', encoding='utf-8') as f:
                sample['input_output'] = f.read()
        
        # 4. metadata.json (可选，难度等信息在这里)
        meta_path = os.path.join(folder, 'metadata.json')
        if os.path.isfile(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
                sample['metadata'] = meta
                sample['difficulty'] = meta.get('difficulty', 'Unknown')
        else:
            sample['metadata'] = {}
            sample['difficulty'] = 'Unknown'
        
        all_samples.append(sample)

    if not all_samples:
        raise ValueError(f"没有有效样本 from {split_dir}")

    print("[load_apps_per_folder] OK")
    return all_samples


    dataset = Dataset.from_list(all_samples)
    
    if verbose:
        print(f"加载完成：{len(dataset)} 条样本 (split={split})")
        if len(dataset) > 0:
            print("样本字段示例:", list(dataset[0].keys()))
            print("难度分布:", dict(dataset.features['difficulty']._counter_value))
    
    return dataset


client_base = OpenAI(api_key="0", base_url="http://0.0.0.0:6001/v1")
client_tune = OpenAI(api_key="0", base_url="http://0.0.0.0:7001/v1")


def infer_once_demo(inp="User: Here is the original code. Please provide a cleaner, more concise version of this code following clean code principles\n@Override\n  public void close()\n  {\n    if (stringBufferMapper != null) {\n      stringBufferMapper.close();\n      deleteTempFile(stringDictionaryFile);\n    }\n    if (longBuffer != null) {\n      ByteBufferUtils.unmap(longBuffer);\n      deleteTempFile(longDictionaryFile);\n    }\n    if (doubleBuffer != null) {\n      ByteBufferUtils.unmap(doubleBuffer);\n      deleteTempFile(doubleDictionaryFile);\n    }\n    if (arrayBuffer != null) {\n      ByteBufferUtils.unmap(arrayBuffer);\n      deleteTempFile(arrayDictionaryFile);\n    }\n  }\n\nAssistant:"):
    instruction="please give the python code to solve the question directly, no more useless output,dont output your thinking proccess.\n"
    messages = [{"role": "user", "content":instruction+  inp}
    #,{"role": "system", "content": "please give the python code to solve the question"}
    ]
    result = client.chat.completions.create(messages=messages, model="deepseek")
    ret=result.choices[0].message.content
    print("[infer_once]",messages,ret)
    return ret


import sys

sys.path.append("/home/wangbn/code_clean")
from infClean import solve

def infer_once_out(inp=""):
    global client_base, client_tune
    
    return solve(client_base, client_base, model="default", user_prompt=inp)
    

def infer_once(inp="User: Here is the original code. Please provide a cleaner, more concise version of this code following clean code principles\n@Override\n  public void close()\n  {\n    if (stringBufferMapper != null) {\n      stringBufferMapper.close();\n      deleteTempFile(stringDictionaryFile);\n    }\n    if (longBuffer != null) {\n      ByteBufferUtils.unmap(longBuffer);\n      deleteTempFile(longDictionaryFile);\n    }\n    if (doubleBuffer != null) {\n      ByteBufferUtils.unmap(doubleBuffer);\n      deleteTempFile(doubleDictionaryFile);\n    }\n    if (arrayBuffer != null) {\n      ByteBufferUtils.unmap(arrayBuffer);\n      deleteTempFile(arrayDictionaryFile);\n    }\n  }\n\nAssistant:"):
    ret=infer_once_out(inp)
    print("[infer_once] ret=",ret)
    return ret


def load_dataset(path,split):
    print("[load_dataset]",path,split)
    path_="/home/wangbn/APPS"
    split_="test"
    problems = load_apps_per_folder(
        split=split_,                # "test" 或 "train"
        root_dir=path_    # 你的实际路径
    )
    s="problems{}".format(split[4::])
    print("[load_dataset] s",s)
    problems=eval(s)
    return problems

# ================== 在你的脚本中使用 ==================
# 替换原来的加载代码，例如：
# problems = load_from_disk(...)   或   load_dataset(...)

problems = load_apps_per_folder(
    split="test",                # "test" 或 "train"
    root_dir="/home/wangbn/APPS"     # 你的实际路径
)

# 后续访问示例（兼容大多数 APPS 评测脚本）：
# problem = problems[0]
# print(problem['question'][:200])
# print("参考解数量:", len(problem['solutions']))
# print("难度:", problem['difficulty'])