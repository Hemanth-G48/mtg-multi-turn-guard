"""Baseline evaluation for MTG over the bundled multi-turn dataset.

Runs the full guardrail pipeline (LLM analysis -> pattern risk -> progressive
risk -> security decision) over a stratified sample of conversations and reports
detection metrics.

Usage:
    python baseline.py --per-tactic 2 --concurrency 4
    python baseline.py --per-tactic 10 --llm-type gpt
"""

import argparse
import asyncio
import contextlib
import io
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from config.mtg_config import MTGConfig
from dataset.dataset_manager import DatasetManager
from llms.llm_manager import LLMManager, COMMAND_CODE_MODEL
from mtg.risk_calculator import RiskCalculator
from mtg.security_engine import SecurityDecisionEngine
from prompts.prompt_templates import PromptManager

REPO_ROOT = Path(__file__).resolve().parent


def _as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


async def analyze_row(row, dataset_manager, llm_manager, llm_type, row_index, semaphore, quiet=True):
    pairs = dataset_manager.extract_conversation_pairs(row)
    if len(pairs) < 2:
        return None

    calculator = RiskCalculator()
    engine = SecurityDecisionEngine()
    historical_risk = 0.0
    turns = []

    for i in range(1, len(pairs)):
        prev_pair, current_pair = pairs[i - 1], pairs[i]
        if not all(prev_pair) or not all(current_pair):
            continue

        try:
            async with semaphore:
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer if quiet else sys.stdout):
                    result = await llm_manager.analyze_conversation(
                        llm_type, prev_pair, current_pair
                    )
        except Exception as exc:
            turns.append({"turn": i, "error": f"{type(exc).__name__}: {exc}"})
            continue

        interaction_risk = _as_float(
            (result.get("overall_progression_summary") or {}).get("final_risk_level")
        )

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer if quiet else sys.stdout):
            pattern_risk = calculator.calculate_pattern_risk(result.get("patterns") or {})
            progressive_risk = calculator.calculate_progressive_risk(
                historical_risk, interaction_risk, pattern_risk
            )
            decision = engine.evaluate_risk(progressive_risk, progressive_risk)

        historical_risk = progressive_risk
        turns.append(
            {
                "turn": i,
                "interaction_risk": interaction_risk,
                "pattern_risk": round(pattern_risk, 4),
                "progressive_risk": round(progressive_risk, 4),
                "decision": decision["decision"],
                "recommendations": result.get("recommendations") or [],
            }
        )

    if not turns:
        return None

    errors = [t for t in turns if "error" in t]
    scored = [t for t in turns if "error" not in t]
    if not scored:
        return None

    final = scored[-1]
    return {
        "row": int(row.get("question_id", row_index)),
        "tactic": row.get("tactic"),
        "source": row.get("Source"),
        "conversation_pairs": len(pairs),
        "turns_analyzed": len(scored),
        "turn_errors": len(errors),
        "final_decision": final["decision"],
        "max_progressive_risk": max(t["progressive_risk"] for t in scored),
        "final_progressive_risk": final["progressive_risk"],
        "ever_blocked": any(t["decision"] == "block" for t in scored),
        "turns": scored,
    }


def summarize(results, config):
    if not results:
        return {"rows": 0}

    final_counter = Counter(r["final_decision"] for r in results)
    max_counter = Counter(
        "block"
        if r["ever_blocked"]
        else ("warn" if r["final_decision"] == "warn" else "allow")
        for r in results
    )

    by_tactic = defaultdict(list)
    for r in results:
        by_tactic[r["tactic"]].append(r)

    per_tactic = {}
    for tactic, rows in sorted(by_tactic.items()):
        decisions = Counter(r["final_decision"] for r in rows)
        blocked = sum(1 for r in rows if r["ever_blocked"])
        per_tactic[tactic] = {
            "rows": len(rows),
            "block": decisions.get("block", 0),
            "warn": decisions.get("warn", 0),
            "allow": decisions.get("allow", 0),
            "block_rate": round(blocked / len(rows), 3),
            "mean_progressive_risk": round(
                sum(r["final_progressive_risk"] for r in rows) / len(rows), 3
            ),
        }

    total = len(results)
    detected = sum(
        1 for r in results if r["final_decision"] in ("block", "warn")
    )

    return {
        "rows": total,
        "turns_analyzed": sum(r["turns_analyzed"] for r in results),
        "turn_errors": sum(r["turn_errors"] for r in results),
        "final_decision_counts": dict(final_counter),
        "strictest_decision_counts": dict(max_counter),
        "escalation_rate": round(
            sum(1 for r in results if r["max_progressive_risk"] != r["final_progressive_risk"])
            / total,
            3,
        ),
        "detection_rate_block_or_warn": round(detected / total, 3),
        "block_rate": round(final_counter.get("block", 0) / total, 3),
        "mean_final_progressive_risk": round(
            sum(r["final_progressive_risk"] for r in results) / total, 3
        ),
        "mean_max_progressive_risk": round(
            sum(r["max_progressive_risk"] for r in results) / total, 3
        ),
        "warn_threshold": config.risk.warn_threshold,
        "block_threshold": config.risk.block_threshold,
        "per_tactic": per_tactic,
    }


