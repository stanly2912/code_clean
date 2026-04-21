import os
import sys
import json
import argparse  # 新增：用于接收 bash 传来的单文件路径
import subprocess
from datetime import datetime


sys.path.insert(0, "/home/wangbn/code_clean/parser_code/")
import cut

# ==========================================
# 1. 基础配置区
# ==========================================
OUTPUT_LOG_PATH = "/home/wangbn/infer_results_hx/eval_Human/10Humanbase_418.log"
EVAL_SCRIPT_DIR = "/home/wangbn/code_clean/human-eval/human_eval"
EVAL_SCRIPT_PATH = os.path.join(EVAL_SCRIPT_DIR, "evaluate_functional_correctness.py")
K_SAMPLES = 5

# 当没有接收到命令行参数时，默认跑这里面的文件
TARGET_FILES = [
    #"/home/wangbn/infer_results_hx/Human_results/mis7b_API/online/humaneval_pass5.jsonl",
    #"/home/wangbn/infer_results_hx/Human_results/QW_7B_Base/local/humaneval_pass5.jsonl",
    #"/home/wangbn/infer_results_hx/Human_results/QW_coder_7B_instruct/local/humaneval_pass5.jsonl",
    #"/home/wangbn/infer_results_hx/Human_results/qwen3-8B_API/online/humaneval_pass5.jsonl"
    "/home/wangbn/infer_results_hx/Human_results/qwen3-8B_API/online/humaneval_pass5.jsonl",
    "/home/wangbn/infer_results_hx/Human_results/mis7b_API/online/humaneval_pass5.jsonl",
    "/home/wangbn/infer_results_hx/Human_results/QW_coder_7B_Base/local/humaneval_pass5.jsonl",
    "/home/wangbn/infer_results_hx/Human_results/deepseek-coder-6.7b-instruct/local/humaneval_pass5.jsonl",
    "/home/wangbn/infer_results_hx/Human_results/dolphin-2.6-mistral-7b-dpo/local/humaneval_pass5.jsonl",
    "/home/wangbn/infer_results_hx/Human_results/hunyuan-7b/online/humaneval_pass5.jsonl"


]

def log_print(msg, file=None):
    print(msg)
    if file:
        file.write(msg + "\n")
        file.flush()

def prepare_eval_format(input_file, log_file=None):
    if not os.path.exists(input_file):
        log_print(f"[错误] 找不到文件: {input_file}", log_file)
        return None

    output_file = input_file.replace(".jsonl", "_eval.jsonl")
    log_print(f"[格式处理] 正在读取文件并准备官方格式...", log_file)
    
    existing_tasks = set()
    count = 0
    
    with open(input_file, "r", encoding="utf-8") as fin, \
         open(output_file, "w", encoding="utf-8") as fout:
        
        for line in fin:
            if not line.strip():
                continue
            data = json.loads(line)
            task_id = data.get("task_id")
            
            if "completions" in data:
                codes = data["completions"]
            elif "completion" in data:
                codes = [data["completion"]]
            else:
                continue
                
            existing_tasks.add(task_id)
            for code_ in codes:
                code=cut.fix_code(code_)
                fout.write(json.dumps({"task_id": task_id, "completion": code}, ensure_ascii=False) + "\n")
                count += 1
                
        missing_count = 0
        for i in range(164):
            expected_task_id = f"HumanEval/{i}"
            if expected_task_id not in existing_tasks:
                missing_count += 1
                for _ in range(K_SAMPLES):
                    fout.write(json.dumps({"task_id": expected_task_id, "completion": ""}, ensure_ascii=False) + "\n")
                    count += 1
                    
    if missing_count > 0:
        log_print(f"  [警告] 缺失了 {missing_count} 道题！已自动补交白卷。", log_file)
        
    log_print(f" -> 处理完成！生成评测专用文件: {output_file}", log_file)
    return output_file

def main():
    # ==== 核心修改：允许通过命令行接收特定评测文件 ====
    parser = argparse.ArgumentParser()
    parser.add_argument("--target_file", type=str, default="", help="要评测的具体 JSONL 文件路径")
    args = parser.parse_args()

    # 如果 sh 脚本传了参数，就只评测那一个文件；如果没传，就用默认的 TARGET_FILES 列表
    files_to_evaluate = [args.target_file] if args.target_file else TARGET_FILES
    # ==================================================

    os.makedirs(os.path.dirname(OUTPUT_LOG_PATH), exist_ok=True)
    
    with open(OUTPUT_LOG_PATH, "a", encoding="utf-8") as log_file:
        log_print(f"\n{'='*50}", log_file)
        log_print(f"===== Pass@K Evaluation Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====", log_file)
        
        for input_path in files_to_evaluate:
            log_print(f"\n{'-'*50}", log_file)
            log_print(f"开始评测文件: {input_path}", log_file)
            
            eval_ready_file = prepare_eval_format(input_path, log_file)
            if not eval_ready_file:
                continue

            log_print(f"正在调用官方脚本计算 Pass@1 和 Pass@5 ...", log_file)
            
            try:
                cmd = [sys.executable, EVAL_SCRIPT_PATH, eval_ready_file, "--k", "1,5"]
                process = subprocess.Popen(
                    cmd, cwd=EVAL_SCRIPT_DIR, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, encoding='utf-8'
                )

                for line in process.stdout:
                    clean_line = line.strip()
                    if clean_line:
                        log_print(f"  [评测结果] {clean_line}", log_file)

                process.wait()
                if process.returncode == 0:
                    log_print(f"✅ 文件评测圆满成功！", log_file)
                else:
                    log_print(f"❌ 评测遇到错误，返回码: {process.returncode}", log_file)
            except Exception as e:
                log_print(f"❌ 严重错误: {e}", log_file)

        log_print(f"\n{'='*50}", log_file)
        log_print(f"所有评测任务结束！详细结果保存在: {OUTPUT_LOG_PATH}", log_file)

if __name__ == "__main__":
    main()