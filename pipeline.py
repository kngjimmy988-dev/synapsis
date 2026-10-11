"""
pipeline.py
Synapsis — the full verification pipeline (v0.4 — plain English).

  raw text + PMID
        ↓
  extractor        -> raw facts with quotes
        ↓
  resolve_name     -> entity IDs + qualifiers
        ↓
  quote_verifier   -> quote must exist in the source
        ↓
  evidence_checker -> meaning check (rules)
        ↓
  claim_ledger     -> dedup + store

All user-facing output uses plain English:
  Found       = the tool spotted this claim
  Verified    = the quote supports the claim
  Needs a look= the tool couldn't confirm it
  Failed      = the quote does not support it
  Repeats     = same claim from the same source, counted once
"""

from datetime import datetime, timezone

from extractor import extract_facts
from claim_schema import make_claim, CLOSED_RELATIONS
from ontology import resolve_name, object_type_of, is_valid_link
from quote_verifier import verify_quote
from evidence_checker import meaning_check
from claim_ledger import add_claim, load_ledger


def _run_meta():
    return {
        "model": "openai/gpt-oss-120b",
        "pipeline_version": "0.4",
        "temperature": 0.1,
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def process_abstract(abstract, pmid, verbose=True):
    if verbose:
        print("=" * 60)
        print(f"SYNAPSIS  |  PMID {pmid}")
        print("=" * 60)

    if verbose:
        print("\n[1] Reading the abstract...")
    raw_facts = extract_facts(abstract)
    if verbose:
        print(f"    Found {len(raw_facts)} claims.")

    created = []
    duplicates = []
    needs_review = []
    rejected = []

    for i, fact in enumerate(raw_facts, 1):
        if verbose:
            print(f"\n[{i}] {fact.get('subject')} --{fact.get('relation')}--> {fact.get('object')}")

        # --- relation must be in the closed list ---
        if fact.get("relation") not in CLOSED_RELATIONS:
            rejected.append({**fact, "reason": "relation not in closed list"})
            if verbose:
                print(f"     FAILED - '{fact.get('relation')}' is not an allowed relation")
            continue

        # --- resolve subject and object ---
        subj_r = resolve_name(fact.get("subject", ""))
        obj_r = resolve_name(fact.get("object", ""))

        subj = subj_r["entity_id"] or subj_r["input"]
        obj = obj_r["entity_id"] or obj_r["input"]

        subj_type = object_type_of(subj)
        obj_type = object_type_of(obj)

        if verbose:
            s_status = "resolved" if subj_r["status"] == "resolved" else "UNRESOLVED"
            o_status = "resolved" if obj_r["status"] == "resolved" else "UNRESOLVED"
            print(f"     entities: {subj} ({s_status})  ->  {obj} ({o_status})")

        # --- if either entity is unresolved, flag, don't store as verified ---
        if subj_r["status"] == "unresolved" or obj_r["status"] == "unresolved":
            who = subj if subj_r["status"] == "unresolved" else obj
            reason = f"entity not recognized: {who}"
            needs_review.append({**fact, "reason": reason})
            if verbose:
                print(f"     NEEDS A LOOK - {reason}")
            continue

        # --- link type check (when both types known) ---
        if subj_type and obj_type:
            if not is_valid_link(fact["relation"], subj_type, obj_type):
                reason = f"{subj_type} --{fact['relation']}--> {obj_type} is not allowed"
                rejected.append({**fact, "reason": reason})
                if verbose:
                    print(f"     FAILED - {reason}")
                continue

        # --- build context: fold state from subject/object ---
        ctx = dict(fact.get("context", {}) or {})
        if subj_r["state"] and "state" not in ctx:
            ctx["state"] = subj_r["state"]
        if obj_r["state"] and "state" not in ctx:
            ctx["state"] = obj_r["state"]

        # --- build claim ---
        claim = make_claim(
            subject=subj,
            relation=fact["relation"],
            object_=obj,
            context=ctx,
            source={
                "pmid": pmid,
                "quote": fact.get("quote", ""),
                "section": "Abstract",
            },
            evidence_type="direct",
            status="extracted",
            confidence=0.0,
            run=_run_meta(),
        )

        # --- quote verification ---
        vres = verify_quote(claim["source"]["quote"], abstract)
        if not vres["verified"]:
            rejected.append({**fact, "reason": f"quote not in source: {vres['reason']}"})
            if verbose:
                print(f"     FAILED - quote not found in source")
            continue
        claim["status"] = "quote_verified"

        # --- meaning check ---
        mres = meaning_check(claim["relation"], claim["context"], claim["source"]["quote"])
        if mres["result"] == "fail":
            rejected.append({**fact, "reason": f"meaning check: {mres['flags']}"})
            if verbose:
                print(f"     FAILED - {mres['flags']}")
            continue
        if mres["result"] == "review":
            claim["status"] = "needs_review"
            needs_review.append({**fact, "reason": f"{mres['flags']}"})
            if verbose:
                print(f"     NEEDS A LOOK - {mres['flags']}")
        else:
            claim["status"] = "evidence_checked"

        # --- store in ledger (dedup happens inside) ---
        result = add_claim(claim)
        if result["action"] == "duplicate":
            duplicates.append(result["claim"]["id"])
            if verbose:
                print(f"     REPEAT of #{result['claim']['id']}")
        else:
            created.append(result["claim"])
            if verbose:
                print(f"     VERIFIED (id={result['claim']['id']})")

    summary = {
        "pmid": pmid,
        "extracted": len(raw_facts),
        "created": len(created),
        "duplicates": len(duplicates),
        "needs_review": len(needs_review),
        "rejected": len(rejected),
        "claims": created,
    }

    if verbose:
        print("\n" + "=" * 60)
        print(f"SUMMARY — Found {summary['extracted']}, "
              f"Verified {summary['created']}, "
              f"Repeats {summary['duplicates']}, "
              f"Needs a look {summary['needs_review']}, "
              f"Failed {summary['rejected']}")
        print("=" * 60)

    return summary


if __name__ == "__main__":
    sample = """
    BRCA1 mutations are known to impair DNA repair mechanisms in cells.
    TP53 mutations have been strongly linked to the development of breast cancer.
    """

    result = process_abstract(sample, pmid="TEST0001")

    print("\n\nFINAL LEDGER:")
    ledger = load_ledger()
    print(f"  Total claims stored: {len(ledger['claims'])}")
    for c in ledger["claims"]:
        runs = len(c.get("runs", []))
        print(f"  #{c['id']}: {c['subject']} --{c['relation']}--> {c['object']}"
              f"  [{c['status']}]  (runs: {runs})")
