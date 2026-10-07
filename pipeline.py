"""
pipeline.py
Synapsis — the full verification pipeline.

  raw text + PMID
        ↓
  extractor (LLM) → raw facts with quotes
        ↓
  claim_schema   → structured claim record
        ↓
  ontology       → normalized entity ids + type checks
        ↓
  quote_verifier → quote must exist in source text
        ↓
  claim_ledger   → store ONLY verified claims

Nothing enters the ledger as a fact unless its quote is found in the source.
"""

from datetime import datetime, timezone

from extractor import extract_facts
from claim_schema import make_claim, CLOSED_RELATIONS
from ontology import normalize_entity, object_type_of, is_valid_link
from quote_verifier import verify_quote
from claim_ledger import add_claim, load_ledger


def _run_meta():
    return {
        "model": "openai/gpt-oss-120b",
        "pipeline_version": "0.1",
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def process_abstract(abstract, pmid, verbose=True):
    if verbose:
        print("=" * 60)
        print(f"PIPELINE  |  PMID {pmid}")
        print("=" * 60)

    if verbose:
        print("\n[1] Extracting facts with Groq LLM...")
    raw_facts = extract_facts(abstract)
    if verbose:
        print(f"    -> {len(raw_facts)} raw facts returned")

    claims_added = []
    rejected = []

    for i, fact in enumerate(raw_facts, 1):
        if verbose:
            print(f"\n[2.{i}] {fact.get('subject')} --{fact.get('relation')}--> {fact.get('object')}")

        # Validate relation
        if fact.get("relation") not in CLOSED_RELATIONS:
            rejected.append({**fact, "reason": "relation not in closed list"})
            if verbose:
                print(f"      REJECTED - relation '{fact.get('relation')}' not allowed")
            continue

        # Normalize entities
        subj = normalize_entity(fact.get("subject", ""))
        obj  = normalize_entity(fact.get("object", ""))
        subj_type = object_type_of(subj)
        obj_type  = object_type_of(obj)
        if verbose:
            print(f"      normalized: {subj} ({subj_type}) -> {obj} ({obj_type})")

        # Type-check the link (only if both types are known)
        if subj_type and obj_type:
            if not is_valid_link(fact["relation"], subj_type, obj_type):
                reason = f"link type invalid: {subj_type} --{fact['relation']}--> {obj_type}"
                rejected.append({**fact, "reason": reason})
                if verbose:
                    print(f"      REJECTED - {reason}")
                continue

        # Build the claim record
        claim = make_claim(
            subject=subj,
            relation=fact["relation"],
            object_=obj,
            context=fact.get("context", {}),
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

        # Verify the quote
        result = verify_quote(claim["source"]["quote"], abstract)
        if not result["verified"]:
            rejected.append({**fact, "reason": f"quote failed: {result['reason']}"})
            if verbose:
                print(f"      REJECTED - quote check failed: {result['reason']}")
            continue

        # Passed — promote to quote_verified and store
        claim["status"] = "quote_verified"
        stored = add_claim(claim)
        claims_added.append(stored)
        if verbose:
            print(f"      STORED (id={stored['id']}, status=quote_verified)")

    summary = {
        "pmid": pmid,
        "extracted": len(raw_facts),
        "verified": len(claims_added),
        "rejected": len(rejected),
        "claims": claims_added,
        "rejected_facts": rejected,
    }

    if verbose:
        print("\n" + "=" * 60)
        print(f"SUMMARY - extracted: {summary['extracted']}, "
              f"verified: {summary['verified']}, rejected: {summary['rejected']}")
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
        print(f"  #{c['id']}: {c['subject']} --{c['relation']}--> {c['object']}  [{c['status']}]")
