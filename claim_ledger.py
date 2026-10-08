"""
claim_ledger.py
Synapsis — the claim ledger. JSON storage. Full history + dedup.
"""

import json
import os
import hashlib
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


def claim_key(subject, relation, obj, context, source_id):
    """
    Deterministic fingerprint. Same fact from same source = same key.
    Different wording of the same entity -> same key.
    """
    from ontology import resolve_name

    def _id(name):
        r = resolve_name(name)
        return r["entity_id"] if r["status"] == "resolved" else name

    payload = {
        "s": _id(subject),
        "r": (relation or "").upper(),
        "o": _id(obj),
        "ctx": {k: context[k] for k in sorted(context or {})},
        "src": source_id or "",
    }
    raw = repr(payload).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:12]


def _ctx_with_state(claim):
    """Return claim context with state folded in from subject/object if needed."""
    from ontology import resolve_name
    ctx = dict(claim.get("context", {}) or {})
    for raw in [claim.get("subject", ""), claim.get("object", "")]:
        r = resolve_name(raw)
        if r["state"] and "state" not in ctx:
            ctx["state"] = r["state"]
    return ctx


def add_claim(claim_dict):
    """
    Add a claim. If the same claim already exists, log the new attempt
    as another run on the existing claim.
    Returns {"claim": <claim>, "action": "created" | "duplicate"}.
    """
    ledger = load_ledger()
    claim_dict = dict(claim_dict)

    ctx = _ctx_with_state(claim_dict)
    pmid = (claim_dict.get("source") or {}).get("pmid", "")
    key = claim_key(
        claim_dict.get("subject", ""),
        claim_dict.get("relation", ""),
        claim_dict.get("object", ""),
        ctx,
        pmid,
    )

    # Look for an existing claim with the same fingerprint
    for existing in ledger["claims"]:
        e_ctx = _ctx_with_state(existing)
        e_pmid = (existing.get("source") or {}).get("pmid", "")
        e_key = claim_key(
            existing.get("subject", ""),
            existing.get("relation", ""),
            existing.get("object", ""),
            e_ctx,
            e_pmid,
        )
        if e_key == key:
            existing.setdefault("runs", []).append({
                "at": _now(),
                "run": claim_dict.get("run", {}),
                "quote": (claim_dict.get("source") or {}).get("quote", ""),
            })
            save_ledger(ledger)
            return {"claim": existing, "action": "duplicate"}

    # New claim
    claim_dict["id"] = ledger["next_id"]
    ledger["next_id"] += 1
    claim_dict["history"] = [
        {"status": claim_dict["status"], "at": _now(), "note": "created"}
    ]
    claim_dict["runs"] = [{
        "at": _now(),
        "run": claim_dict.get("run", {}),
        "quote": (claim_dict.get("source") or {}).get("quote", ""),
    }]
    ledger["claims"].append(claim_dict)
    save_ledger(ledger)
    return {"claim": claim_dict, "action": "created"}


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

    # First claim
    c1 = make_claim(
        subject="BRCA1", relation="INHIBITS", object_="DNA_Repair",
        context={"state": "mutated"},
        source={"pmid": "TEST0001", "quote": "BRCA1 mutations impair DNA repair.",
                "section": "Abstract"},
    )
    r1 = add_claim(c1)
    print(f"Claim 1: id={r1['claim']['id']}, action={r1['action']}")

    # Same fact, different wording -> should be a duplicate
    c2 = make_claim(
        subject="BRCA1 mutations", relation="INHIBITS", object_="DNA_repair_mechanisms",
        context={"state": "mutated"},
        source={"pmid": "TEST0001", "quote": "BRCA1 mutations impair DNA repair.",
                "section": "Abstract"},
    )
    r2 = add_claim(c2)
    print(f"Claim 2: id={r2['claim']['id']}, action={r2['action']}")

    # Same fact, different source -> should be a NEW claim
    c3 = make_claim(
        subject="BRCA1", relation="INHIBITS", object_="DNA_Repair",
        context={"state": "mutated"},
        source={"pmid": "TEST0002", "quote": "BRCA1 mutations impair DNA repair.",
                "section": "Abstract"},
    )
    r3 = add_claim(c3)
    print(f"Claim 3: id={r3['claim']['id']}, action={r3['action']}")

    # Check final state
    ledger = load_ledger()
    print(f"\nTotal claims in ledger: {len(ledger['claims'])}")
    for c in ledger["claims"]:
        print(f"  #{c['id']} runs={len(c['runs'])}  {c['subject']} --{c['relation']}--> {c['object']}")

    print("\nExpected:")
    print("  Claim 1: created")
    print("  Claim 2: duplicate (same fact, same source, different wording)")
    print("  Claim 3: created (same fact, DIFFERENT source)")
    print("  Total: 2 claims, claim 1 has 2 runs")
