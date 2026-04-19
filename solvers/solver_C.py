import ast
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


_CODE_BLOCK_RE = re.compile(r"```(?:[a-zA-Z0-9_+\-]*)\s*(.*?)```", re.DOTALL)
_CODE_START_RE = re.compile(r"(?m)^(?:async\s+def |def |class |from |import |if __name__ ==)")
_REQUIRED_SPEC_KEYS = (
    "INTENT",
    "INPUTS",
    "OUTPUTS",
    "MUST_PRESERVE",
    "ALLOWED_CHANGES",
    "AMBIGUITIES",
)


@dataclass(frozen=True)
class CodeFacts:
    code: str
    compiles: bool
    meta: Optional[tuple]
    complexity: Optional[int]
    looks_like_code: bool
    explanatory: bool
    line_count: int


@dataclass
class Candidate:
    label: str
    code: str
    valid: bool
    compiles: bool
    interface_ok: bool
    complexity: Optional[int]
    score: float
    source: str = ""


def _safe_text(value) -> str:
    return value if isinstance(value, str) else ""


def _extract_code_text(text) -> str:
    text = _safe_text(text).strip()
    if not text:
        return ""

    blocks = _CODE_BLOCK_RE.findall(text)
    if blocks:
        return max(blocks, key=lambda block: len(block.strip())).strip()

    match = _CODE_START_RE.search(text)
    if match:
        return text[match.start():].strip()
    return text


def _strip_code_fence(text) -> str:
    return _extract_code_text(text).strip()


def _try_external_fix(code: str) -> str:
    try:
        fixer = globals().get("cut")
        if fixer is not None and hasattr(fixer, "fix_code"):
            fixed = fixer.fix_code(code)
            if isinstance(fixed, str) and fixed.strip():
                return fixed.strip()
    except Exception:
        pass
    return code.strip()


def _safe_fix_code(text) -> str:
    code = _strip_code_fence(text)
    return _try_external_fix(code) if code else ""


def _looks_like_code(text) -> bool:
    text = _safe_text(text).strip()
    if not text:
        return False
    markers = (
        "def ",
        "async def ",
        "class ",
        "import ",
        "from ",
        "return ",
        "for ",
        "while ",
        "if ",
        "try:",
        "except",
        "with ",
        "=",
    )
    hits = sum(token in text for token in markers)
    return hits >= 2 or ("\n" in text and ("def " in text or "class " in text))


def _extract_original_code(text) -> str:
    text = _safe_text(text).strip()
    if not text:
        return ""
    extracted = _extract_code_text(text)
    if _looks_like_code(extracted):
        return extracted.strip()
    return text if _looks_like_code(text) else ""


def _is_explanatory_text(code: str) -> bool:
    low = code.lower().strip()
    prefixes = (
        "here is",
        "here's",
        "below is",
        "the code",
        "explanation",
        "i revised",
        "i updated",
    )
    return any(low.startswith(prefix) for prefix in prefixes)


def _analyze_tree(tree: ast.AST) -> Tuple[tuple, int]:
    body = tuple(getattr(tree, "body", []))
    top_level_ids = {id(node) for node in body}
    meta = []
    complexity = 1
    branch_nodes = (
        ast.If,
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.Try,
        ast.ExceptHandler,
        ast.With,
        ast.AsyncWith,
        ast.IfExp,
        ast.comprehension,
    )

    for node in ast.walk(tree):
        if id(node) in top_level_ids:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = node.args
                meta.append(
                    (
                        "async" if isinstance(node, ast.AsyncFunctionDef) else "def",
                        node.name,
                        tuple(arg.arg for arg in getattr(args, "posonlyargs", [])),
                        tuple(arg.arg for arg in args.args),
                        args.vararg.arg if args.vararg else None,
                        tuple(arg.arg for arg in args.kwonlyargs),
                        args.kwarg.arg if args.kwarg else None,
                    )
                )
            elif isinstance(node, ast.ClassDef):
                meta.append(("class", node.name))

        if isinstance(node, branch_nodes):
            complexity += 1
        elif isinstance(node, ast.BoolOp):
            complexity += max(0, len(node.values) - 1)

    return tuple(meta), complexity


