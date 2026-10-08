"""
evidence_checker.py
Synapsis — first version of the evidence_checked stage.

A rule layer that examines whether a quote actually supports a claim.
It can FAIL a claim or send it to REVIEW. It can never PROVE a claim.

Rules check:
  - direction mismatch (claim says inhibits, quote says increases)
  - relation stronger than the quote's wording
  - qualifier in quote missing from claim context
  - negation words in the quote
  - hedged language in the quote
"""

import re


# ---- word lists ------------------------------------------------------

DOWN_REL = {"INHIBITS", "DECREASES_EXPRESSION"}
UP_REL = {"ACTIVATES", "INCREASES_EXPRESSION", "INCREASES_RISK_OF"}

DOWN_WORDS = [
    "impair", "impairs", "impaired", "inhibit", "inhibits", "inhibited",
    "decrease", "decreases", "decreased", "reduce", "reduces", "reduced",
    "suppress", "suppresses", "suppressed", "block", "blocks", "blocked",
    "loss of", "downregulate", "downregulates", "lower", "abolish",
]
UP_WORDS = [
    "activate", "activates", "activated", "increase", "increases", "increased",
    "promote", "promotes", "promoted", "enhance", "enhances", "enhanced",
    "upregulate", "upregulates", "drive", "drives", "elevate", "raise",
    "cause", "causes", "caused",
]
ASSOC_WORDS = [
    "linked to", "associated with", "correlated with", "correlation",
    "related to", "connected to",
]
NEG_WORDS = [
    "not", "no", "fails to", "failed to", "without", "absence of",
    "cannot", "unable to", "does not", "do not",
]
HEDGE_WORDS = [
    "may", "might", "could", "suggest", "suggests", "suggested",
    "potentially", "possibly", "appears to", "seems",
]

STATE_IN_QUOTE = {
    "mutation": "mutated", "mutations": "mutated", "mutated": "mutated",
    "mutant": "mutated", "overexpression": "overexpressed",
    "overexpressed": "overexpressed", "deletion": "deleted",
}


# ---- helpers ---------------------------------------------------------

def _has(text, phrase):
    return re.search(r"\b" + re.escape(phrase) + r"\b", text) is not None


def _any(text, words):
    return any(_has(text, w) for w in words)


# ---- the check -------------------------------------------------------

def meaning_check(relation, context, quote):
    """
    Returns {"result": "pass_rules" | "review" | "fail",
             "flags": [list of flag names]}
    """
    q = (quote or "").lower()
    rel = (relation or "").upper()
    ctx = context or {}
    flags = []

    # -- direction ---------------------------------------------------
    has_down = _any(q, DOWN_WORDS)
    has_up = _any(q, UP_WORDS)

    if rel in DOWN_REL and has_up and not has_down:
        flags.append("direction_mismatch")
    if rel in UP_REL and has_down and not has_up:
        flags.append("direction_mismatch")

    # -- relation stronger than wording ------------------------------
    if rel != "ASSOCIATED_WITH" and _any(q, ASSOC_WORDS) and not (has_up or has_down):
        flags.append("relation_stronger_than_quote")

    # -- qualifier in quote, missing from claim context --------------
    q_states = {v for k, v in STATE_IN_QUOTE.items() if _has(q, k)}
    claim_state = ctx.get("state")
    if q_states and not claim_state:
        flags.append("qualifier_missing_in_claim")
    if claim_state and q_states and claim_state not in q_states:
        flags.append("context_not_in_quote")
    if claim_state and not q_states:
        flags.append("context_not_in_quote")

    # -- negation ----------------------------------------------------
    if _any(q, NEG_WORDS):
        flags.append("negation_in_quote")

    # -- hedging -----------------------------------------------------
    if rel != "ASSOCIATED_WITH" and _any(q, HEDGE_WORDS):
        flags.append("hedged_language")

    # -- verdict -----------------------------------------------------
    if any(f in ("direction_mismatch", "qualifier_missing_in_claim") for f in flags):
        return {"result": "fail", "flags": flags}
    if flags:
        return {"result": "review", "flags": flags}
    return {"result": "pass_rules", "flags": []}


# ---- self-test -------------------------------------------------------

if __name__ == "__main__":
    tests = [
        ("INHIBITS", {"state": "mutated"},
         "BRCA1 mutations are known to impair DNA repair mechanisms in cells.",
         "pass_rules"),
        ("INCREASES_RISK_OF", {"state": "mutated"},
         "TP53 mutations have been strongly linked to the development of breast cancer.",
         "review"),
        ("ASSOCIATED_WITH", {"state": "overexpressed"},
         "Additionally, overexpression of the HER2 protein is associated with aggressive breast cancer progression.",
         "pass_rules"),
        ("INHIBITS", {},
         "BRCA1 mutations are known to impair DNA repair mechanisms in cells.",
         "fail"),
        ("INHIBITS", {"state": "mutated"},
         "BRCA1 mutations increase DNA repair in cells.",
         "fail"),
        ("INHIBITS", {"state": "mutated"},
         "BRCA1 mutations do not impair homologous recombination in this cell line.",
         "review"),
    ]

    print("=== evidence_checker self-test ===")
    all_pass = True
    for i, (rel, ctx, quote, expected) in enumerate(tests, 1):
        r = meaning_check(rel, ctx, quote)
        ok = r["result"] == expected
        all_pass = all_pass and ok
        mark = "OK " if ok else "FAIL"
        print(f"  {mark} [{i}] expected={expected:10s} got={r['result']:10s}  flags={r['flags']}")

    print("\n" + ("ALL PASS" if all_pass else "SOME FAILED"))
