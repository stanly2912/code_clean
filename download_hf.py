from huggingface_hub import snapshot_download
import os

# 存放路径
save_path = '/home/wangbn/7B_model/Qwen2.5-Coder-7B-Instruct'
os.makedirs(save_path, exist_ok=True)

print('🚀 开始从 Hugging Face 下载 Qwen2.5-Coder-7B-Instruct...')
# 下载模型，不使用软链接，直接把实体文件下到目标文件夹
snapshot_download(
    repo_id='Qwen/Qwen2.5-Coder-7B-Instruct', 
    local_dir=save_path,
    local_dir_use_symlinks=False
)
print(f'✅ 下载完成！模型保存在：{save_path}')