def _analyze_code(code: str, cache: Dict[str, "CodeFacts"]) -> "CodeFacts":
    code = _safe_text(code).strip()
    cached = cache.get(code)
    if cached is not None:
        return cached

    looks_like = _looks_like_code(code)
    explanatory = _is_explanatory_text(code)
    if not code:
        facts = CodeFacts("", False, None, None, False, False, 0)
        cache[code] = facts
        return facts

    try:
        tree = ast.parse(code)
        compile(tree, "<generated>", "exec")
        meta, complexity = _analyze_tree(tree)
        facts = CodeFacts(
            code=code,
            compiles=True,
            meta=meta,
            complexity=complexity,
            looks_like_code=looks_like,
            explanatory=explanatory,
            line_count=len(code.splitlines()),
        )
    except Exception:
        facts = CodeFacts(
            code=code,
            compiles=False,
            meta=None,
            complexity=None,
            looks_like_code=looks_like,
            explanatory=explanatory,
            line_count=len(code.splitlines()),
        )

    cache[code] = facts
    return facts


def _infer_once(client, model, prompt: str) -> str:
    messages = [{"role": "user", "content": prompt}]
    try:
        response = client.chat.completions.create(messages=messages, model=model)
        return _safe_text(response.choices[0].message.content)
    except Exception as exc:
        print(f"[_infer_once] error: {exc}")
        return ""


def _ask_model(name: str, client, model, prompt: str) -> str:
    output = _infer_once(client, model, prompt)
    print(f"[solve][{name}] {output}")
    return output


def _parse_spec_lines(text: str) -> Dict[str, str]:
    result = {key: "unknown" for key in _REQUIRED_SPEC_KEYS}
    for raw_line in _safe_text(text).splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip().upper()
        if key in result:
            value = value.strip() or "unknown"
            if len(value) >= len(result[key]):
                result[key] = value
    return result


def _merge_specs(*spec_texts: str) -> str:
    merged = {key: "unknown" for key in _REQUIRED_SPEC_KEYS}
    for spec_text in spec_texts:
        parsed = _parse_spec_lines(spec_text)
        for key in _REQUIRED_SPEC_KEYS:
            value = parsed.get(key, "unknown")
            if value.lower() != "unknown" and len(value) >= len(merged[key]):
                merged[key] = value
    return "\n".join(f"{key}: {merged[key]}" for key in _REQUIRED_SPEC_KEYS)


def _task_risk(task_description: str, original_code: str, facts: Optional[CodeFacts]) -> int:
    task_low = task_description.lower()
    code_low = original_code.lower()
    score = 0
    risky_terms = (
        "optimize",
        "refactor",
        "rewrite",
        "architecture",
        "bug",
        "fix",
        "performance",
        "async",
        "thread",
        "concurrency",
        "cache",
        "multi-agent",
        "framework",
    )
    score += sum(term in task_low for term in risky_terms)
    score += task_description.count("\n") // 6
    score += code_low.count("class ")
    score += code_low.count("def ") // 4
    if facts and facts.complexity:
        score += facts.complexity // 12
    return score


def _normalize_decision(text: str, labels: Sequence[str]) -> str:
    up = _safe_text(text).strip().upper()
    for label in labels:
        label_up = label.upper()
        if re.search(rf"\b{re.escape(label_up)}\b", up):
            return label_up
    return ""


def _score_candidate(
    raw_code: str,
    label: str,
    original_code: str,
    original_meta: Optional[tuple],
    original_complexity: Optional[int],
    cache: Dict[str, CodeFacts],
    source: str = "",
) -> Candidate:
    cleaned = _safe_fix_code(raw_code)
    if not cleaned:
        return Candidate(label, "", False, False, False, None, float("-inf"), source)

    facts = _analyze_code(cleaned, cache)
    interface_ok = True if not original_meta else facts.meta == original_meta
    valid = facts.looks_like_code and facts.compiles and interface_ok

    if not valid:
        score = -1000.0
        score += 10.0 if facts.looks_like_code else 0.0
        score += 20.0 if facts.compiles else 0.0
        score += 20.0 if interface_ok else 0.0
        return Candidate(label, cleaned, False, facts.compiles, interface_ok, facts.complexity, score, source)

    original_s = original_code.strip()
    cleaned_s = cleaned.strip()
    score = 100.0
    if label == "ORIGINAL":
        score += 10.0
    if cleaned_s == original_s:
        score += 18.0
    else:
        score += max(0.0, 12.0 - abs(len(cleaned_s) - len(original_s)) / 120.0)

    if facts.explanatory:
        score -= 40.0
    if "```" in cleaned:
        score -= 12.0

    lower = cleaned.lower()
    if "todo" in lower or "placeholder" in lower:
        score -= 25.0

    if facts.complexity is not None:
        score += max(0.0, 20.0 - float(facts.complexity))
        if original_complexity is not None and facts.complexity > original_complexity:
            score -= min(15.0, 1.5 * (facts.complexity - original_complexity))

    return Candidate(label, cleaned, True, True, True, facts.complexity, score, source)


