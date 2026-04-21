import json
import argparse
from openai import OpenAI
import sys

# 动态添加 human-eval 根目录到 sys.path
human_eval_root = "./human-eval"  # 改成你的实际路径
sys.path.insert(0, human_eval_root)
# 现在可以正常导入包
from human_eval.data import stream_jsonl


sys.path.insert(0, "./parser_code/")
import cut
sys.path.insert(0, "./solvers/")
import solver_old,solver_A,solver_B,solver_C


human_raw_fail_ids= [
    "0",
    "9",
    "10",
    "20",
    "36",
    "37",
    "39",
    "42",
    "74",
    "75",
    "83",
    "91",
    "93",
    "95",
    "99",
    "102",
    "108",
    "111",
    "114",
    "117",
    "120",
    "125",
    "127",
    "129",
    "130",
    "132",
    "135",
    "137",
    "141",
    "145",
    "149",
]
#以下提示词有哪些前后冲突或者语焉不详，请给出三条最重要的修改建议

#以下提示词有哪些前后冲突或者语焉不详，请修复并润色



system_prompt_general="""

You are a rigorous software engineer and coding assistant.
Prioritize correctness, syntax validity, completeness, and executability above all else.

## Output Format
- Output only one Markdown fenced code block.
- Use the correct language identifier whenever possible, such as ```python or ```cpp.
- Do not output any explanations, notes, test cases, or test scripts.
- Unless the user explicitly requests pseudocode, always output real code.

## Scope Decision
- If the user provides a function signature, preserve that function signature exactly and output its implementation only.
- If the user does not provide a function signature, output a complete runnable program.
- For complete programs, use standard console input and standard console output.

## Interface Constraints
- Do not change any user-provided function signature, function name, class name, method signature, parameter list, or return type.
- Do not change any explicitly required interface.
- You may add necessary internal helper functions or supporting logic as long as the required interface remains unchanged.

## Code Quality
- Ensure the output is syntactically correct and directly usable.
- Do not omit critical implementation details.
- Prefer conservative, robust, and widely compatible implementations when uncertain.
- Handle relevant edge cases, boundary conditions, and common failure points when appropriate.

## Python Rules
- Follow PEP 8 style conventions.
- If the user provides a function signature, output only that function implementation and any necessary helper definitions.
- If the user does not provide a function signature, output a complete program using standard input and standard output.
- Do not generate test cases.

## C++ Rules
- Output standard-compliant and compilable C++ code.
- Include all necessary headers and definitions for the requested scope.
- If the user provides a function signature, preserve it exactly and output its implementation only.
- If the user does not provide a function signature, output a complete program with a main function using standard input and standard output.

## Final Check Before Output
Before producing the answer, verify:
- brackets, braces, parentheses, and quotes are matched
- indentation and formatting are valid
- imports, headers, namespaces, and dependencies are sufficient
- required signatures and interfaces are preserved exactly
- there are no undefined symbols, missing return paths, or incomplete logic

## Mandatory Instruction
Your final answer must contain only one Markdown fenced code block.

"""




instruction_correct_human = r"""
You are a senior Python engineer. Your task is to repair the given code so that it is correct, runnable, and, when safe, more efficient.

Follow these rules in order of priority:
1. Correctness
2. Preserve the intended behavior and output format
3. Improve performance only when it is clearly safe

Procedure:
1. Read the function description, docstring, and inline comments carefully.
2. Infer the intended behavior primarily from:
   - the explicit function/task description
   - then the docstring
   - then inline comments
   - then the existing code
3. If these sources conflict, follow the most explicit specification and briefly note the ambiguity.
4. Add any missing imports that are required for the code to run.
   - Prefer the Python standard library.
   - Only introduce a third-party package if the original code or specification already clearly depends on it.
   - Do not add unnecessary dependencies.
5. Check the loop logic and control flow carefully:
   - If a loop is incorrect, rewrite it.
   - If a loop is unnecessarily slow, optimize it without changing semantics.
   - Do not change the intended output format, external behavior, or edge-case behavior unless the original code is clearly broken.
6. Review the entire code for:
   - syntax errors
   - indentation issues
   - incorrect conditions
   - wrong loop boundaries
   - missing return statements
   - variable-scope issues
   - missing imports
   - obvious edge-case failures
7. Return a corrected version that can run directly, including all necessary imports.

Important constraints:
- Do not add new features, side effects, logging, or I/O unless explicitly required.
- Preserve the original function signature

- Keep the original function names and parameter signatures unchanged, do not have 'self' parameter
- Do not change the number of top-level functions or their definitions; you may add nested helper functions if needed
- Do NOT modify the public interface
- The output MUST contain valid Python code only, with no explanations
- Do NOT generate any test code or usage examples
- Ensure the code is complete and directly executable

If the intended behavior is genuinely ambiguous in a way that materially affects the implementation, provide at least 2 plausible corrected versions and briefly explain the difference.

Output format:
1. Briefly explain what was wrong.
2. Then provide the corrected code in a single code block.
3. If multiple versions are necessary, label them clearly (e.g. Version A / Version B) and explain the behavioral difference briefly.
4. Keep the explanation concise and focus on the repair.
"""

