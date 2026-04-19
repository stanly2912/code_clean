import os
import sys
import json
import time
import re
import argparse
import ast
from tqdm import tqdm
from openai import OpenAI

# 确保能够找到依赖模块
sys.path.insert(0, "/home/wangbn/code_clean/parser_code/")
import cut

sys.path.append("/home/wangbn/code_clean")
try:
    from infClean import solve, system_prompt_general
except ImportError:
    print("警告: 无法从 /home/wangbn/code_clean 导入 infClean。如果运行 API/MAS 模式将会报错。")

# ==========================================
# 基础配置
# ==========================================
SPOC_PATH = "/home/wangbn/code_clean/spoc/"
OUTPUT_PATH = "/home/wangbn/code_clean/infer_results_jzy"

API_KEY = "sk-88UT5OLYRw6so66EliV7rNFI4Y9oblR1Lns3dKNjwXABVtk7"
BASE_URL = "https://api.agicto.cn/v1"
ONLINE_MODEL = "Llama-3-8b-chat-hf"

K_SAMPLES = 5
TEMPERATURE = 0.7


def get_clean_code(raw_text):
    """统一的代码提取清洗函数"""
    pattern = re.compile(r'```(?:python)?(.*?)```', re.IGNORECASE | re.DOTALL)
    match = pattern.search(raw_text or "")
    if match:
        return match.group(1).strip()
    if "```" in (raw_text or ""):
        parts = raw_text.split("```")
        if len(parts) >= 2:
            return parts[-2].strip()
    return (raw_text or "").strip()


def build_messages(question):
    """SPOC 的消息构造。不要重复拼接 system prompt，避免长度膨胀。"""
    system_text = (
        "You are an expert competitive programmer. "
        "Translate pseudocode into a complete, runnable Python 3 program. "
        "Output only Python code. Do not include explanations."
    )
    return [
        {"role": "system", "content": system_text},
        {"role": "user", "content": question},
    ]


def has_usable_chat_template(tokenizer):
    template = getattr(tokenizer, "chat_template", None)
    return isinstance(template, str) and template.strip() != ""


def is_chat_model(model_path):
    model_name = os.path.basename(str(model_path)).lower()
    chat_keywords = ["chat", "instruct", "assistant"]
    return any(k in model_name for k in chat_keywords)


def inject_default_chat_template(tokenizer):
    tokenizer.chat_template = (
        "{% for message in messages %}"
        "{{'<|im_start|>' + message['role'] + '\n' + message['content'] + '<|im_end|>' + '\n'}}"
        "{% endfor %}"
        "{% if add_generation_prompt %}{{ '<|im_start|>assistant\n' }}{% endif %}"
    )


def build_local_prompt(question, messages, tokenizer, use_chat_template, force_strict=False):
    """
    参考 APPS_infer_hx.py 的 local 部分：
    - chat/instruct 模型走 apply_chat_template
    - base 模型走 completion prompt，避免生成空格/伪代码续写
    """
    if use_chat_template:
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

    if force_strict:
        instruction = (
            "Output only valid Python 3 code. "
            "No English explanation. No pseudocode. No markdown fence.\n\n"
        )
    else:
        instruction = (
            "Translate the following pseudocode into a complete runnable Python 3 program.\n"
            "Requirements:\n"
            "- Output code only\n"
            "- Use standard input/output\n"
            "- The answer must be valid Python 3 syntax\n"
            "- Do not explain anything\n\n"
        )

    return (
        instruction
        + "Pseudocode:\n"
        + question
        + "\n\nPython 3 code:\n"
    )


