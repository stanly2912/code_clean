import urllib.request
import os

models = {
    "qwen2.5_coder": "Qwen/Qwen2.5-Coder-7B/generations.json",
    "deepseek_v2": "deepseek-ai/DeepSeek-Coder-V2-Lite-Base/generations.json",
    "llama3.1": "meta-llama/Meta-Llama-3.1-8B/generations.json",
    "qwen2.5_7b": "Qwen/Qwen2.5-7B/generations.json",
    "codellama": "codellama/CodeLlama-7b-hf/generations.json"
}

base_url = "https://hf-mirror.com/datasets/bigcode/bigcodebench-results/resolve/main/"
save_dir = "/home/wangbn/code_clean/downloaded_apps_base/"
os.makedirs(save_dir, exist_ok=True)

for name, path in models.items():
    url = base_url + path
    print(f"正在下载 {name}...")
    try:
        urllib.request.urlretrieve(url, os.path.join(save_dir, f"{name}_base.json"))
        print(f"成功: {name}_base.json")
    except Exception as e:
        print(f"失败 {name}: {e}")