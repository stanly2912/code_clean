from openai import OpenAI

import json                     # Added missing import
    

client = OpenAI(api_key="0", base_url="http://0.0.0.0:7000/v1")


def test_once(inp="User: Here is the original code. Please provide a cleaner, more concise version of this code following clean code principles\n@Override\n  public void close()\n  {\n    if (stringBufferMapper != null) {\n      stringBufferMapper.close();\n      deleteTempFile(stringDictionaryFile);\n    }\n    if (longBuffer != null) {\n      ByteBufferUtils.unmap(longBuffer);\n      deleteTempFile(longDictionaryFile);\n    }\n    if (doubleBuffer != null) {\n      ByteBufferUtils.unmap(doubleBuffer);\n      deleteTempFile(doubleDictionaryFile);\n    }\n    if (arrayBuffer != null) {\n      ByteBufferUtils.unmap(arrayBuffer);\n      deleteTempFile(arrayDictionaryFile);\n    }\n  }\n\nAssistant:"):
    messages = [{"role": "user", "content": inp}]
    result = client.chat.completions.create(messages=messages, model="deepseek")
    return result.choices[0].message.content


def test_batch(dics):
    for dic in dics:
        print("[test_batch]")
        pred = test_once(dic["instruction"]+dic["input"])
        dic["predict"] = pred


if __name__ == "__main__":
    input_file = "/home/wangbn/code_clean/input_data/data75.json"
    output_file = "/home/wangbn/code_clean/output_no.json"
    
    
    
    Is = [8371, 4326, 2957, 1824, 6710, 8452, 1093, 5762, 4801, 9320,
                  2046, 7585, 3164, 1932, 8340, 4178, 6291, 7534, 1285, 9706,
                  4823, 3459, 2468, 5190, 7049, 6897, 1301, 9145, 5623, 3784]
    
    with open(input_file, 'r', encoding='utf-8') as f:
        dics_ = json.load(f)
    
    dics=[]
    for i in Is:
        dics.append(dics_[(i+1)%len(dics_)])

    test_batch(dics)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(dics, f, ensure_ascii=False, indent=2)
    