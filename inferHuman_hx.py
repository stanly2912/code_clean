# Human_infer_hx.py
import os
import sys
import json
import re
import time 
import argparse
import torch # 移到最外层
from tqdm import tqdm
from openai import OpenAI
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer # 移到最外层

sys.path.insert(0, "/home/wangbn/code_clean/parser_code/")
try:
    import cut
except ImportError:
    pass

sys.path.append("/home/wangbn/code_clean")
try:
    from infClean import solve,system_prompt_general
except ImportError:
    print("警告: 无法从 /home/wangbn/code_clean 导入 infClean。如果运行 MAS 模式将会报错。")

def get_clean_code(raw_text, prompt_text=""):
    # ===== 彻底剔除 <think> ... </think> 思考过程 =====
    # 正则匹配并删除成对的 think 标签及其中间的所有内容
    raw_text = re.sub(r'<think>.*?</think>', '', raw_text, flags=re.DOTALL)
    # 如果因为 max_tokens 不够长导致被截断，没有输出 </think>，把多余的 <think> 也删掉
    raw_text = raw_text.replace('<think>', '').strip()
    # ===========================================================

    pattern = re.compile(r'```(?:python)?(.*?)```', re.IGNORECASE | re.DOTALL)
    match = pattern.search(raw_text)
    if match:
        code = match.group(1).strip()
    elif "```" in raw_text:
        parts = raw_text.split("```")
        if len(parts) >= 2:
            code = parts[-2].strip()
    else:
        code = raw_text.strip()
        
    if not code.startswith("def ") and not code.startswith("import ") and prompt_text:
        code = prompt_text + "\n" + code
        
    return code
def build_messages(question):
    return [
        {"role": "system", "content": system_prompt_general},
        {"role": "user", "content": question+system_prompt_general}
    ]