instruction_clean_human = r"""
You are given an original piece of code, along with some corrected code and reference reasoning. Rewrite the original code to be cleaner while strictly following clean code principles. If you are not confident that your rewritten code is correct, return the original code unchanged.

Objectives:
- Reduce cyclomatic complexity where possible
- Minimize the number of lines without sacrificing clarity
- Preserve 100% of the original functionality and behavior
- Do NOT introduce type hints or docstrings unless they already exist

Constraints:
- Keep the original function names and parameter signatures unchanged, do not have 'self' parameter
- Do not change the number of top-level functions or their definitions; you may add nested helper functions if needed
- Do NOT modify the public interface
- The output MUST contain valid Python code only, with no explanations
- Do NOT generate any test code or usage examples
- Ensure the code is complete and directly executable

Implementation Rules:
- You may import necessary standard-library modules
- You may define helper functions if needed
- Improve structure and readability
- If the original code contains bugs or obvious issues, fix them only if doing so preserves the intended behavior

Output Format:
- Return ONLY the final improved Python code
- The code MUST define the function(s) using `def` with the original names and parameters

----------------------
Example 1:

Input:
def add(a,b):
    result = 0
    result = a + b
    return result

Output:
def add(a, b):
    return a + b

----------------------
Example 2:

Input:
def is_even(n):
    if n % 2 == 0:
        return True
    else:
        return False

Output:
def is_even(n):
    return n % 2 == 0

----------------------
Example 3:

Input:
def find_max(nums):
    max_val = nums[0]
    for i in range(len(nums)):
        if nums[i] > max_val:
            max_val = nums[i]
    return max_val

Output:
def find_max(nums):
    max_val = nums[0]
    for num in nums:
        if num > max_val:
            max_val = num
    return max_val

----------------------

Now rewrite the given code accordingly.
"""