def is_valid_python(code: str) -> bool:
    code = (code or "").strip()
    if not code:
        return False
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def main():
    global SPOC_PATH, OUTPUT_PATH, API_KEY, BASE_URL, ONLINE_MODEL, K_SAMPLES, TEMPERATURE

    parser = argparse.ArgumentParser(description="SPOC Code Generation")
    parser.add_argument("--mode", type=str, choices=["local", "online", "API", "MAS"], default="API", help="运行模式")
    parser.add_argument("--output_path", type=str, default=OUTPUT_PATH, help="结果保存的根目录")
    parser.add_argument("--spoc_path", type=str, default=SPOC_PATH, help="SPOC 数据集路径")
    parser.add_argument("--model_path", type=str, default="/home/wangbn/7B_model/qwen/Qwen2_5-Coder-7B-base", help="Local模式模型路径")
    parser.add_argument("--online_model", type=str, default=ONLINE_MODEL, help="Online模式模型名称")
    parser.add_argument("--api_url", type=str, default=BASE_URL, help="Online模式 API URL")
    parser.add_argument("--api_key", type=str, default=API_KEY, help="Online模式 API Key")
    parser.add_argument("--test_limit", type=int, default=50, help="测试数量限制")
    parser.add_argument("--k_samples", type=int, default=5, help="Pass@K 的 K 值")
    parser.add_argument("--temperature", type=float, default=0.7, help="生成温度")
    parser.add_argument("--max_new_tokens", type=int, default=512, help="本地生成的最大新 token 数")

    args = parser.parse_args()

    MODE = args.mode
    OUTPUT_PATH = args.output_path
    SPOC_PATH = args.spoc_path
    ONLINE_MODEL = args.online_model
    BASE_URL = args.api_url
    API_KEY = args.api_key
    K_SAMPLES = args.k_samples
    TEMPERATURE = args.temperature
    TEST_LIMIT = args.test_limit

    print(f"========== 当前运行模式: {MODE.upper()} | 目标: Pass@{K_SAMPLES} (Temp: {TEMPERATURE}) ==========")
    print(f"输出目录: {OUTPUT_PATH}")

    model = None
    tokenizer = None
    client = None
    client_tune = None
    client_base = None
    use_chat_template = False

    if MODE == "local":
        print(f"正在加载本地模型到 GPU... (路径: {args.model_path})")
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(args.model_path, trust_remote_code=True)

        # 参考 APPS_infer_hx.py：缺失模板时先补一个标准 ChatML 模板。这里只作为 chat 模型兜底。
        if not has_usable_chat_template(tokenizer):
            print("警告：未检测到 chat_template，正在手动注入默认 ChatML 模板...")
            inject_default_chat_template(tokenizer)

        model = AutoModelForCausalLM.from_pretrained(
            args.model_path,
            device_map="auto",
            torch_dtype=torch.bfloat16,
            trust_remote_code=True,
        ).eval()

        model.config.use_cache = False
        if hasattr(model, "generation_config") and model.generation_config is not None:
            model.generation_config.use_cache = False

        if tokenizer.pad_token_id is None:
            if tokenizer.eos_token is not None:
                tokenizer.pad_token = tokenizer.eos_token
            elif tokenizer.unk_token is not None:
                tokenizer.pad_token = tokenizer.unk_token

        # 只对 chat/instruct 模型启用 chat_template；base 模型仍然走纯文本 prompt。
        use_chat_template = is_chat_model(args.model_path)
        if use_chat_template:
            print("检测到 chat/instruct 模型，本地分支将使用 chat_template 推理。")
        else:
            print("检测到 base 模型，本地分支将使用纯文本 prompt 推理。")

        print("本地模型加载完毕！")

    elif MODE == "online":
        print(f"初始化 Online API (Model: {ONLINE_MODEL}, URL: {BASE_URL})...")
        client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    elif MODE == "API" or MODE == "MAS":
        print(f"初始化 {MODE} 双路系统客户端 (接入本地 vLLM 端口)...")
        client_base = OpenAI(api_key="0", base_url="http://0.0.0.0:6001/v1")
        client_tune = OpenAI(api_key="0", base_url="http://0.0.0.0:7001/v1")

        file_paths = [
            r"/home/wangbn/infer_results_jzy/SPOC_results/local/spoc_test_pass5.jsonl"
        ]
        original_codes = {}
        for file_path in file_paths:
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            dic = json.loads(line)
                            original_codes[dic["task_id"]] = dic["completions"]
        print(f"加载了 {len(original_codes)} 个 original_codes 记录")

    print("\n========== 开始读取 SPOC 数据 ==========")
    import pandas as pd

    tsv_filename = "spoc-testp.tsv"
    tsv_path = os.path.join(SPOC_PATH, "test", tsv_filename)

    if not os.path.exists(tsv_path):
        print(f"错误: 未找到文件 {tsv_path}")
        return

    df = pd.read_csv(tsv_path, sep="\t", dtype=str)
    unique_problems = {}

    for _, row in df.iterrows():
        probid = str(row["probid"])
        if probid in unique_problems:
            continue
        group = df[df["probid"] == row["probid"]].sort_values("line")
        pseudo_lines = group["text"].fillna("").tolist()
        unique_problems[probid] = "\n".join(pseudo_lines)

    all_ids = list(unique_problems.keys())
    print(f"成功加载数据集，共找到 {len(all_ids)} 个唯一 probid")

    save_dir = os.path.join(OUTPUT_PATH, MODE)
    os.makedirs(save_dir, exist_ok=True)
    jsonl_path = os.path.join(save_dir, "spoc_test_pass5.jsonl")

    completed_task_ids = set()
    if os.path.exists(jsonl_path):
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    completed_task_ids.add(json.loads(line)["task_id"])

    success_count = 0
    for task_id in tqdm(all_ids, desc="SPOC 测试进度"):
        if success_count >= TEST_LIMIT:
            break
        if task_id in completed_task_ids:
            continue

        question_text = unique_problems[task_id]
        messages = build_messages(question_text)
        completions_list = []

        for sample_idx in range(K_SAMPLES):
            time.sleep(0.1)
            clean_code = ""

            if MODE == "online":
                try:
                    response = client.chat.completions.create(
                        model=ONLINE_MODEL, messages=messages, temperature=TEMPERATURE
                    )
                    clean_code = get_clean_code(response.choices[0].message.content)
                except Exception as e:
                    print(f"\n[API error] Task {task_id}: {e}")

            elif MODE == "local":
                try:
                    max_ctx = getattr(tokenizer, "model_max_length", 4096)
                    if not isinstance(max_ctx, int) or max_ctx <= 0 or max_ctx > 100000:
                        max_ctx = 4096
                    max_new = args.max_new_tokens
                    max_input_len = max(512, max_ctx - max_new)
                    input_device = next(model.parameters()).device

                    # 第一个样本用 greedy，后面用采样，提高 pass@5 的多样性。
                    for retry_idx in range(2):
                        prompt_text = build_local_prompt(
                            question=question_text,
                            messages=messages,
                            tokenizer=tokenizer,
                            use_chat_template=use_chat_template,
                            force_strict=(retry_idx > 0),
                        )

                        model_inputs = tokenizer(
                            [prompt_text],
                            return_tensors="pt",
                            truncation=True,
                            max_length=max_input_len,
                        )
                        model_inputs = {k: v.to(input_device) for k, v in model_inputs.items()}

                        if sample_idx == 0:
                            generate_kwargs = {
                                "max_new_tokens": max_new,
                                "do_sample": False,
                                "repetition_penalty": 1.1,
                                "pad_token_id": tokenizer.pad_token_id,
                            }
                        else:
                            generate_kwargs = {
                                "max_new_tokens": max_new,
                                "do_sample": True,
                                "temperature": max(TEMPERATURE, 0.8),
                                "top_p": 0.95,
                                "repetition_penalty": 1.1,
                                "pad_token_id": tokenizer.pad_token_id,
                            }

                        if tokenizer.eos_token_id is not None:
                            generate_kwargs["eos_token_id"] = tokenizer.eos_token_id

                        with torch.no_grad():
                            generated_ids = model.generate(**model_inputs, **generate_kwargs)

                        prompt_len = model_inputs["input_ids"].shape[1]
                        new_tokens = generated_ids[0][prompt_len:]
                        response = tokenizer.decode(new_tokens.cpu(), skip_special_tokens=True)
                        clean_code = get_clean_code(response).strip()

                        if not clean_code:
                            full_output = tokenizer.decode(generated_ids[0].cpu(), skip_special_tokens=True)
                            if full_output.startswith(prompt_text):
                                response = full_output[len(prompt_text):]
                            else:
                                response = full_output
                            clean_code = get_clean_code(response).strip()

                        if is_valid_python(clean_code):
                            break

                    if not is_valid_python(clean_code):
                        clean_code = ""

                except Exception as e:
                    print(f"\n[Local GPU error] Task {task_id}: {e}")
                    clean_code = ""

            elif MODE == "API" or MODE == "MAS":
                try:
                    if task_id in original_codes:
                        A = original_codes[task_id]
                        original_code = A[sample_idx % len(A)]
                    else:
                        response = client_base.chat.completions.create(
                            model="default", messages=messages, temperature=TEMPERATURE
                        )
                        original_code = get_clean_code(response.choices[0].message.content)

                    user_prompt = f"'''\n{question_text}'''\n{original_code}"
                    clean_code = solve(client_base, client_tune, model="default", user_prompt=user_prompt)
                    clean_code = get_clean_code(clean_code)
                except Exception as e:
                    print(f"\n[API mode error] Task {task_id}: {e}")
                    clean_code = ""

            completions_list.append(clean_code)

        if completions_list:
            result = {
                "task_id": task_id,
                "completions": completions_list
            }
            with open(jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")

            success_count += 1
            completed_task_ids.add(task_id)

    print(f"测试已完成。文件保存在: {jsonl_path}")


if __name__ == "__main__":
    main()
