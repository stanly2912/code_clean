#APPS_infer_hx.py
import os
import sys
import json
import time
import re
import argparse
from tqdm import tqdm
from openai import OpenAI
import traceback
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


sys.path.insert(0, "/home/wangbn/code_clean/parser_code/")
import cut

#==========================================
#导入MAS 模块
#==========================================
#确保能够找到 infClean 模块

sys.path.append("/home/wangbn/code_clean")
try:
  from infClean import solve,system_prompt_general
except ImportError:
  print("警告: 无法从 /home/wangbn/code_clean 导入 infClean。如果运行 MAS 模式将会报错。")

#==========================================
#基础配置
#==========================================

APPS_PATH = "/home/wangbn/APPS/test"
OUTPUT_PATH = "/home/wangbn/APPS_results/apps_7results2"

#每种难度的测试题数限制
TARGET_LIMITS = {
"introductory": 2,
"interview": 2,
"competition": 2
}

#API & 模型配置
#API_KEY = "sk_VrZ4jhQDLWUK2lyQj40u5yr6p5Uq1lLpnQ4Cxh_BnUY"
API_KEY = "sk-88UT5OLYRw6so66EliV7rNFI4Y9oblR1Lns3dKNjwXABVtk7"
BASE_URL = "https://api.agicto.cn/v1"
ONLINE_MODEL = "Llama-3-8b-chat-hf"

#只跑 pass@5，温度设为 0.7 增加代码多样性
K_SAMPLES = 5
TEMPERATURE = 0.7


def get_clean_code(raw_text):
    """统一的代码提取清洗函数 (正则提取Markdown代码块)"""
    pattern = re.compile(r'(?:python)?(.*?)', re.IGNORECASE | re.DOTALL)
    match = pattern.search(raw_text)

    if match:
        return match.group(1).strip()
    if "```" in raw_text:
        parts = raw_text.split("```")
    if len(parts) >= 2:
        return parts[-2].strip()
    return raw_text.strip()

def build_messages(question):
    """统一 Prompt 格式，保证实验条件严格一致"""
    ret= [
        {
            "role": "system",
            "content": system_prompt_general
        },
        {
            "role": "user",
            "content": question + system_prompt_general
        }
    ]
    print("[build_messages]",ret)
    return ret


def main():
    global APPS_PATH, OUTPUT_PATH, TARGET_LIMITS, API_KEY, BASE_URL, ONLINE_MODEL, K_SAMPLES, TEMPERATURE
    parser = argparse.ArgumentParser(description="APPS Code Generation for Table VI")
    parser.add_argument("--mode", type=str, choices=["local", "online", "MAS"], default="MAS", help="运行模式 (推荐 MAS)")
    parser.add_argument("--output_path", type=str, default=OUTPUT_PATH, help="结果保存的根目录")
    parser.add_argument("--apps_path", type=str, default=APPS_PATH, help="APPS 数据集路径")
    parser.add_argument("--model_path", type=str, default="/home/wangbn/7B_model/qwen/Qwen2_5-Coder-7B-base", help="Local模式下的本地模型路径")
    parser.add_argument("--online_model", type=str, default=ONLINE_MODEL, help="Online模式下的模型名称")
    parser.add_argument("--api_url", type=str, default=BASE_URL, help="Online模式下的 API URL")
    parser.add_argument("--api_key", type=str, default=API_KEY, help="Online模式下的 API Key")

    # 每种难度的题目数量限制
    parser.add_argument("--introductory", type=int, default=50, help="Introductory 难度测试数量")
    parser.add_argument("--interview", type=int, default=50, help="Interview 难度测试数量")
    parser.add_argument("--competition", type=int, default=50, help="Competition 难度测试数量")

    # 其他超参
    parser.add_argument("--k_samples", type=int, default=5, help="Pass@K 的 K 值")
    parser.add_argument("--temperature", type=float, default=0.7, help="生成温度")

    args = parser.parse_args()

    # 更新全局配置
    MODE = args.mode
    OUTPUT_PATH = args.output_path
    APPS_PATH = args.apps_path
    ONLINE_MODEL = args.online_model
    BASE_URL = args.api_url
    API_KEY = args.api_key
    K_SAMPLES = args.k_samples
    TEMPERATURE = args.temperature

    TARGET_LIMITS = {
    "introductory": args.introductory,
    "interview": args.interview,
    "competition": args.competition
    }

    print(f"========== 当前运行模式: {MODE.upper()} | 目标: Pass@{K_SAMPLES} (Temperature: {TEMPERATURE}) ==========")
    print(f"输出目录: {OUTPUT_PATH}")
    print(f"测试数量限制: {TARGET_LIMITS}")

    # ==========================================
    # 严格遵循格式的初始化模块
    # ==========================================
    model = None
    client = None
    client_tune = None
    client_base = None

    if MODE == "local":
        print(f"正在将大模型加载到 GPU 中，请稍候... (路径: {args.model_path})")
        LOCAL_MODEL_PATH = args.model_path # 使用 args 传进来的路径
        tokenizer = AutoTokenizer.from_pretrained(LOCAL_MODEL_PATH, trust_remote_code=True)

