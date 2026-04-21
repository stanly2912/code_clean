from data import write_jsonl, read_problems


from openai import OpenAI
import argparse


client = OpenAI(api_key="0", base_url="http://0.0.0.0:6000/v1")

def infer_once(inp="User: Here is the original code. Please provide a cleaner, more concise version of this code following clean code principles\n@Override\n  public void close()\n  {\n    if (stringBufferMapper != null) {\n      stringBufferMapper.close();\n      deleteTempFile(stringDictionaryFile);\n    }\n    if (longBuffer != null) {\n      ByteBufferUtils.unmap(longBuffer);\n      deleteTempFile(longDictionaryFile);\n    }\n    if (doubleBuffer != null) {\n      ByteBufferUtils.unmap(doubleBuffer);\n      deleteTempFile(doubleDictionaryFile);\n    }\n    if (arrayBuffer != null) {\n      ByteBufferUtils.unmap(arrayBuffer);\n      deleteTempFile(arrayDictionaryFile);\n    }\n  }\n\nAssistant:"):
    instruction="please give the python code to solve the question directly, no more useless output,dont output your thinking proccess.\n"
    print("[infer_once]")
    messages = [{"role": "user", "content":  instruction+inp}
    #,{"role": "system", "content": "please give the python code to solve the question"}
    ]
    result = client.chat.completions.create(messages=messages, model="deepseek")
    ret=result.choices[0].message.content
    print("[infer_once]",messages,ret)
    return ret


def generate_one_completion(user_prompt):
    print("[generate_one_completion]",user_prompt)
    ret=infer_once(user_prompt)
    return ret
    
    
    import argparse

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=str, default="samples.jsonl")
    args = parser.parse_args()

    problems = read_problems()

    num_samples_per_task = 1
    samples = [
        dict(
            task_id=task_id,
            completion=generate_one_completion(problems[task_id]["prompt"])
        )
        for task_id in problems
        for _ in range(num_samples_per_task)
    ]

    print("start write jsonl")

    write_jsonl(args.output, samples)