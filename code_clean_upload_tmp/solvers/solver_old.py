
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

以上不要管，轻易不要改这份代码
将以下代码喂给AI，让他优化框架

----------------------------
建议提示词：

优化以下多智能体架构solve，其中client_base是基座模型，client_tune是拿cpp和py干净代码微调后的微调模型
保证函数签名不变，功能不变

[

适当优化算法的时间复杂度
结合相关最新的文献和工作，优化智能体架构
]
优化架构，
solve框架本身可以稍微复杂，但是要保证生成的代码，正确、整洁、圈复杂度低，并return最终修改的代码

给出完整python代码


----------------------------
"""


import ast
import re
from dataclasses import dataclass


_CODE_BLOCK_RE = re.compile(r"```(?:[a-zA-Z0-9_+\-]*)\s*(.*?)```", flags=re.DOTALL)
_CODE_START_RE = re.compile(r"(?m)^(?:async\s+def |def |class |from |import |if __name__ ==)")


@dataclass(frozen=True)
class CodeFacts:
    code: str
    compiles: bool
    meta: tuple | None
    complexity: int | None
    looks_like_code: bool
    explanatory: bool


@dataclass
class Candidate:
    label: str
    raw: str
    code: str
    valid: bool
    compiles: bool
    interface_ok: bool
    complexity: int | None
    score: float


def _safe_text(value):
    return value if isinstance(value, str) else ""


def _extract_code_text(text):
    if not isinstance(text, str):
        return ""
    s = text.strip()
    if not s:
        return ""

    blocks = _CODE_BLOCK_RE.findall(s)
    if blocks:
        return max(blocks, key=lambda x: len(x.strip())).strip()

    match = _CODE_START_RE.search(s)
    if match:
        return s[match.start():].strip()
    return s


def _strip_code_fence(text):
    return _extract_code_text(text).strip()


def _try_external_fix(code):
    try:
        fixer = globals().get("cut", None)
        if fixer is not None and hasattr(fixer, "fix_code"):
            fixed = fixer.fix_code(code)
            if isinstance(fixed, str) and fixed.strip():
                return fixed.strip()
    except Exception:
        pass
    return code.strip()


def _safe_fix_code(text):
    code = _strip_code_fence(text)
    return _try_external_fix(code) if code else ""


def _looks_like_code(text):
    if not isinstance(text, str):
        return False
    s = text.strip()
    if not s:
        return False
    markers = [
        "def ", "async def ", "class ", "import ", "from ",
        "return ", "for ", "while ", "if ", "elif ", "else:",
        "try:", "except", "with ", "yield ", "=",
    ]
    hits = sum(marker in s for marker in markers)
    return hits >= 2 or ("\n" in s and ("def " in s or "class " in s))


def _extract_original_code(text):
    if not isinstance(text, str) or not text.strip():
        return ""
    extracted = _extract_code_text(text)
    if _looks_like_code(extracted):
        return extracted.strip()
    s = text.strip()
    return s if _looks_like_code(s) else ""


def _top_level_meta_from_tree(tree):
    meta = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            posonly = tuple(a.arg for a in getattr(args, "posonlyargs", []))
            normal = tuple(a.arg for a in args.args)
            kwonly = tuple(a.arg for a in args.kwonlyargs)
            vararg = args.vararg.arg if args.vararg else None
            kwarg = args.kwarg.arg if args.kwarg else None
            meta.append((
                "async" if isinstance(node, ast.AsyncFunctionDef) else "def",
                node.name,
                posonly,
                normal,
                vararg,
                kwonly,
                kwarg,
            ))
        elif isinstance(node, ast.ClassDef):
            meta.append(("class", node.name))
    return tuple(meta)


def _compute_complexity_from_tree(tree):
    complexity = 1
    branch_nodes = (
        ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.ExceptHandler,
        ast.With, ast.AsyncWith, ast.IfExp, ast.comprehension,
    )
    for node in ast.walk(tree):
        if isinstance(node, branch_nodes):
            complexity += 1
        elif isinstance(node, ast.BoolOp):
            complexity += max(0, len(node.values) - 1)
    return complexity


def _is_explanatory_text(code):
    low = code.lower().strip()
    prefixes = (
        "here is", "here's", "below is", "the code",
        "explanation", "i revised", "i updated",
    )
    return any(low.startswith(prefix) for prefix in prefixes)


def _analyze_code(code, cache):
    code = _safe_text(code).strip()
    cached = cache.get(code)
    if cached is not None:
        return cached

    looks_like = _looks_like_code(code)
    explanatory = _is_explanatory_text(code)
    if not code:
        facts = CodeFacts("", False, None, None, False, False)
        cache[code] = facts
        return facts

    try:
        tree = ast.parse(code)
        compile(tree, "<generated>", "exec")
        facts = CodeFacts(
            code=code,
            compiles=True,
            meta=_top_level_meta_from_tree(tree),
            complexity=_compute_complexity_from_tree(tree),
            looks_like_code=looks_like,
            explanatory=explanatory,
        )
    except Exception:
        facts = CodeFacts(code, False, None, None, looks_like, explanatory)

    cache[code] = facts
    return facts


def _compiles(code):
    return _analyze_code(code, {}).compiles


def _top_level_meta(code):
    facts = _analyze_code(code, {})
    return facts.meta if facts.compiles else None


def _interface_preserved(code, original_meta):
    if not original_meta:
        return True
    facts = _analyze_code(code, {})
    return facts.compiles and facts.meta == original_meta


def _complexity_proxy(code):
    facts = _analyze_code(code, {})
    return facts.complexity if facts.compiles else None



def _normalize_decision(text, labels):
    if not isinstance(text, str):
        return ""

    up = text.strip().upper()

    # 先按长度从长到短排序，避免 B 先匹配掉 B2
    for label in sorted(labels, key=len, reverse=True):
        label_up = label.upper()

        # 先做完全相等判断
        if up == label_up:
            return label_up

        # 再做边界匹配
        if re.search(rf"(?<!\w){re.escape(label_up)}(?!\w)", up):
            return label_up

    return ""


def _infer_once(client, model, prompt):
    messages = [{"role": "user", "content": prompt}]
    try:
        response = client.chat.completions.create(messages=messages, model=model)
        return response.choices[0].message.content
    except Exception as exc:
        print(f"[_infer_once] Error during inference: {exc}")
        return ""


def _ask_model(name, client, model, prompt):
    try:
        out = _infer_once(client, model, prompt)
        print(f"[solve] {name}=", out)
        return out if isinstance(out, str) else ""
    except Exception as exc:
        print(f"[solve] {name} error=", exc)
        return ""


def _score_candidate(code, original_code, original_meta, original_complexity, label, analysis_cache):
    cleaned = _safe_fix_code(code)
    if not cleaned:
        return Candidate(label, _safe_text(code), "", False, False, False, None, float("-inf"))

    facts = _analyze_code(cleaned, analysis_cache)
    interface_ok = (facts.meta == original_meta) if (facts.compiles and original_meta) else not original_meta
    valid = bool(cleaned) and facts.looks_like_code and facts.compiles and interface_ok

    if not valid:
        penalty = -1000.0
        if facts.looks_like_code:
            penalty += 10.0
        if facts.compiles:
            penalty += 20.0
        if interface_ok:
            penalty += 20.0
        return Candidate(label, _safe_text(code), cleaned, False, facts.compiles, interface_ok, facts.complexity, penalty)

    score = 100.0
    if label == "ORIGINAL":
        score += 20.0
    if original_code:
        cleaned_s = cleaned.strip()
        original_s = original_code.strip()
        if cleaned_s == original_s:
            score += 25.0
        diff = abs(len(cleaned_s) - len(original_s))
        score += max(0.0, 15.0 - diff / 120.0)

    if facts.explanatory:
        score -= 50.0
    if "```" in cleaned:
        score -= 20.0

    low = cleaned.lower()
    if "todo" in low or "placeholder" in low:
        score -= 30.0

    if facts.complexity is not None:
        score += max(0.0, 18.0 - float(facts.complexity))
        if original_complexity is not None and facts.complexity > original_complexity:
            score -= min(12.0, float(facts.complexity - original_complexity) * 1.5)

    return Candidate(label, _safe_text(code), cleaned, True, True, True, facts.complexity, score)


def _rank_candidates(candidates):
    return sorted(candidates, key=lambda c: (c.valid, c.interface_ok, c.compiles, c.score), reverse=True)


def _pick_by_decision(decision, candidate_map):
    chosen = candidate_map.get(decision)
    return chosen if chosen and chosen.valid else None


def _best_fallback(ranked):
    for candidate in ranked:
        if candidate.valid:
            return candidate
    for candidate in ranked:
        if candidate.label == "ORIGINAL" and candidate.code:
            return candidate
    return Candidate("ORIGINAL", "", "", False, False, False, None, float("-inf"))


def _parse_spec_lines(text):
    result = {
        "INTENT": "unknown",
        "INPUTS": "unknown",
        "OUTPUTS": "unknown",
        "MUST_PRESERVE": "unknown",
        "ALLOWED_CHANGES": "unknown",
        "AMBIGUITIES": "unknown",
    }
    for raw_line in _safe_text(text).splitlines():
        line = raw_line.strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().upper()
        if key in result:
            value = value.strip() or "unknown"
            result[key] = value
    return result


def _merge_specs(*spec_texts):
    merged = {
        "INTENT": "unknown",
        "INPUTS": "unknown",
        "OUTPUTS": "unknown",
        "MUST_PRESERVE": "unknown",
        "ALLOWED_CHANGES": "unknown",
        "AMBIGUITIES": "unknown",
    }
    for field in merged:
        best = "unknown"
        for spec_text in spec_texts:
            value = _parse_spec_lines(spec_text).get(field, "unknown")
            if value.lower() != "unknown" and len(value) >= len(best):
                best = value
        merged[field] = best
    return "\n".join(f"{key}: {value}" for key, value in merged.items())


def _build_spec_prompt(task_description, original_code):
    return (
        "ROLE: SPEC_AGENT\n"
        "Goal: infer the intended behavior and hard constraints from the user's request and original code.\n"
        "Do NOT write code.\n"
        "Return plain text only with exactly these 6 lines:\n"
        "INTENT: ...\n"
        "INPUTS: ...\n"
        "OUTPUTS: ...\n"
        "MUST_PRESERVE: ...\n"
        "ALLOWED_CHANGES: ...\n"
        "AMBIGUITIES: ...\n"
        "If evidence is weak, write 'unknown'. Keep each line short.\n\n"
        "USER TASK:\n"
        f"{task_description}\n\n"
        "ORIGINAL CODE:\n"
        f"{original_code if original_code else '[EMPTY]'}\n"
    )


def _build_repair_prompt_a(spec, task_description, original_code, instruction_correct):
    return (
        "ROLE: REPAIR_AGENT_A\n"
        "Objective: produce the most correct directly runnable Python repair.\n"
        "BACKGROUND_GUIDANCE:\n"
        f"{instruction_correct}\n\n"
        "HARD_RULES:\n"
        "- Return ONLY complete valid Python code.\n"
        "- No explanation. No markdown fences.\n"
        "- Preserve original function names, parameter signatures, public interface, and number of top-level functions.\n"
        "- Add only required imports.\n"
        "- Prefer correctness first.\n"
        "- Prefer simple control flow, early returns, and low nesting when safe.\n"
        "- Do not invent behavior not grounded in the task or original code.\n"
        "- If the task is materially ambiguous or you are not confident, return ORIGINAL CODE unchanged.\n\n"
        "SPEC:\n"
        f"{spec if spec else 'unknown'}\n\n"
        "USER TASK:\n"
        f"{task_description}\n\n"
        "ORIGINAL CODE:\n"
        f"{original_code if original_code else '[EMPTY]'}\n"
    )


def _build_repair_prompt_b(spec, task_description, original_code, instruction_correct, instruction_clean):
    return (
        "ROLE: REPAIR_AGENT_B\n"
        "Objective: make the smallest safe set of edits needed to make the code correct, neat, and directly runnable.\n"
        "BACKGROUND_GUIDANCE:\n"
        f"{instruction_correct}\n\n"
        f"{instruction_clean}\n\n"
        "HARD_RULES:\n"
        "- Return ONLY complete valid Python code.\n"
        "- No explanation. No markdown fences.\n"
        "- Preserve original function names, parameter signatures, public interface, and number of top-level functions.\n"
        "- Make minimal edits.\n"
        "- Prefer keeping the original code over making a risky change.\n"
        "- When multiple fixes are possible, prefer the simpler, cleaner, lower-branch version.\n"
        "- If any modification is not clearly justified by the task, spec, or original code, keep that part unchanged.\n"
        "- If uncertainty remains, return ORIGINAL CODE unchanged.\n\n"
        "SPEC:\n"
        f"{spec if spec else 'unknown'}\n\n"
        "USER TASK:\n"
        f"{task_description}\n\n"
        "ORIGINAL CODE:\n"
        f"{original_code if original_code else '[EMPTY]'}\n"
    )


def _build_cleaner_prompt(spec, original_code, selected_code, instruction_clean):
    return (
        "ROLE: CLEANER_AGENT\n"
        "Goal: minimally simplify and clean the selected code while preserving behavior exactly.\n"
        "BACKGROUND_GUIDANCE:\n"
        f"{instruction_clean}\n\n"
        "HARD_RULES:\n"
        "- Return ONLY valid Python code.\n"
        "- No explanation. No markdown fences.\n"
        "- Preserve function names, parameter signatures, public interface, and number of top-level functions exactly.\n"
        "- Do not perform large rewrites.\n"
        "- Prefer early returns, reduced nesting, smaller repeated logic, and cleaner naming only when clearly safe.\n"
        "- Prefer a lower-complexity control flow when semantics stay identical.\n"
        "- If any cleanup may change behavior, return SELECTED CODE unchanged.\n\n"
        "SPEC:\n"
        f"{spec if spec else 'unknown'}\n\n"
        "ORIGINAL CODE:\n"
        f"{original_code if original_code else '[EMPTY]'}\n\n"
        "SELECTED CODE:\n"
        f"{selected_code}\n"
    )


def _build_verifier_prompt(spec, task_description, original_code, baseline_code, final_candidate):
    return (
        "ROLE: VERIFY_AGENT\n"
        "Return ONLY Python code.\n"
        "Compare FINAL_CANDIDATE with BASELINE_CODE using the task, spec, and original interface.\n"
        "If FINAL_CANDIDATE is fully consistent, no riskier than BASELINE_CODE, and not more complex without good reason, return FINAL_CANDIDATE unchanged.\n"
        "Otherwise return BASELINE_CODE unchanged.\n"
        "Be conservative.\n\n"
        "SPEC:\n"
        f"{spec if spec else 'unknown'}\n\n"
        "USER TASK:\n"
        f"{task_description}\n\n"
        "ORIGINAL CODE:\n"
        f"{original_code if original_code else '[EMPTY]'}\n\n"
        "BASELINE_CODE:\n"
        f"{baseline_code}\n\n"
        "FINAL_CANDIDATE:\n"
        f"{final_candidate if final_candidate else '[EMPTY]'}\n"
    )


def _select_baseline(candidate_map, decision):
    picked = _pick_by_decision(decision, candidate_map)
    if picked is not None:
        return picked
    ranked = _rank_candidates(list(candidate_map.values()))
    print("[solve] ranked_candidates=", [(c.label, c.score, c.valid, c.complexity) for c in ranked])
    return _best_fallback(ranked)


def _build_critic_prompt(spec, task_description, original_code, candidate_code):
    return (
        "ROLE: CRITIC_AGENT\n"
        "Do NOT write code.\n"
        "Return plain text only with exactly these 5 lines:\n"
        "MAJOR_RISK: ...\n"
        "INTERFACE_CHECK: ...\n"
        "BEHAVIOR_CHECK: ...\n"
        "SIMPLIFY_HINT: ...\n"
        "REPAIR_PLAN: ...\n"
        "Keep each line short and concrete. If no issue is clear, write 'none'.\n\n"
        "SPEC:\n"
        f"{spec if spec else 'unknown'}\n\n"
        "USER TASK:\n"
        f"{task_description}\n\n"
        "ORIGINAL CODE:\n"
        f"{original_code if original_code else '[EMPTY]'}\n\n"
        "CANDIDATE CODE:\n"
        f"{candidate_code if candidate_code else '[EMPTY]'}\n"
    )


def _build_revise_prompt(spec, task_description, original_code, candidate_code, critique, instruction_clean):
    return (
        "ROLE: REVISE_AGENT\n"
        "Goal: revise CANDIDATE CODE according to CRITIQUE while preserving behavior and interface.\n"
        "Return ONLY valid Python code.\n"
        "No explanation. No markdown fences.\n"
        "Preserve original function names, parameter signatures, public interface, and number of top-level functions exactly.\n"
        "Prefer minimal safe edits and lower-branch control flow.\n"
        "If the critique is weak or uncertain, return CANDIDATE CODE unchanged.\n\n"
        "STYLE_GUIDANCE:\n"
        f"{instruction_clean}\n\n"
        "SPEC:\n"
        f"{spec if spec else 'unknown'}\n\n"
        "USER TASK:\n"
        f"{task_description}\n\n"
        "ORIGINAL CODE:\n"
        f"{original_code if original_code else '[EMPTY]'}\n\n"
        "CANDIDATE CODE:\n"
        f"{candidate_code if candidate_code else '[EMPTY]'}\n\n"
        "CRITIQUE:\n"
        f"{critique if critique else 'none'}\n"
    )


def _build_judge_prompt(spec, original_code, candidate_payload):
    labels = ", ".join(candidate_payload)
    body = []
    for label, code in candidate_payload.items():
        body.append(f"{label}:\n{code if code else '[EMPTY]'}")
    joined = "\n\n".join(body)
    return (
        "ROLE: FINAL_JUDGE\n"
        f"Return exactly ONE token only from: ORIGINAL or {labels} or NONE.\n"
        "Prefer correctness first, then interface preservation, then minimal edits, then lower complexity.\n"
        "Choose ORIGINAL if uncertainty remains.\n\n"
        "SPEC:\n"
        f"{spec if spec else 'unknown'}\n\n"
        "ORIGINAL CODE:\n"
        f"{original_code if original_code else '[EMPTY]'}\n\n"
        f"{joined}\n"
    )


def _collect_candidates(
    original_code,
    original_meta,
    task_description,
    instruction_correct,
    instruction_clean,
    spec,
    client_base,
    client_tune,
    model,
    analysis_cache,
):
    original_facts = _analyze_code(original_code, analysis_cache) if original_code else None
    original_complexity = original_facts.complexity if original_facts else None

    raw_a = _ask_model(
        "draft_a",
        client_base,
        model,
        _build_repair_prompt_a(spec, task_description, original_code, instruction_correct),
    )
    raw_b = _ask_model(
        "draft_b",
        client_tune,
        model,
        _build_repair_prompt_b(spec, task_description, original_code, instruction_correct, instruction_clean),
    )

    cand_a = _score_candidate(raw_a, original_code, original_meta, original_complexity, "A", analysis_cache)
    cand_b = _score_candidate(raw_b, original_code, original_meta, original_complexity, "B", analysis_cache)

    critique_a = _ask_model(
        "critique_a",
        client_tune,
        model,
        _build_critic_prompt(spec, task_description, original_code, cand_a.code),
    ) if cand_a.code else ""
    critique_b = _ask_model(
        "critique_b",
        client_base,
        model,
        _build_critic_prompt(spec, task_description, original_code, cand_b.code),
    ) if cand_b.code else ""

    raw_a2 = _ask_model(
        "repair_a",
        client_base,
        model,
        _build_revise_prompt(spec, task_description, original_code, cand_a.code, critique_a, instruction_clean),
    ) if cand_a.code else ""
    raw_b2 = _ask_model(
        "repair_b",
        client_tune,
        model,
        _build_revise_prompt(spec, task_description, original_code, cand_b.code, critique_b, instruction_clean),
    ) if cand_b.code else ""

    candidate_map = {
        "ORIGINAL": _score_candidate(original_code, original_code, original_meta, original_complexity, "ORIGINAL", analysis_cache),
        "A": cand_a,
        "B": cand_b,
        "A2": _score_candidate(raw_a2, original_code, original_meta, original_complexity, "A2", analysis_cache),
        "B2": _score_candidate(raw_b2, original_code, original_meta, original_complexity, "B2", analysis_cache),
    }
    print("[solve] cand_a=", candidate_map["A"].code)
    print("[solve] cand_b=", candidate_map["B"].code)
    print("[solve] cand_a2=", candidate_map["A2"].code)
    print("[solve] cand_b2=", candidate_map["B2"].code)
    return candidate_map


def _judge_top_candidates(candidate_map, spec, original_code, client_base, model):
    ranked = _rank_candidates(list(candidate_map.values()))
    short_list = {}
    for candidate in ranked:
        if candidate.label == "ORIGINAL":
            continue
        if candidate.valid and candidate.label not in short_list:
            short_list[candidate.label] = candidate.code
        if len(short_list) == 3:
            break

    if not short_list:
        return ""

    judge_raw = _ask_model(
        "judge",
        client_base,
        model,
        _build_judge_prompt(spec, original_code, short_list),
    )
    return _normalize_decision(judge_raw, ("ORIGINAL", "A", "B", "A2", "B2", "NONE"))


def _verify_selected(
    selected,
    spec,
    task_description,
    original_code,
    original_meta,
    client_base,
    model,
    analysis_cache,
):
    if not selected.code or selected.label == "ORIGINAL":
        return selected

    original_facts = _analyze_code(original_code, analysis_cache) if original_code else None
    original_complexity = original_facts.complexity if original_facts else None

    verified_raw = _ask_model(
        "verifier",
        client_base,
        model,
        _build_verifier_prompt(
            spec=spec,
            task_description=task_description,
            original_code=original_code,
            baseline_code=selected.code,
            final_candidate=selected.code,
        ),
    )
    verified_candidate = _score_candidate(
        verified_raw, original_code, original_meta, original_complexity, "VERIFIED", analysis_cache
    )
    print("[solve] verified_candidate=", verified_candidate.code)
    return verified_candidate if verified_candidate.valid else selected


def solve(
    client_base,
    client_tune,
    model,
    task_description,
    original_code,
    instruction_correct,
    instruction_clean,
):
    print("[solve] task_description=", task_description)

    task_description = _safe_text(task_description)
    instruction_correct = _safe_text(instruction_correct)
    instruction_clean = _safe_text(instruction_clean)

    raw_original = _safe_text(original_code)
    normalized_original = _extract_original_code(raw_original) or _strip_code_fence(raw_original)
    analysis_cache = {}
    original_facts = _analyze_code(normalized_original, analysis_cache) if normalized_original else None
    original_meta = original_facts.meta if original_facts else None

    print("[solve] original_code=", normalized_original)

    spec = _ask_model(
        "spec",
        client_base,
        model,
        _build_spec_prompt(task_description, normalized_original),
    ).strip()

    candidate_map = _collect_candidates(
        original_code=normalized_original,
        original_meta=original_meta,
        task_description=task_description,
        instruction_correct=instruction_correct,
        instruction_clean=instruction_clean,
        spec=spec,
        client_base=client_base,
        client_tune=client_tune,
        model=model,
        analysis_cache=analysis_cache,
    )

    decision = _judge_top_candidates(
        candidate_map=candidate_map,
        spec=spec,
        original_code=normalized_original,
        client_base=client_base,
        model=model,
    )
    print("[solve] judge_decision=", decision)

    selected = _select_baseline(candidate_map, decision)
    print("[solve] selected_label=", selected.label)
    print("[solve] selected_code=", selected.code)

    if not selected.code:
        print("[solve] no selected_code, final fallback to original")
        return normalized_original if isinstance(normalized_original, str) else ""

    finalized = _verify_selected(
        selected=selected,
        spec=spec,
        task_description=task_description,
        original_code=normalized_original,
        original_meta=original_meta,
        client_base=client_base,
        model=model,
        analysis_cache=analysis_cache,
    )
    print("[solve] finalized_label=", finalized.label)
    print("[solve] finalized_code=", finalized.code)

    if finalized.valid and finalized.code:
        return finalized.code
    if selected.valid and selected.code:
        return selected.code

    original_candidate = candidate_map.get("ORIGINAL")
    if original_candidate and original_candidate.code:
        print("[solve] fallback to original candidate")
        return original_candidate.code

    print("[solve] final fallback")
    return normalized_original if isinstance(normalized_original, str) else ""
