import json

input_path = "/home/wangbn/code_clean/infer_results_jzy/gpt-4.1_API/online/spoc_test_pass5.jsonl"
output_path = "/home/wangbn/code_clean/infer_results_jzy/gpt-4.1_API/online/spoc_test_pass5_standard.json"

with open(input_path, 'r', encoding='utf-8') as f:
    # 将每一行读取并存入列表
    data = [json.loads(line) for line in f if line.strip()]

with open(output_path, 'w', encoding='utf-8') as f:
    # 将整个列表保存为一个标准的 JSON 数组
    json.dump(data, f, ensure_ascii=False, indent=4)

print(f"转换完成，请在 shell 脚本中使用新路径: {output_path}")