# 👇 新增这块代码：如果没有模板，强制分配一个标准的 Qwen ChatML 模板
        if tokenizer.chat_template is None:
          print("警告：未检测到 chat_template，正在手动注入默认 ChatML 模板...")
          tokenizer.chat_template = "{% for message in messages %}{{'<|im_start|>' + message['role'] + '\n' + message['content'] + '<|im_end|>' + '\n'}}{% endfor %}{% if add_generation_prompt %}{{ '<|im_start|>assistant\n' }}{% endif %}"
# 👆 新增结束


        model = AutoModelForCausalLM.from_pretrained(
            LOCAL_MODEL_PATH, device_map="auto", torch_dtype=torch.bfloat16, trust_remote_code=True
        ).eval()
        print("加载完毕！显卡已准备就绪。")
    
    elif MODE == "online":
        print(f"正在初始化 Online API 客户端 (Model: {ONLINE_MODEL}, URL: {BASE_URL})...")
        client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
        print("API 客户端初始化完成。")
    
    elif MODE == "MAS":
        print("正在初始化 MAS 多智能体系统客户端 (接入本地 vLLM 端口)...")
        # MAS 模式的配置暂未通过 args 完全开放，可根据需要后续添加
        client_base = OpenAI(api_key="0", base_url="http://0.0.0.0:6001/v1")
        client_tune = OpenAI(api_key="0", base_url="http://0.0.0.0:7001/v1")
        file_paths=[
        #    r"/home/wangbn/infer_results_hx/APPS_results/QW_coder_7B_Base/local/competition_pass5.jsonl",
        #    r"/home/wangbn/infer_results_hx/APPS_results/QW_coder_7B_Base/local/interview_pass5.jsonl",
        #    r"/home/wangbn/infer_results_hx/APPS_results/QW_coder_7B_Base/local/introductory_pass5.jsonl",
        ]
    
        original_codes={}
        for file_path in file_paths:
            generations = []
            if os.path.exists(file_path): # 增加文件存在性检查，防止报错
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            generations.append(json.loads(line))
                A={dic["task_id"]:dic["completions"] for dic in generations}
                original_codes.update(A)
            else:
                print(f"ERR: 找不到历史结果文件 {file_path}")
            
        print(f"加载了 {len(original_codes)} 个 original_codes 记录",original_codes.keys())
        print("MAS 初始化完成。")

