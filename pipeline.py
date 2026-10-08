"""
pipeline.py
Synapsis — the full verification pipeline (v0.3).

  raw text + PMID
        ↓
  extractor       -> raw facts with quotes
        ↓
  resolve_name    -> entity IDs + state/property qualifiers
        ↓
  quote_verifier  -> quote must exist in source
        ↓
  evidence_checker-> meaning check (rules)
        ↓
  claim_ledger    -> dedup + store verified claims
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
        "pipeline_version": "0.3",
        "temperature": 0.1,
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def process_abstract(abstract, pmid, verbose=True):
    if verbose:
        print("=" * 60)
        print(f"PIPELINE v0.3  |  PMID {pmid}")
        print("=" * 60)

    if verbose:
        print("\n[1] Extracting facts with Groq LLM...")
    raw_facts = extract_facts(abstract)
    if verbose:
        print(f"    -> {len(raw_facts)} raw facts returned")

    claims_added = []
    duplicates = []
    rejected = []
    needs_review = []

    for i, fact in enumerate(raw_facts, 1):
        if verbose:
            print(f"\n[2.{i}] {fact.get('subject')} --{fact.get('relation')}--> {fact.get('object')}")

        # --- relation must be in the closed list ---
        if fact.get("relation") not in CLOSED_RELATIONS:
            rejected.append({**fact, "reason": "relation not in closed list"})
            if verbose:
                print(f"      REJECTED - relation '{fact.get('relation')}' not allowed")
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
            print(f"      {subj} ({subj_type}, {s_status}) -> {obj} ({obj_type}, {o_status})")

        # --- if either entity is unresolved, flag for review, don't store ---
        if subj_r["status"] == "unresolved" or obj_r["status"] == "unresolved":
            reason = f"unresolved entity: {subj if subj_r['status']=='unresolved' else obj}"
            needs_review.append({**fact, "reason": reason})
            if verbose:
                print(f"      REVIEW - {reason}")
            continue

        # --- link type check (only when both types are known) ---
        if subj_type and obj_type:
            if not is_valid_link(fact["relation"], subj_type, obj_type):
                reason = f"link type invalid: {subj_type} --{fact['relation']}--> {obj_type}"
                rejected.append({**fact, "reason": reason})
                if verbose:
                    print(f"      REJECTED - {reason}")
                continue

        # --- build context: fold state from subject/object into it ---
        ctx = dict(fact.get("context", {}) or {})
        if subj_r["state"] and "state" not in ctx:
            ctx["state"] = subj_r["state"]
        if obj_r["state"] and "state" not in ctx:
            ctx["state"] = obj_r["state"]

        # --- build the claim record ---
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
            rejected.append({**fact, "reason": f"quote failed: {vres['reason']}"})
            if verbose:
                print(f"      REJECTED - quote check failed: {vres['reason']}")
            continue
        claim["status"] = "quote_verified"

        # --- meaning check ---
        mres = meaning_check(claim["relation"], claim["context"], claim["source"]["quote"])
        if mres["result"] == "fail":
            rejected.append({**fact, "reason": f"meaning check failed: {mres['flags']}"})
            if verbose:
                print(f"      REJECTED - meaning check: {mres['flags']}")
            continue
        if mres["result"] == "review":
            claim["status"] = "needs_review"
            needs_review.append({**fact, "reason": f"meaning check: {mres['flags']}"})
            if verbose:
                print(f"      REVIEW - meaning check: {mres['flags']}")
            # still store, but as needs_review
        else:
            claim["status"] = "evidence_checked"

        # --- store in ledger (dedup happens inside) ---
        result = add_claim(claim)
        if result["action"] == "duplicate":
            duplicates.append(result["claim"]["id"])
            if verbose:
                print(f"      DUPLICATE of claim #{result['claim']['id']} (extra run logged)")
        else:
            claims_added.append(result["claim"])
            if verbose:
                print(f"      STORED (id={result['claim']['id']}, status={result['claim']['status']})")

    summary = {
        "pmid": pmid,
        "extracted": len(raw_facts),
        "created": len(claims_added),
        "duplicates": len(duplicates),
        "needs_review": len(needs_review),
        "rejected": len(rejected),
        "claims": claims_added,
    }

    if verbose:
        print("\n" + "=" * 60)
        print(f"SUMMARY - extracted: {summary['extracted']}, "
              f"created: {summary['created']}, "
              f"duplicates: {summary['duplicates']}, "
              f"needs_review: {summary['needs_review']}, "
              f"rejected: {summary['rejected']}")
        print("=" * 60)

    return summary


if __name__ == "__main__":
    sample_abstract = """
    BRCA1 mutations are known to impair DNA repair mechanisms in cells.
    Recent studies show that impaired DNA repair leads to accumulation of
    mutations in the TP53 gene. TP53 mutations have been strongly linked
    to the development of breast cancer. Additionally, overexpression of
    the HER2 protein is associated with aggressive breast cancer progression.
    """

    result = process_abstract(sample_abstract, pmid="TEST0001")

    print("\n\nFINAL LEDGER SUMMARY:")
    ledger = load_ledger()
    print(f"  Total claims in ledger: {len(ledger['claims'])}")
    for c in ledger["claims"]:
        runs = len(c.get("runs", []))
        print(f"  #{c['id']}: {c['subject']} --{c['relation']}--> {c['object']}"
              f"  [{c['status']}]  (runs: {runs})")
