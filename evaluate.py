"""
evaluate.py
Synapsis — compute precision from hand-labeled claims.

Reads:
  labels.json      — your labels: {claim_id: {label, ...}}
  claim_ledger.json — all claims the pipeline stored

Outputs:
  Precision on evidence_checked claims
  Precision on needs_review claims
  Error breakdown
"""

import json


def load_json(path):
    with open(path) as f:
        return json.load(f)


def main():
    labels = load_json("labels.json")
    ledger = load_json("claim_ledger.json")
    claims = {str(c["id"]): c for c in ledger["claims"]}

    print("=" * 60)
    print("SYNAPSIS — PRECISION REPORT")
    print("=" * 60)

    # Group by original pipeline status
    buckets = {
        "evidence_checked": {"correct": 0, "partly": 0, "wrong": 0, "total": 0},
        "needs_review":     {"correct": 0, "partly": 0, "wrong": 0, "total": 0},
    }

    for cid, lab in labels.items():
        if cid not in claims:
            continue
        status = claims[cid]["status"]
        if status not in buckets:
            buckets[status] = {"correct": 0, "partly": 0, "wrong": 0, "total": 0}
        buckets[status][lab["label"]] += 1
        buckets[status]["total"] += 1

    print("\nBREAKDOWN BY PIPELINE STATUS")
    print("-" * 60)
    for status, b in buckets.items():
        if b["total"] == 0:
            continue
        print(f"\n  Status: {status}  (n={b['total']})")
        print(f"    correct : {b['correct']}  ({100*b['correct']/b['total']:.0f}%)")
        print(f"    partly  : {b['partly']}   ({100*b['partly']/b['total']:.0f}%)")
        print(f"    wrong   : {b['wrong']}    ({100*b['wrong']/b['total']:.0f}%)")

    # Headline numbers
    ec = buckets.get("evidence_checked", {"total": 0, "correct": 0, "wrong": 0})
    nr = buckets.get("needs_review",     {"total": 0, "correct": 0, "wrong": 0})

    print("\n" + "=" * 60)
    print("HEADLINE NUMBERS")
    print("=" * 60)

    if ec["total"] > 0:
        precision_ec = 100 * ec["correct"] / ec["total"]
        precision_ec_strict = 100 * (ec["correct"] + ec["partly"]) / ec["total"]
        print(f"\nPrecision on `evidence_checked` claims (n={ec['total']}):")
        print(f"  Strict  (only 'correct' counts):     {precision_ec:.0f}%")
        print(f"  Lenient ('correct' + 'partly'):      {precision_ec_strict:.0f}%")

    if nr["total"] > 0:
        false_flag = 100 * nr["correct"] / nr["total"]
        print(f"\nFlagging on `needs_review` claims (n={nr['total']}):")
        print(f"  Actually correct (false alarms):     {false_flag:.0f}%")

    # Total across both
    total_n = ec["total"] + nr["total"]
    total_correct = ec["correct"] + nr["correct"]
    total_partly  = ec["partly"] + nr["partly"]
    total_wrong   = ec["wrong"] + nr["wrong"]

    print("\n" + "=" * 60)
    print(f"OVERALL (n={total_n})")
    print("=" * 60)
    print(f"  correct : {total_correct}  ({100*total_correct/total_n:.0f}%)")
    print(f"  partly  : {total_partly}   ({100*total_partly/total_n:.0f}%)")
    print(f"  wrong   : {total_wrong}    ({100*total_wrong/total_n:.0f}%)")
    print("=" * 60)


if __name__ == "__main__":
    main()
