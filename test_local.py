import traceback
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

LOCAL_MODEL_PATHS = [
    #这边加入你的报错模型
    #"/home/data/wangbn/7B_model/CodeLlama-7b-hf",
    "/home/data/wangbn/7B_model/baichuan2-7b-base"
    # "/home/data/wangbn/7B_model/Qwen2.5-Coder-7b-Base",
    # "/home/data/wangbn/7B_model/Qwen2.5-Coder-7B-instruct",
    # "/home/data/wangbn/7B_model/CodeLlama-7b-hf",
    # "/home/data/wangbn/7B_model/dolphin-2.6-mistral-7b-dpo",
]

for model_path in LOCAL_MODEL_PATHS:
    print("=========")
    print(model_path)

    try:
        tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            trust_remote_code=True,
            use_fast=False
        )

        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            device_map="auto",
            dtype=torch.bfloat16,
            trust_remote_code=True,
        ).eval()



        # 关闭 cache，绕开 Baichuan2 的 past_key_values 兼容问题
        model.config.use_cache = False
        if hasattr(model, "generation_config") and model.generation_config is not None:
            model.generation_config.use_cache = False
        #==============================================================

        prompt = "generate quick sort python code"
        inputs = tokenizer(prompt, return_tensors="pt")
        print(f"inputs:{inputs}")
        input_ids = inputs["input_ids"].to("cuda")
        generation_output = model.generate(
            input_ids=input_ids,
            max_new_tokens=1024,
            num_beams = 3,
            num_return_sequences=3,
            return_dict_in_generate=True
        )

        print("query:", prompt)
        for i, output_sequence in enumerate(generation_output.sequences):
            output_text = tokenizer.decode(output_sequence, skip_special_tokens=True)
            print(f"Generated sequence {i+1}: {output_text}")

    except Exception as e:
        print(f"[ERROR] {e}")
        traceback.print_exc()


"""
当模型推理出现编译错误或者输出空串时，
将模型放到开头的list
运行这个排查错误：
python /home/wangbn/test_local.py
先把这个调通，再参考这个代码去调infer.py的"LOCAL"分支

如果卡住不懂，运行nvidia-smi，可能是因为GPU爆


outputs = model.generate(inputs, max_new_tokens=512, do_sample=False, top_k=50, top_p=0.95, num_return_sequences=1, eos_token_id=tokenizer.eos_token_id)
"""