def main():
    parser = argparse.ArgumentParser(description="HumanEval Code Generation")
    parser.add_argument("--mode", type=str, choices=["local", "online", "MAS"], default="MAS")
    parser.add_argument("--output_path", type=str, default="/home/wangbn/HumanEval_results")
    parser.add_argument("--model_path", type=str, default="")
    parser.add_argument("--online_model", type=str, default="Llama-3-8b-chat-hf")
    parser.add_argument("--api_url", type=str, default="https://api.agicto.cn/v1")
    parser.add_argument("--api_key", type=str, default="sk-88UT5OLYRw6so66EliV7rNFI4Y9oblR1Lns3dKNjwXABVtk7")
    parser.add_argument("--mas_history_file", type=str, default="")
    parser.add_argument("--k_samples", type=int, default=5)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--limit", type=int, default=164)

    args = parser.parse_args()
    
    MODE = args.mode
    OUTPUT_PATH = args.output_path
    LOCAL_MODEL_PATH = args.model_path
    TARGET_LIMIT = args.limit

    model = None
    tokenizer = None
    client = None
    client_tune = None
    client_base = None

    if MODE == "local":
        print(f"加载大模型到 GPU... (路径: {LOCAL_MODEL_PATH})")
        tokenizer = AutoTokenizer.from_pretrained(LOCAL_MODEL_PATH, trust_remote_code=True)
        if tokenizer.chat_template is None:
            tokenizer.chat_template = "{% for message in messages %}{{'<|im_start|>' + message['role'] + '\n' + message['content'] + '<|im_end|>' + '\n'}}{% endfor %}{% if add_generation_prompt %}{{ '<|im_start|>assistant\n' }}{% endif %}"
        model = AutoModelForCausalLM.from_pretrained(
            LOCAL_MODEL_PATH, device_map="auto", torch_dtype=torch.bfloat16, trust_remote_code=True
        ).eval()
        
    elif MODE == "online":
        client = OpenAI(api_key=args.api_key, base_url=args.api_url)
        
    elif MODE == "MAS":
        client_base = OpenAI(api_key="0", base_url="http://0.0.0.0:6001/v1")
        client_tune = OpenAI(api_key="0", base_url="http://0.0.0.0:7001/v1")
        
        original_codes = {}
        print("mas_history_file=",args.mas_history_file)
        if args.mas_history_file and os.path.exists(args.mas_history_file):
            with open(args.mas_history_file, "r", encoding="utf-8") as f:
                generations = [json.loads(line) for line in f if line.strip()]
            original_codes = {dic["task_id"]: cut.extract_codes(dic,ONLY_FUNCTION=False) for dic in generations}
        print("original_codes=",original_codes.keys())

    print("\n========== 读取本地 HumanEval 数据集 ==========")
    local_data_path = "/home/wangbn/code_clean/HumanEval.jsonl/human-eval-v2-20210705.jsonl"
    
    if not os.path.exists(local_data_path):
        print(f"致命错误: 找不到本地数据集 {local_data_path}，请确认是否上传成功且名字正确！")
        return
        
    dataset = []
    # 直接用普通的 open 读取
    with open(local_data_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                dataset.append(json.loads(line))
                
    print(f"成功加载本地数据，共 {len(dataset)} 题！")

    save_dir = os.path.join(OUTPUT_PATH, MODE)
    os.makedirs(save_dir, exist_ok=True)
    jsonl_path = os.path.join(save_dir, "humaneval_pass5.jsonl")
    
    # 【明确保证】：这里就是断点续传的读取逻辑
    completed_task_ids = set()
    if os.path.exists(jsonl_path):
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    completed_task_ids.add(json.loads(line)["task_id"])

    success_count = 0
    for item in tqdm(dataset, desc="进度"):
        if success_count >= TARGET_LIMIT:
            break
            
        task_id = item["task_id"]
        prompt_text = item["prompt"]
        
        # 【明确保证】：遇到跑过的，直接跳过
        if task_id in completed_task_ids:
            print(f"发现存档 {task_id}，跳过。")
            continue
            
        messages = build_messages(prompt_text)
        completions_list = [] 

        for sample_idx in range(args.k_samples):
            clean_code = ""
            
            if MODE == "online":
                max_retries = 5  # 最大重试次数
                for attempt in range(max_retries):
                    try:
                        response = client.chat.completions.create(
                            model=args.online_model, messages=messages, temperature=args.temperature
                        )
                        clean_code = get_clean_code(response.choices[0].message.content, prompt_text)
                        
                        # 成功请求到数据后，为了防止发得太快，强制休息 1 秒再发下一个
                        time.sleep(1) 
                        break  # 成功了就跳出重试循环
                        
                    except Exception as e:
                        error_str = str(e)
                        # 如果是 503(服务器忙) 或 429(请求太快) 错误，就等待重试
                        if "503" in error_str or "429" in error_str or "busy" in error_str.lower():
                            wait_time = 2 ** attempt  # 呈指数级等待：1秒, 2秒, 4秒, 8秒...
                            print(f"\n[API 平台拥挤] 被拦截，休息 {wait_time} 秒后进行第 {attempt+1} 次重试...")
                            time.sleep(wait_time)
                        else:
                            # 如果是其他严重错误（比如余额不足、秘钥填错），直接打印并跳过
                            print(f"\n[API 致命错误] Task {task_id}: {e}")
                            break
                
            elif MODE == "local":
                try:
                        text = tokenizer.apply_chat_template(
                            messages,
                            tokenize=False,
                            add_generation_prompt=True
                        )
                        model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

                        generated_ids = model.generate(
                            **model_inputs,
                            max_new_tokens=1024
                        )
                        generated_ids = [
                            output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
                        ]

                        response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]

                        # ===== 关键修复：调用 get_clean_code =====
                        clean_code = get_clean_code(response, prompt_text)
                        
                except Exception as e:
                        print(f"\n[Local GPU error] Task {task_id}: {e}")
                    
            elif MODE == "MAS":
                try:
                    original_code=""
                    if task_id in original_codes and len(original_codes[task_id]) >sample_idx>= 0:
                        original_code = original_codes[task_id][sample_idx]
                        print("original_code find")
                        
                    if original_code=="":
                        print("WARN:original_code not find",task_id,sample_idx)
                        if(0):
                            response = client_base.chat.completions.create(
                                model="default", messages=messages, temperature=args.temperature
                            )
                            original_code = get_clean_code(response.choices[0].message.content, prompt_text)
                            print("original_code generate")

                    if(original_code==""):
                        print("WARN:original_code empty",task_id,sample_idx)
                        clean_code=""
                    else:
                        raw_clean_code = solve(client_base, client_tune, model="default", task_description=prompt_text,original_code=original_code)
                        clean_code = get_clean_code(raw_clean_code, prompt_text)

                        
                except Exception as e:
                    print(f"\n[MAS error] Task {task_id}: {e}")
                    clean_code = ""
            print("clean_code=",clean_code)
            completions_list.append(clean_code)


        if completions_list:
            result = {"task_id": task_id, "completions": completions_list}
            # 【明确保证】： "a" 模式代表追加！
            with open(jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
                
            success_count += 1
            completed_task_ids.add(task_id)

if __name__ == "__main__":
    main()