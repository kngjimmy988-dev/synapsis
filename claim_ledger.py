"""
claim_ledger.py
Synapsis — the claim ledger. JSON file. Full history per claim.
"""

import json
import os
from datetime import datetime, timezone
from claim_schema import STATUS_LEVELS

LEDGER_FILE = "claim_ledger.json"


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_ledger():
    if not os.path.exists(LEDGER_FILE):
        return {"claims": [], "next_id": 1}
    with open(LEDGER_FILE, "r") as f:
        return json.load(f)


def save_ledger(ledger):
    with open(LEDGER_FILE, "w") as f:
        json.dump(ledger, f, indent=2)


def add_claim(claim_dict):
    ledger = load_ledger()
    claim_dict = dict(claim_dict)
    claim_dict["id"] = ledger["next_id"]
    ledger["next_id"] += 1
    claim_dict["history"] = [
        {"status": claim_dict["status"], "at": _now(), "note": "created"}
    ]
    ledger["claims"].append(claim_dict)
    save_ledger(ledger)
    return claim_dict


def update_status(claim_id, new_status, note=""):
    if new_status not in STATUS_LEVELS:
        raise ValueError(f"Invalid status: {new_status}")
    ledger = load_ledger()
    for c in ledger["claims"]:
        if c["id"] == claim_id:
            c["status"] = new_status
            c["history"].append({"status": new_status, "at": _now(), "note": note})
            save_ledger(ledger)
            return c
    raise ValueError(f"Claim id {claim_id} not found")


def summary():
    ledger = load_ledger()
    counts = {s: 0 for s in STATUS_LEVELS}
    for c in ledger["claims"]:
        counts[c["status"]] = counts.get(c["status"], 0) + 1
    return counts


if __name__ == "__main__":
    if os.path.exists(LEDGER_FILE):
        os.remove(LEDGER_FILE)
    from claim_schema import make_claim
    c = make_claim(
        subject="BRCA1", relation="INHIBITS", object_="DNA_Repair",
        source={"pmid": "000000", "quote": "test", "section": "Abstract"},
    )
    c = add_claim(c)
    print(f"Added id={c['id']}, status={c['status']}")
    c = update_status(c["id"], "quote_verified", note="passed string check")
    print(f"Updated id={c['id']}, status={c['status']}")
    print("Summary:", summary())
    for h in c["history"]:
        print("  ", h)