def _dedupe_candidates(candidates: Iterable[Candidate]) -> List[Candidate]:
    best_by_code: Dict[str, Candidate] = {}
    for candidate in candidates:
        current = best_by_code.get(candidate.code)
        if current is None or candidate.score > current.score:
            best_by_code[candidate.code] = candidate
    return list(best_by_code.values())


def _rank_candidates(candidates: Sequence[Candidate]) -> List[Candidate]:
    return sorted(
        candidates,
        key=lambda item: (item.valid, item.interface_ok, item.compiles, item.score),
        reverse=True,
    )


def _build_spec_prompt(task_description: str, original_code: str) -> str:
    return (
        "ROLE: SPEC_AGENT\n"
        "Infer intent and hard constraints from task plus code.\n"
        "Do not write code.\n"
        "Return exactly these 6 lines:\n"
        "INTENT: ...\n"
        "INPUTS: ...\n"
        "OUTPUTS: ...\n"
        "MUST_PRESERVE: ...\n"
        "ALLOWED_CHANGES: ...\n"
        "AMBIGUITIES: ...\n"
        "Use unknown when uncertain.\n\n"
        "TASK:\n"
        f"{task_description}\n\n"
        "ORIGINAL_CODE:\n"
        f"{original_code or '[EMPTY]'}\n"
    )


def _build_repair_prompt(
    role: str,
    spec: str,
    task_description: str,
    original_code: str,
    guidance: str,
    extra_rules: str = "",
) -> str:
    return (
        f"ROLE: {role}\n"
        "Return only complete valid Python code.\n"
        "No markdown fences. No explanation.\n"
        "Preserve original function names, parameter signatures, public interface, and number of top-level functions.\n"
        "Prefer directly runnable, correct, low-nesting code.\n"
        "If the task is materially ambiguous, return ORIGINAL_CODE unchanged.\n"
        f"{extra_rules}\n\n"
        "GUIDANCE:\n"
        f"{guidance}\n\n"
        "SPEC:\n"
        f"{spec}\n\n"
        "TASK:\n"
        f"{task_description}\n\n"
        "ORIGINAL_CODE:\n"
        f"{original_code or '[EMPTY]'}\n"
    )


def _build_critic_prompt(spec: str, task_description: str, original_code: str, candidate_code: str) -> str:
    return (
        "ROLE: CRITIC_AGENT\n"
        "Do not write code.\n"
        "Return exactly these 5 lines:\n"
        "MAJOR_RISK: ...\n"
        "INTERFACE_CHECK: ...\n"
        "BEHAVIOR_CHECK: ...\n"
        "SIMPLIFY_HINT: ...\n"
        "REVISION_HINT: ...\n"
        "Use none when no issue is clear.\n\n"
        "SPEC:\n"
        f"{spec}\n\n"
        "TASK:\n"
        f"{task_description}\n\n"
        "ORIGINAL_CODE:\n"
        f"{original_code or '[EMPTY]'}\n\n"
        "CANDIDATE_CODE:\n"
        f"{candidate_code or '[EMPTY]'}\n"
    )


def _build_revise_prompt(
    spec: str,
    task_description: str,
    original_code: str,
    baseline_code: str,
    critique: str,
    guidance: str,
) -> str:
    return (
        "ROLE: REVISE_AGENT\n"
        "Return only valid Python code.\n"
        "No markdown fences. No explanation.\n"
        "Preserve original function names, parameter signatures, public interface, and number of top-level functions.\n"
        "Prefer minimal safe edits.\n"
        "If critique is weak or uncertain, return BASELINE_CODE unchanged.\n\n"
        "GUIDANCE:\n"
        f"{guidance}\n\n"
        "SPEC:\n"
        f"{spec}\n\n"
        "TASK:\n"
        f"{task_description}\n\n"
        "ORIGINAL_CODE:\n"
        f"{original_code or '[EMPTY]'}\n\n"
        "BASELINE_CODE:\n"
        f"{baseline_code or '[EMPTY]'}\n\n"
        "CRITIQUE:\n"
        f"{critique or 'none'}\n"
    )


def _build_verify_prompt(spec: str, task_description: str, original_code: str, candidate_code: str) -> str:
    return (
        "ROLE: VERIFY_AGENT\n"
        "Return only valid Python code.\n"
        "If CANDIDATE_CODE is clearly correct, interface-safe, and not riskier than ORIGINAL_CODE, return CANDIDATE_CODE unchanged.\n"
        "Otherwise return ORIGINAL_CODE unchanged.\n\n"
        "SPEC:\n"
        f"{spec}\n\n"
        "TASK:\n"
        f"{task_description}\n\n"
        "ORIGINAL_CODE:\n"
        f"{original_code or '[EMPTY]'}\n\n"
        "CANDIDATE_CODE:\n"
        f"{candidate_code or '[EMPTY]'}\n"
    )