# ==========================================
# 任务生成主循环
# ==========================================
# ... [保留原有的主循环部分，不需要修改] ...
    print("\n========== 开始读取本地 APPS 数据 ==========")
    all_ids = [d for d in os.listdir(APPS_PATH) if d.isdigit() and os.path.isdir(os.path.join(APPS_PATH, d))]


    all_ids = sorted(all_ids, key=int)
    splits = ["introductory", "interview", "competition"]

    for split_name in splits:
        print(f"\n>>>>>>>> 正在全力生成难度: {split_name.upper()} <<<<<<<<")
    
        # 结果保存目录
        save_dir = os.path.join(OUTPUT_PATH, MODE)
        os.makedirs(save_dir, exist_ok=True)
        
        # 输出单个 JSONL 文件
        jsonl_path = os.path.join(save_dir, f"{split_name}_pass5.jsonl")
        
        # ---------------- 断点续传逻辑 ----------------
        completed_task_ids = set()
        if os.path.exists(jsonl_path):
            with open(jsonl_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        completed_task_ids.add(json.loads(line)["task_id"])
    
        # ----------------------------------------------
        success_count=0
        for task_id in tqdm(all_ids, desc=f"{split_name} 进度"):
            if success_count >= TARGET_LIMITS[split_name]:
                break
            
            if task_id in completed_task_ids:
                print("发现存档",task_id)
                if(1):
                    print("跳过")
                    continue
                else:
                    print("追加")

            task_path = os.path.join(APPS_PATH, task_id)
            meta_file = os.path.join(task_path, "metadata.json")
            question_file = os.path.join(task_path, "question.txt")
            
            if not os.path.exists(meta_file) or not os.path.exists(question_file): 
                continue
            
            with open(meta_file, 'r', encoding='utf-8') as f:
                if json.load(f).get('difficulty') != split_name:
                    continue
    
            with open(question_file, 'r', encoding='utf-8') as f:
                question_text = f.read()
            
            messages = build_messages(question_text)
            completions_list = [] # 用于存放当前题目生成的 5 个代码样本

            # 针对每个题目生成 5 次
            for sample_idx in range(K_SAMPLES):
                time.sleep(0.1)
                clean_code = ""
                print("sample_idx=",sample_idx)
                
                if MODE == "online":
                    try:
                        response = client.chat.completions.create(
                            model=ONLINE_MODEL, messages=messages, temperature=TEMPERATURE
                        )
                        print("response=",response)
                        clean_code = get_clean_code(response.choices[0].message.content)
                    except Exception as e:
                        print(f"\n[API error] Task {task_id}: {e}")
                    
                elif MODE == "local":
                    try:
                        text = tokenizer.apply_chat_template(
                            messages,
                            tokenize=False,
                            add_generation_prompt=True
                        )
                        model_inputs = tokenizer([text], return_tensors="pt").to(model.    device)
    
                        generated_ids = model.generate(
                            **model_inputs,
                            max_new_tokens=1024*8,
                            repetition_penalty=1.1,
                            do_sample=True,
                            pad_token_id=tokenizer.eos_token_id,
                            temperature=args.temperature
                        )
    
                        generated_ids = [
                            output_ids[len(input_ids):] for input_ids, output_ids in zip    (model_inputs.input_ids, generated_ids)
                        ]
    
                        response = tokenizer.batch_decode(generated_ids,     skip_special_tokens=True)[0]
                        clean_code=response
                    except Exception as e:
                        print(f"\n[Local GPU error] Task {task_id}: {e}")
                        
                elif MODE == "MAS":
                    """
                    try:
                        # 调用 solve 函数
                        # user_prompt 传入原始题目文本
                        print("[MAS] task_id=",task_id)
                        #original_code
                        if task_id in original_codes:
                            A=original_codes[task_id]
                            original_code=A[sample_idx%len(A)]
                            print("[MAS] find original_code")
                        else:
                            
                            print("[MAS]  ERROR not find original_code")
                            response = client_base.chat.completions.create(
                                model="default",messages=messages, temperature=TEMPERATURE
                            )
                            original_code = get_clean_code(response.choices[0].message.    content)
    
                        if(0):
                            clean_code=original_code
                        else:
                            user_prompt="\'\'\'\n{}\'\'\'\n{}".format(question_text,    original_code)
                            clean_code = solve(client_base, client_tune, model="default",     user_prompt=user_prompt)
                            
                            # 如果学长的 solve 函数返回的是包含 markdown 的粗糙文本，可以在这里    加一句: 
                            clean_code = get_clean_code(clean_code)
                    except Exception as e:
                        print(f"\n[MAS error] Task {task_id}: {e}")
                        clean_code = ""
                        """
    
    

                    
                    try:
                        original_code=""
                        if task_id in original_codes and len(original_codes[task_id])     >sample_idx>= 0:
                            original_code = original_codes[task_id][sample_idx]
                            print("original_code find")
                            
                        if original_code=="":
                            print("WARN:original_code not find",task_id,sample_idx)
                            if(1):
                                response = client_base.chat.completions.create(
                                    model="default", messages=messages, temperature=args.    temperature
                                )
                                original_code = get_clean_code(response.choices[0].message.    content)
                                print("original_code generate")
    
                        if(original_code==""):
                            print("WARN:original_code empty",task_id,sample_idx)
                            clean_code=""
                        else:
                            raw_clean_code = solve(client_base, client_tune,     model="default", task_description=question_text,    original_code=original_code)
                            clean_code = get_clean_code(raw_clean_code)
                            
                    except Exception as e:
                        print(f"\n[MAS error] Task {task_id}: {e}")
                        clean_code = ""
                
                print("clean_code=",clean_code)
                    
                completions_list.append(clean_code)

            # 将结果以 JSONL 格式追加写入文件
            if completions_list:
                result = {
                    "task_id": task_id,
                    "difficulty": split_name,
                    "completions": completions_list  # 包含 5 个元素的数组
                }
                #print("result=",result)
                with open(jsonl_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(result, ensure_ascii=False) + "\n")
                    
                success_count += 1
                completed_task_ids.add(task_id)

    print(f"[{split_name.upper()}] 难度已完成。文件保存在: {jsonl_path}")

if __name__ == "__main__":
    main ()