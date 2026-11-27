import json
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "results/baseline_commandcode_5pt.json"
with open(path, encoding="utf-8") as f:
    data = json.load(f)

s = data["summary"]
for key in [
    "model",
    "rows",
    "turns_analyzed",
    "turn_errors",
    "warn_threshold",
    "block_threshold",
    "mean_final_progressive_risk",
    "mean_max_progressive_risk",
    "detection_rate_block_or_warn",
    "block_rate",
    "escalation_rate",
    "elapsed_seconds",
]:
    print(f"{key:34} {s.get(key)}")
print(f"{'final_decision_counts':34} {s.get('final_decision_counts')}")
print()
header = f"{'tactic':<28}{'rows':>5}{'block':>7}{'warn':>6}{'allow':>7}{'blk%':>7}{'mean':>8}"
print(header)
print("-" * len(header))
for tactic, v in s["per_tactic"].items():
    print(
        f"{tactic:<28}{v['rows']:>5}{v['block']:>7}{v['warn']:>6}"
        f"{v['allow']:>7}{v['block_rate']:>7}{v['mean_progressive_risk']:>8}"
    )