def _build_pairwise_judge_prompt(spec: str, original_code: str, left: Candidate, right: Candidate) -> str:
    return (
        "ROLE: JUDGE_AGENT\n"
        "Return exactly one token: LEFT or RIGHT or ORIGINAL.\n"
        "Prefer correctness first, then interface preservation, then lower complexity, then minimal edits.\n"
        "If uncertain, choose ORIGINAL.\n\n"
        "SPEC:\n"
        f"{spec}\n\n"
        "ORIGINAL_CODE:\n"
        f"{original_code or '[EMPTY]'}\n\n"
        f"LEFT ({left.label}):\n{left.code or '[EMPTY]'}\n\n"
        f"RIGHT ({right.label}):\n{right.code or '[EMPTY]'}\n"
    )


def _build_strategy_prompt(spec: str, task_description: str, original_code: str) -> str:
    return (
        "ROLE: STRATEGY_AGENT\n"
        "Do not write code.\n"
        "Return exactly 2 short lines:\n"
        "PLAN_A: ...\n"
        "PLAN_B: ...\n"
        "Plans must preserve public interface and differ in repair strategy.\n\n"
        "SPEC:\n"
        f"{spec}\n\n"
        "TASK:\n"
        f"{task_description}\n\n"
        "ORIGINAL_CODE:\n"
        f"{original_code or '[EMPTY]'}\n"
    )


def _build_plan_repair_prompt(
    role: str,
    plan_text: str,
    spec: str,
    task_description: str,
    original_code: str,
    guidance: str,
) -> str:
    return (
        f"ROLE: {role}\n"
        "Return only complete valid Python code.\n"
        "No markdown fences. No explanation.\n"
        "Preserve original function names, parameter signatures, public interface, and number of top-level functions.\n"
        "Apply the plan conservatively.\n"
        "If the plan conflicts with original interface or task evidence, keep the original code for that part.\n\n"
        "PLAN:\n"
        f"{plan_text}\n\n"
        "GUIDANCE:\n"
        f"{guidance}\n\n"
        "SPEC:\n"
        f"{spec}\n\n"
        "TASK:\n"
        f"{task_description}\n\n"
        "ORIGINAL_CODE:\n"
        f"{original_code or '[EMPTY]'}\n"
    )


def _pairwise_pick(
    spec: str,
    original_code: str,
    left: Candidate,
    right: Candidate,
    client_base,
    model,
) -> Candidate:
    if left.score >= right.score + 8.0:
        return left
    if right.score >= left.score + 8.0:
        return right

    decision = _normalize_decision(
        _ask_model(
            "pairwise_judge",
            client_base,
            model,
            _build_pairwise_judge_prompt(spec, original_code, left, right),
        ),
        ("LEFT", "RIGHT", "ORIGINAL"),
    )
    if decision == "LEFT":
        return left
    if decision == "RIGHT":
        return right
    if left.label == "ORIGINAL":
        return left
    if right.label == "ORIGINAL":
        return right
    return left


def _prepare_context(task_description, original_code, instruction_correct, instruction_clean):
    task_description = _safe_text(task_description)
    instruction_correct = _safe_text(instruction_correct)
    instruction_clean = _safe_text(instruction_clean)
    raw_original = _safe_text(original_code)
    normalized_original = _extract_original_code(raw_original) or _strip_code_fence(raw_original)

    cache: Dict[str, CodeFacts] = {}
    facts = _analyze_code(normalized_original, cache) if normalized_original else CodeFacts("", False, None, None, False, False, 0)
    return {
        "task_description": task_description,
        "instruction_correct": instruction_correct,
        "instruction_clean": instruction_clean,
        "original_code": normalized_original,
        "original_facts": facts,
        "original_meta": facts.meta,
        "original_complexity": facts.complexity,
        "cache": cache,
    }