instruction_clean_2 = r"""
You are an expert Python code reviewer and refactoring engineer.

You are given:
- the original code,
- one or more corrected implementations,
- and reference reasoning that may help infer the intended behavior.

Your task is to choose the best behavioral interpretation and rewrite the code into a cleaner version without changing its intended behavior.

Follow this procedure exactly:

Step 1: Determine intended behavior
- Read the original code, all corrected implementations, and the reference reasoning carefully.
- Infer the intended behavior from the strongest evidence across the corrected implementations, the reasoning, and the original code context.
- Use majority agreement as a signal, not a rule.
- If sources conflict, prefer the interpretation best supported overall and most consistent with the original code context.
- Behavioral correctness is the highest priority.

Step 2: Select the best candidate logic
- Choose the implementation that best matches the intended behavior.
- If multiple implementations are behaviorally equivalent, prefer the one with better runtime efficiency.
- If efficiency is also similar, prefer the one with simpler control flow and less redundancy.
- Treat candidate implementations as references for behavior and logic, not as templates to copy directly.

Step 3: Make itclean
- Rewrite the code into a cleaner version while preserving the original public interface and top-level structure.
- Keep the original function names, parameter signatures, and top-level function definitions unchanged.
- You may borrow logic from any candidate implementation, but the final code must align with the original external structure.

Apply these principles conservatively:
- Keep logic easy to follow
- Reduce unnecessary branching and nesting
- Reduce cyclomatic complexity where possible
- Remove dead code, duplicated logic, and redundant temporary variables
- Prefer local simplifications over large structural rewrites
- Minimize line count only when readability does not suffer
- Avoid renaming unless it clearly improves readability without changing meaning
- Preserve exception behavior, return values, side effects, and edge-case handling

Hard constraints:
- Preserve the intended behavior as exactly as possible
- Keep all original function names unchanged
- Keep all original parameter signatures unchanged
- Keep the number of top-level functions unchanged
- Do not add or remove top-level function definitions
- Do not modify the public interface
- Do not add type hints unless they already exist
- Do not add docstrings unless they already exist
- You may add nested helper functions only if they clearly improve readability and do not alter behavior
- Fix bugs only when necessary to match the intended behavior

Conservatism rule:
- If evidence about the intended behavior is insufficient, ambiguous, or materially conflicting, return the original code unchanged
- Prefer no refactor over a risky refactor
- Prefer a smaller cleanup over a larger rewrite

Output rules:
- Return only valid, complete, directly executable Python code
- Do not include explanations
- Do not include reasoning
- Do not include tests
- Do not include usage examples
- Do not add explanatory comments about the refactor
- Standard library imports and custom helper functions are required; all custom functions must have corresponding implementations.

Before producing the final code, internally verify:
- syntax is valid
- function signatures are unchanged
- top-level function count is unchanged
- intended behavior is preserved as closely as possible
- the rewritten code is cleaner than the selected candidate

Now output the final rewritten Python code only.
"""



def fix_prompt_human(old_code):
    
    old_instruction="you must follow:\n    1. Provide the complete code without any textual explanations and do not generate test scripts.\n    2. Please strictly follow the specified format provided below for the code.\n    3. Do not change the function names.\n    4. The original code content must be fully included in the generated complete code, including all package import sections.\n    5. For Python language, do not generate test cases or main function.\n    6. Do not generate test cases.\n    "
    ret=old_code.replace(old_instruction,"")
    ret=ret
    return ret

    
def get_args():
    parser = argparse.ArgumentParser(description="LLM Code Refactor Tool")
    parser.add_argument("--input", type=str, default="./in.json", help="Input JSON/JSONL file path")
    parser.add_argument("--output", type=str, default="./out.json", help="Output JSON/JSONL file path")
    parser.add_argument("--base_url", type=str, default="http://0.0.0.0:6000/v1", help="Base model API URL")
    parser.add_argument("--tune_url", type=str, default="http://0.0.0.0:7000/v1", help="Tuned model API URL")
    parser.add_argument("--model", type=str, default="default", help="Model name to use")
    return parser.parse_args()


def infer_once(client, model, inp):
    messages = [{"role": "user", "content": inp}]
    try:
        response = client.chat.completions.create(messages=messages, model=model)
        return response.choices[0].message.content
    except Exception as e:
        print(f"[infer_once] Error during inference: {e}")
        return ""


"""
#old code

Algorithm Solve(task_description)
    refined_instruction ← InstructAgent(instruction)
    thought_proccess ← InferAgent(correction_instruction + task_description)
    final_code ← CleanAgent(
        refined_instruction + task_description + thought_proccess
    )
    final_code ← fix_code(final_code)
    return final_code
End Algorithm

import time
def solve(client_base, client_tune, model, user_prompt,
    instruction_correct=instruction_correct_human,
    instruction_clean=instruction_clean_human):

    #return user_prompt

    print("[solve] user_prompt=",user_prompt)

    if(1):
        instruction_clean = infer_once(
            client_base,
            model,
            ""
            + "Please revise the prompt according to the following task requirements. "
            + "=" * 10 + "These are the task requirements: " + user_prompt + "=" * 10 + "end"
            + "=" * 10 + "This is the prompt: " + instruction_clean + "=" * 10 + "end"
            + ""
        )

    print("[solve] instruction_clean=",instruction_clean)
    text1 = infer_once(client_base, model, instruction_correct + user_prompt)
    if not text1:
        return ""
    time.sleep(0.1)
    print("[solve] text1=",text1)
    ret= infer_once(client_tune, model, 
        ""+
        instruction_clean+ 
        "="*10+"here's original code" +user_prompt+"="*10+"end original code"+
        "="*10+"here's fixed code" +text1+"="*10+"end original code"+

        ""
        )
    
    ret=cut.fix_code(ret)
    print("[solve] ret=",ret)
    if not isinstance(ret, str):
        print("[solve] ERROR ret=", ret)
        return ""
    return ret
    

"""