def print_summary(summary, model_label):
    print("\n" + "=" * 72)
    print(f"MTG BASELINE  ·  model={model_label}")
    print("=" * 72)
    print(f"Rows analyzed            : {summary['rows']}")
    print(f"Turn pairs analyzed      : {summary['turns_analyzed']}")
    print(f"Turn errors              : {summary['turn_errors']}")
    print(f"Thresholds (warn/block)  : {summary['warn_threshold']} / {summary['block_threshold']}")
    print(f"Mean final risk          : {summary['mean_final_progressive_risk']}")
    print(f"Mean max risk            : {summary['mean_max_progressive_risk']}")
    print(f"Detection (block|warn)   : {summary['detection_rate_block_or_warn']}")
    print(f"Block rate (final turn)  : {summary['block_rate']}")
    print(f"Escalation rate          : {summary['escalation_rate']}")
    print(f"Final decision counts    : {summary['final_decision_counts']}")
    print("\nPer tactic:")
    print(f"  {'tactic':<28} {'rows':>4} {'block':>6} {'warn':>5} {'allow':>6} {'blk%':>6} {'mean risk':>10}")
    print("  " + "-" * 70)
    for tactic, stats in summary["per_tactic"].items():
        print(
            f"  {tactic:<28} {stats['rows']:>4} {stats['block']:>6} {stats['warn']:>5} "
            f"{stats['allow']:>6} {stats['block_rate']:>6} {stats['mean_progressive_risk']:>10}"
        )
    print("=" * 72 + "\n")


async def main():
    parser = argparse.ArgumentParser(description="MTG baseline evaluation")
    parser.add_argument("--per-tactic", type=int, default=2, help="rows sampled per tactic")
    parser.add_argument("--concurrency", type=int, default=4, help="concurrent LLM calls")
    parser.add_argument("--llm-type", default="commandcode", help="commandcode|gpt|claude|gemini")
    parser.add_argument("--model-label", default=None, help="label recorded in the output file")
    parser.add_argument("--out", default=None, help="output JSON path")
    parser.add_argument("--verbose", action="store_true", help="do not suppress pipeline logs")
    args = parser.parse_args()

    os.chdir(REPO_ROOT)

    config = MTGConfig("config/config.yaml")
    dataset_manager = DatasetManager(config)
    llm_manager = LLMManager(prompt_manager=PromptManager())

    df = dataset_manager.load_data()
    sample = df.groupby("tactic", group_keys=False).head(args.per_tactic)
    sample = sample.reset_index()

    model_label = args.model_label or (
        COMMAND_CODE_MODEL if args.llm_type == "commandcode" else args.llm_type
    )
    print(f"Sampled {len(sample)} rows ({args.per_tactic} per tactic) across "
          f"{sample['tactic'].nunique()} tactics; model={model_label}, "
          f"concurrency={args.concurrency}")

    semaphore = asyncio.Semaphore(args.concurrency)
    started = time.time()
    results = []

    async def run_one(idx, row):
        outcome = await analyze_row(
            row, dataset_manager, llm_manager, args.llm_type, idx, semaphore,
            quiet=not args.verbose,
        )
        status = outcome["final_decision"] if outcome else "skipped"
        print(f"  [{idx + 1}/{len(sample)}] {row.get('tactic'):<28} -> {status}")
        return outcome

    outcomes = await asyncio.gather(
        *(run_one(idx, row) for idx, (_, row) in enumerate(sample.iterrows()))
    )
    results = [o for o in outcomes if o]

    elapsed = time.time() - started
    summary = summarize(results, config)
    summary["model"] = model_label
    summary["llm_type"] = args.llm_type
    summary["per_tactic_sampled"] = args.per_tactic
    summary["concurrency"] = args.concurrency
    summary["elapsed_seconds"] = round(elapsed, 1)

    print_summary(summary, model_label)

    out_path = args.out or f"results/baseline_{args.llm_type}.json"
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": results}, f, indent=2, ensure_ascii=False)
    print(f"Wrote {out_path}  ({elapsed:.1f}s)")


if __name__ == "__main__":
    asyncio.run(main())