def solve(
    client_base,
    client_tune,
    model,
    task_description,
    original_code,
    instruction_correct,
    instruction_clean,
):
    ctx = _prepare_context(task_description, original_code, instruction_correct, instruction_clean)
    task_description = ctx["task_description"]
    instruction_correct = ctx["instruction_correct"]
    instruction_clean = ctx["instruction_clean"]
    original_code = ctx["original_code"]
    original_meta = ctx["original_meta"]
    original_complexity = ctx["original_complexity"]
    original_facts = ctx["original_facts"]
    cache = ctx["cache"]

    risk = _task_risk(task_description, original_code, original_facts)

    spec_base = _ask_model("spec_base", client_base, model, _build_spec_prompt(task_description, original_code))
    spec_tune = _ask_model("spec_tune", client_tune, model, _build_spec_prompt(task_description, original_code))
    spec = _merge_specs(spec_base, spec_tune)

    strategy_raw = _ask_model("strategy", client_base, model, _build_strategy_prompt(spec, task_description, original_code))
    plan_a = "Preserve structure and repair only incorrect logic."
    plan_b = "Reduce branching and repeated logic while preserving interface."
    for line in _safe_text(strategy_raw).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().upper()
        value = value.strip()
        if key == "PLAN_A" and value:
            plan_a = value
        elif key == "PLAN_B" and value:
            plan_b = value

    original_candidate = _score_candidate(
        original_code,
        "ORIGINAL",
        original_code,
        original_meta,
        original_complexity,
        cache,
        source="original",
    )
    seed_a = _score_candidate(
        _ask_model(
            "seed_a",
            client_base,
            model,
            _build_plan_repair_prompt(
                "PLAN_SOLVER_A",
                plan_a,
                spec,
                task_description,
                original_code,
                instruction_correct,
            ),
        ),
        "SEED_A",
        original_code,
        original_meta,
        original_complexity,
        cache,
        source="seed_a",
    )
    seed_b = _score_candidate(
        _ask_model(
            "seed_b",
            client_tune,
            model,
            _build_plan_repair_prompt(
                "PLAN_SOLVER_B",
                plan_b,
                spec,
                task_description,
                original_code,
                instruction_correct + "\n\n" + instruction_clean,
            ),
        ),
        "SEED_B",
        original_code,
        original_meta,
        original_complexity,
        cache,
        source="seed_b",
    )

    beam = _rank_candidates(_dedupe_candidates([original_candidate, seed_a, seed_b]))[:2]
    expansions = []
    for node in beam:
        if not node.valid or node.label == "ORIGINAL":
            continue
        critic_client = client_tune if node.source == "seed_a" else client_base
        revise_client = client_base if critic_client is client_tune else client_tune
        critique = _ask_model(
            f"beam_critique_{node.label}",
            critic_client,
            model,
            _build_critic_prompt(spec, task_description, original_code, node.code),
        )
        revised = _score_candidate(
            _ask_model(
                f"beam_revise_{node.label}",
                revise_client,
                model,
                _build_revise_prompt(
                    spec,
                    task_description,
                    original_code,
                    node.code,
                    critique,
                    instruction_clean,
                ),
            ),
            f"{node.label}_R1",
            original_code,
            original_meta,
            original_complexity,
            cache,
            source=f"beam_revise_{node.label}",
        )
        expansions.append(revised)

    pool = _rank_candidates(_dedupe_candidates([original_candidate, seed_a, seed_b] + expansions))
    champion = pool[0] if pool else original_candidate

    if champion.valid and champion.label != "ORIGINAL" and risk >= 4:
        second_critique = _ask_model(
            "champion_second_critique",
            client_base,
            model,
            _build_critic_prompt(spec, task_description, original_code, champion.code),
        )
        second_pass = _score_candidate(
            _ask_model(
                "champion_second_revise",
                client_tune,
                model,
                _build_revise_prompt(
                    spec,
                    task_description,
                    original_code,
                    champion.code,
                    second_critique,
                    instruction_clean,
                ),
            ),
            "CHAMPION_R2",
            original_code,
            original_meta,
            original_complexity,
            cache,
            source="champion_second_revise",
        )
        pool = _rank_candidates(_dedupe_candidates(pool + [second_pass]))
        champion = pool[0]

    finalists = [candidate for candidate in pool if candidate.valid][:3]
    if not finalists:
        return original_candidate.code

    winner = finalists[0]
    for challenger in finalists[1:]:
        winner = _pairwise_pick(spec, original_code, winner, challenger, client_base, model)

    if winner.label == "ORIGINAL":
        return original_candidate.code

    verified = _score_candidate(
        _ask_model(
            "tree_verify",
            client_base,
            model,
            _build_verify_prompt(spec, task_description, original_code, winner.code),
        ),
        "TREE_VERIFIED",
        original_code,
        original_meta,
        original_complexity,
        cache,
        source="tree_verify",
    )
    if verified.valid:
        return verified.code
    return winner.code if winner.valid else original_candidate.code
