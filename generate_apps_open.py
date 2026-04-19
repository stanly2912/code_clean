import json
import argparse
from tqdm import tqdm
from datasets import load_dataset
from vllm import LLM, SamplingParams

def get_prompt(problem):
    prompt = problem["question"].strip()
    if problem.get("starter_code") and problem["starter_code"].strip():
        prompt += "\n\nStarter code:\n" + problem["starter_code"].strip()
    prompt += "\n\nWrite a complete Python program that solves the problem.\n"
    prompt += "The program must read input from stdin and print output to stdout.\n"
    prompt += "Only output the code, no explanation, no markdown, no ```."
    return prompt

def generate_for_difficulty(difficulty: str, llm, n_samples: int, temperature: float, max_problems: int = None):
    print(f"🚀 正在生成 {difficulty} 难度... (n_samples={n_samples}, temp={temperature})")
    
    ds = load_dataset("codeparrot/apps", split="test")
    ds = ds.filter(lambda x: x.get("difficulty") == difficulty)
    
    if max_problems:
        ds = ds.select(range(min(max_problems, len(ds))))
    
    problems = list(ds)
    prompts = [get_prompt(p) for p in problems]
    task_ids = [f"apps/{difficulty}/{i:04d}" for i in range(len(problems))]
    
    sampling_params = SamplingParams(
        temperature=temperature,
        max_tokens=2048,
        n=n_samples
    )
    
    outputs = llm.generate(prompts, sampling_params)
    
    generations = []
    for i, output in enumerate(tqdm(outputs, desc=difficulty)):
        completions = [o.text.strip() for o in output.outputs]
        generations.append({
            "task_id": task_ids[i],
            "prompt": prompts[i],
            "completions": completions
        })
        if (i + 1) % 100 == 0:
            save_generations(generations, difficulty, n_samples)
    
    save_generations(generations, difficulty, n_samples)
    print(f"✅ {difficulty} 生成完成！共 {len(generations)} 个问题")
    return generations

def save_generations(generations, difficulty, n_samples):
    filename = f"generations_{difficulty}_n{n_samples}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(generations, f, ensure_ascii=False, indent=2)
    print(f"💾 已保存 → {filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, required=True, help="模型路径，例如 Qwen/Qwen2.5-Coder-7B")
    parser.add_argument("--difficulty", type=str, default="introductory", choices=["introductory", "interview", "competition", "all"])
    parser.add_argument("--n_samples", type=int, default=1, help="Pass@1 用 1，Pass@5 用 5")
    parser.add_argument("--temperature", type=float, default=0.0, help="Pass@1 用 0.0，Pass@5 用 0.8")
    parser.add_argument("--max_problems", type=int, default=None, help="先测试时限制数量")
    args = parser.parse_args()

    print(f"🔧 正在加载模型 {args.model} ...（第一次加载需要 1-3 分钟）")
    llm = LLM(model=args.model, trust_remote_code=True, gpu_memory_utilization=0.90, tensor_parallel_size=1)

    if args.difficulty == "all":
        for diff in ["introductory", "interview", "competition"]:
            generate_for_difficulty(diff, llm, args.n_samples, args.temperature, args.max_problems)
    else:
        generate_for_difficulty(args.difficulty, llm, args.n_samples, args.temperature, args.max_problems)

    print("🎉 全部完成！生成的 JSON 文件可以直接喂给你的评测脚本")