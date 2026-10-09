"""
labeler.py
Synapsis — hand-label claims as correct / partly / wrong.

Shows one claim at a time with its quote and source.
Saves labels to labels.json so you can quit and resume.

Commands while running:
  c = correct
  p = partly correct
  w = wrong
  s = skip (come back later)
  q = quit and save
"""

import json
import os

LEDGER_FILE = "claim_ledger.json"
LABELS_FILE = "labels.json"


def load_ledger():
    with open(LEDGER_FILE) as f:
        return json.load(f)


def load_labels():
    if not os.path.exists(LABELS_FILE):
        return {}
    with open(LABELS_FILE) as f:
        return json.load(f)


def save_labels(labels):
    with open(LABELS_FILE, "w") as f:
        json.dump(labels, f, indent=2)


def show_claim(c, index, total):
    print("\n" + "=" * 60)
    print(f"CLAIM {index}/{total}   [id={c['id']}]")
    print("=" * 60)
    print(f"Status   : {c['status']}")
    print(f"Subject  : {c['subject']}")
    print(f"Relation : {c['relation']}")
    print(f"Object   : {c['object']}")
    print(f"Sign     : {c.get('sign')}")
    print(f"Context  : {c.get('context')}")
    src = c.get("source", {}) or {}
    print(f"PMID     : {src.get('pmid', '?')}")
    print(f"\nQUOTE:")
    print(f"  \"{src.get('quote', '(no quote)')}\"")
    print("\nDoes the quote support the claim as written?")
    print("  c = correct   p = partly   w = wrong   s = skip   q = quit")


def main():
    ledger = load_ledger()
    claims = ledger.get("claims", [])
    labels = load_labels()

    # Only label claims that are evidence_checked or needs_review
    to_label = [c for c in claims if c["status"] in ("evidence_checked", "needs_review")]
    total = len(to_label)

    print("=" * 60)
    print(f"LABELER — {total} claims to review")
    print(f"Already labelled: {len(labels)}")
    print("=" * 60)

    for i, c in enumerate(to_label, 1):
        cid = str(c["id"])
        if cid in labels:
            continue  # already labelled, skip

        show_claim(c, i, total)

        while True:
            choice = input("\nYour label: ").strip().lower()
            if choice in ("c", "p", "w", "s"):
                if choice == "s":
                    break
                label_map = {"c": "correct", "p": "partly", "w": "wrong"}
                labels[cid] = {
                    "label": label_map[choice],
                    "subject": c["subject"],
                    "relation": c["relation"],
                    "object": c["object"],
                    "status": c["status"],
                    "quote": (c.get("source") or {}).get("quote", ""),
                }
                save_labels(labels)
                break
            elif choice == "q":
                save_labels(labels)
                print(f"\nSaved {len(labels)} labels to {LABELS_FILE}")
                return
            else:
                print("  Enter c, p, w, s, or q.")

    save_labels(labels)
    print(f"\nAll done. {len(labels)} labels saved to {LABELS_FILE}.")


if __name__ == "__main__":
    main()
