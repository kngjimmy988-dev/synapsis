"""
claim_schema.py
Synapsis Verified Claim Core — the claim record structure.
"""

CLOSED_RELATIONS = {
    "ACTIVATES":                (+1, "A increases activity of B"),
    "INHIBITS":                 (-1, "A decreases activity of B"),
    "INCREASES_EXPRESSION":     (+1, "A increases expression of gene B"),
    "DECREASES_EXPRESSION":     (-1, "A decreases expression of gene B"),
    "BINDS":                    ( 0, "Physical interaction, direction unspecified"),
    "MODIFIES":                 ( 0, "A chemically modifies B"),
    "PART_OF_PATHWAY":          ( 0, "A is a component of pathway/complex B"),
    "MUTATED_IN":               ( 0, "A is mutated in disease B"),
    "INCREASES_RISK_OF":        (+1, "A raises risk of disease B"),
    "BIOMARKER_OF":             ( 0, "A is a measurable indicator of B"),
    "REQUIRED_FOR":             (+1, "A is required for process B"),
    "TARGETS":                  ( 0, "Drug A targets protein B"),
    "ASSOCIATED_WITH":          ( 0, "Correlation only — never chained"),
}

STATUS_LEVELS = [
    "extracted",
    "quote_verified",
    "evidence_checked",
    "needs_review",
    "verified",
    "contradicted",
]


def make_claim(subject, relation, object_,
               subject_id=None, object_id=None, sign=None, context=None,
               source=None, evidence_type=None,
               status="extracted", confidence=0.0, run=None):
    if relation not in CLOSED_RELATIONS:
        raise ValueError(f"Relation '{relation}' not in closed vocabulary.")
    if status not in STATUS_LEVELS:
        raise ValueError(f"Status '{status}' invalid.")
    if sign is None:
        sign = CLOSED_RELATIONS[relation][0]

    # Coerce context and source to dicts — protects against LLM output
    # that returns a string where a dict is expected.
    if not isinstance(context, dict):
        context = {}
    if not isinstance(source, dict):
        source = {}
    if not isinstance(run, dict):
        run = {}

    return {
        "subject": subject, "subject_id": subject_id,
        "relation": relation,
        "object": object_, "object_id": object_id,
        "sign": sign,
        "context": context,
        "source": source,
        "evidence_type": evidence_type,
        "status": status,
        "confidence": confidence,
        "run": run,
    }


def is_chainable(claim):
    return claim["relation"] != "ASSOCIATED_WITH" and claim["sign"] != 0


if __name__ == "__main__":
    import json
    c = make_claim(
        subject="BRCA1 (mutated)", relation="INHIBITS",
        object_="homologous recombination repair",
        subject_id="HGNC:1100",
        context={"species": "human", "state": "mutated"},
        source={"pmid": "12345678", "quote": "mutated BRCA1 impairs HR repair",
                "section": "Abstract"},
    )
    print(json.dumps(c, indent=2))
    print("\nChainable?", is_chainable(c))
    print("Relations:", len(CLOSED_RELATIONS))

