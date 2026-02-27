from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from src.meter.stress import StressDict
from src.meter.validator import MeterCheckResult, check_meter_poem
from src.rhyme.validator import RhymeCheckResult, check_rhyme
from src.utils.text import split_nonempty_lines


# ---------------------------------------------------------------------------
# Meter Accuracy
# ---------------------------------------------------------------------------

def meter_accuracy(poem_text: str, meter: str, foot_count: int, stress_dict: StressDict, allowed_mismatches: int = 2) -> float:
    results = check_meter_poem(poem_text, meter=meter, foot_count=foot_count, stress_dict=stress_dict, allowed_mismatches=allowed_mismatches)
    if not results:
        return 1.0
    return sum(1 for r in results if r.ok) / len(results)


# ---------------------------------------------------------------------------
# Rhyme Accuracy
# ---------------------------------------------------------------------------

def rhyme_accuracy(poem_text: str, scheme: str, stress_dict: StressDict, threshold: float = 0.7) -> float:
    result = check_rhyme(poem_text, scheme=scheme, stress_dict=stress_dict, threshold=threshold)
    if not result.pairs:
        return 1.0
    return sum(1 for p in result.pairs if p.rhyme_ok) / len(result.pairs)


# ---------------------------------------------------------------------------
# Regeneration Success Rate
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RegenerationStats:
    initial_meter_violations: int
    final_meter_violations: int
    initial_rhyme_violations: int
    final_rhyme_violations: int
    meter_fixed: int
    rhyme_fixed: int
    success_rate: float


def regeneration_success_rate(
    initial_meter_results: list[MeterCheckResult],
    final_meter_results: list[MeterCheckResult],
    initial_rhyme_result: RhymeCheckResult,
    final_rhyme_result: RhymeCheckResult,
) -> RegenerationStats:
    init_m_violations = sum(1 for r in initial_meter_results if not r.ok)
    final_m_violations = sum(1 for r in final_meter_results if not r.ok)

    init_r_violations = sum(1 for p in initial_rhyme_result.pairs if not p.rhyme_ok)
    final_r_violations = sum(1 for p in final_rhyme_result.pairs if not p.rhyme_ok)

    meter_fixed = max(0, init_m_violations - final_m_violations)
    rhyme_fixed = max(0, init_r_violations - final_r_violations)

    total_initial = init_m_violations + init_r_violations
    total_fixed = meter_fixed + rhyme_fixed
    rate = total_fixed / total_initial if total_initial > 0 else 1.0

    return RegenerationStats(
        initial_meter_violations=init_m_violations,
        final_meter_violations=final_m_violations,
        initial_rhyme_violations=init_r_violations,
        final_rhyme_violations=final_r_violations,
        meter_fixed=meter_fixed,
        rhyme_fixed=rhyme_fixed,
        success_rate=rate,
    )


# ---------------------------------------------------------------------------
# BLEU (simple n-gram based, no external deps)
# ---------------------------------------------------------------------------

def _tokenize_simple(text: str) -> list[str]:
    return re.findall(r"[а-яіїєґa-z'ʼ-]+", text.lower())


def _ngrams(tokens: list[str], n: int) -> list[tuple[str, ...]]:
    return [tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def bleu_score(candidate: str, reference: str, max_n: int = 4) -> float:
    cand_tokens = _tokenize_simple(candidate)
    ref_tokens = _tokenize_simple(reference)

    if not cand_tokens or not ref_tokens:
        return 0.0

    brevity_penalty = min(1.0, math.exp(1 - len(ref_tokens) / len(cand_tokens))) if len(cand_tokens) > 0 else 0.0

    log_avg = 0.0
    weight = 1.0 / max_n
    for n in range(1, max_n + 1):
        cand_ngrams = _ngrams(cand_tokens, n)
        ref_ngrams = _ngrams(ref_tokens, n)
        if not cand_ngrams:
            return 0.0
        ref_counts: Counter[tuple[str, ...]] = Counter(ref_ngrams)
        cand_counts: Counter[tuple[str, ...]] = Counter(cand_ngrams)
        clipped = sum(min(cand_counts[ng], ref_counts[ng]) for ng in cand_counts)
        precision = clipped / len(cand_ngrams) if cand_ngrams else 0.0
        if precision == 0:
            return 0.0
        log_avg += weight * math.log(precision)

    return brevity_penalty * math.exp(log_avg)


# ---------------------------------------------------------------------------
# ROUGE-L (longest common subsequence based)
# ---------------------------------------------------------------------------

def _lcs_length(x: list[str], y: list[str]) -> int:
    m, n = len(x), len(y)
    if m == 0 or n == 0:
        return 0
    prev = [0] * (n + 1)
    for i in range(1, m + 1):
        curr = [0] * (n + 1)
        for j in range(1, n + 1):
            if x[i - 1] == y[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(prev[j], curr[j - 1])
        prev = curr
    return prev[n]


def rouge_l_score(candidate: str, reference: str) -> float:
    cand_tokens = _tokenize_simple(candidate)
    ref_tokens = _tokenize_simple(reference)

    if not cand_tokens or not ref_tokens:
        return 0.0

    lcs = _lcs_length(cand_tokens, ref_tokens)
    precision = lcs / len(cand_tokens) if cand_tokens else 0.0
    recall = lcs / len(ref_tokens) if ref_tokens else 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


# ---------------------------------------------------------------------------
# BERTScore (optional, requires transformers)
# ---------------------------------------------------------------------------

def bert_score(candidate: str, reference: str, model_name: str = "bert-base-multilingual-cased") -> float | None:
    try:
        from transformers import AutoModel, AutoTokenizer
        import torch
    except ImportError:
        return None

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)
    model.eval()

    inputs_c = tokenizer(candidate, return_tensors="pt", truncation=True, max_length=512)
    inputs_r = tokenizer(reference, return_tensors="pt", truncation=True, max_length=512)

    with torch.no_grad():
        emb_c = model(**inputs_c).last_hidden_state.squeeze(0)
        emb_r = model(**inputs_r).last_hidden_state.squeeze(0)

    emb_c = emb_c / emb_c.norm(dim=-1, keepdim=True).clamp(min=1e-8)
    emb_r = emb_r / emb_r.norm(dim=-1, keepdim=True).clamp(min=1e-8)

    sim = torch.mm(emb_c, emb_r.T)
    precision = sim.max(dim=1).values.mean().item()
    recall = sim.max(dim=0).values.mean().item()
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


# ---------------------------------------------------------------------------
# Aggregate report
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EvaluationReport:
    meter_accuracy_pct: float
    rhyme_accuracy_pct: float
    bleu: float
    rouge_l: float
    bert_score_val: float | None


def evaluate_poem(
    poem_text: str,
    reference_text: str,
    meter: str,
    foot_count: int,
    rhyme_scheme: str,
    stress_dict: StressDict,
    compute_bertscore: bool = False,
) -> EvaluationReport:
    m_acc = meter_accuracy(poem_text, meter=meter, foot_count=foot_count, stress_dict=stress_dict)
    r_acc = rhyme_accuracy(poem_text, scheme=rhyme_scheme, stress_dict=stress_dict)
    bl = bleu_score(poem_text, reference_text)
    rl = rouge_l_score(poem_text, reference_text)
    bs = bert_score(poem_text, reference_text) if compute_bertscore else None

    return EvaluationReport(
        meter_accuracy_pct=m_acc * 100.0,
        rhyme_accuracy_pct=r_acc * 100.0,
        bleu=bl,
        rouge_l=rl,
        bert_score_val=bs,
    )