"""


"""



import ast
import re
import time





import os


import os

def solve(
    client_base,
    client_tune,
    model,
    task_description,
    original_code,
    instruction_correct=instruction_correct_human,
    instruction_clean=instruction_clean_human,
):
    global system_prompt_general

    mas_file = os.getenv("MAS_FILE")
    print(f"[solve] mas_file= {mas_file}")

    solver_map = {
        "solver_A": solver_A,
        "solver_B": solver_B,
        "solver_C": solver_C,
        "solver_old": solver_old,
    }

    if mas_file:
        solver = solver_map.get(mas_file)
        if solver is None:
            print(f"[solve] ERROR MAS_FILE not found or invalid: {mas_file}")
            solver = solver_old
    else:
        solver = solver_old

    return solver.solve(
        client_base,
        client_tune,
        model,
        task_description,
        original_code,
        instruction_correct=system_prompt_general,
        instruction_clean=system_prompt_general,
    )






def load_data(input_path):
    if input_path.endswith(".jsonl"):
        return list(stream_jsonl(input_path))

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Input JSON should be a list of code snippets.")

    return data













def save_results(output_path, results):
    with open(output_path, "w", encoding="utf-8") as f:
        if output_path.endswith(".jsonl"):
            for item in results:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        else:
            json.dump(results, f, indent=4, ensure_ascii=False)


def main():
    args = get_args()

    client_base = OpenAI(api_key="EMPTY", base_url=args.base_url)
    client_tune = OpenAI(api_key="EMPTY", base_url=args.tune_url)

    try:
        dirty_codes = load_data(args.input)
    except Exception as e:
        print(f"Error loading file: {e}")
        return

    results = []
    total = len(dirty_codes)
    print(f"Starting processing {total} items using model '{args.model}'...")

    for i, case in enumerate(dirty_codes):
        code_snippet = case.get("completion", "") if isinstance(case, dict) else ""
        print("code_snippet", code_snippet)

        is_hard_case=(

            str(i) in human_raw_fail_ids or
            "def fizz_buzz" in code_snippet or
            "def vowels_count" in code_snippet or
            "def intersperse" in code_snippet or 
            "def below_zero" in code_snippet or
            "def first_last" in code_snippet or
            "def make_palindrome" in code_snippet or
            "def has_close_elements" in code_snippet or
            "def fib" in code_snippet or
            "def sum_even" in code_snippet or
            "def closest_pair" in code_snippet or
            "def total_match" in code_snippet or
            "def string_sequence" in code_snippet
            ) 

        if (
            #not is_hard_case or
             not code_snippet) and 1:
            clean_code =code_snippet
        else:
            user_prompt = fix_prompt_human(code_snippet)
            clean_code = solve(client_base, client_tune, args.model, user_prompt)


        clean_code = cut.fix_code(clean_code)

        print("!!clean_code", clean_code)
        #print(code, "!!")

        item = {
            "task_id": cut.k2taskid(i),
            "completion": clean_code
        }
        results.append(item)

        print(f"[{i + 1}/{total}] Processed.")

    try:
        save_results(args.output, results)
    except Exception as e:
        print(f"Error saving file: {e}")
        return

    print(f"\nSuccess! Results saved to: {args.output}")


if __name__ == "__main__":
    main()
    
"""


API_PORT=6000 CUDA_VISIBLE_DEVICES=0 llamafactory-cli api /home/wangbn/code_clean/infer_scripts/inferQWcode.yaml 
API_PORT=7000 CUDA_VISIBLE_DEVICES=0 llamafactory-cli api /home/wangbn/code_clean/infer_scripts/inferQWcode25.yaml 
    

python ./infClean.py   --input /home/wangbn/code_clean/human-eval/human_eval/codesQWcoder.jsonl --output ./cleancodes.jsonl





print(i, type(c), "!!")
        code = extract_code(c)

        #print(code, "!!")

        item = {
            "task_id": k2taskid(i),
            "completion": code
        }
        results_list.append(item)
"""