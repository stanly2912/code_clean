from openai import OpenAI
import json
from pathlib import Path
from typing import List, Dict, Any

client = OpenAI(
    api_key="0",
    base_url="http://0.0.0.0:7025/v1"
)


def test_once(prompt: str, model: str = "deepseek") -> str:
    """单次调用模型获得回复"""
    messages = [{"role": "user", "content": prompt}]
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.0,   # 可根据需要调整
        max_tokens=4096,
    )
    return response.choices[0].message.content.strip()


def load_jsonl(path: str | Path) -> List[Dict[str, Any]]:
    """读取 jsonl 文件"""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")
    
    data = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def write_jsonl(data: List[Dict], path: str | Path, ensure_ascii=False) -> None:
    """写入 jsonl 文件"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with path.open("w", encoding="utf-8") as f:
        for item in data:
            json.dump(item, f, ensure_ascii=ensure_ascii)
            f.write("\n")


def case_to_prompt(case: Dict[str, Any]) -> str:
    """
    将单个 SWE-bench 样例转换为模型可用的中文 prompt
    """
    repo = f"{case['org']}/{case['repo']}"
    problem = case["body"].strip()

    # 合并已解决的 issues 内容
    resolved_bodies = [
        issue.get("body", "").strip()
        for issue in case.get("resolved_issues", [])
        if issue.get("body", "").strip()
    ]
    if resolved_bodies:
        problem += "\n\n已解决的相关问题描述：\n" + "\n\n".join(resolved_bodies)

    hints = case.get("hints", "").strip()

    prompt = f"""IMPORTANT：使用中文回复
IMPORTANT：仅生成修复后的代码片段，不要包含任何说明、测试代码、运行结果
当前环境无法运行完整项目，请只输出修改后的代码

仓库：{repo}
问题描述：
{problem}

提示（如果有）：
{hints}

请直接输出修复后的完整代码块（保持原有文件路径与类结构），不要输出其他任何内容。
"""
    return prompt


def main():
    input_file = "/home/wangbn/multi_swe_bench_mini.jsonl"
    output_file = "/home/wangbn/code_clean/model25_SWEmini.jsonl"  # 建议使用 .jsonl 后缀更清晰

    print("开始加载数据集...")
    cases = load_jsonl(input_file)[0:305]
    print(f"共加载 {len(cases)} 条数据")

    results = []

    for i, case in enumerate(cases, 1):
        
        if case["language"]!="java":
            continue
        instance_id = case.get("instance_id", "unknown")
        print(f"[{i:3d}/{len(cases)}] {instance_id}")

        try:
            prompt = case_to_prompt(case)
            prediction = test_once(prompt)
            
            results.append({
                "instance_id": instance_id,
                "predict": prediction,
                # 可选：保留更多信息方便后续分析
                # "repo": f"{case['org']}/{case['repo']}",
                # "prompt": prompt,
            })
        except Exception as e:
            print(f"  处理失败 {instance_id} : {e}")
            results.append({
                "instance_id": instance_id,
                "predict": f"[ERROR] {str(e)}",
                "error": True
            })

    print("\n保存结果...")
    write_jsonl(results, output_file)
    print(f"已保存到：{output_file}")


if __name__ == "__main__":
    main()