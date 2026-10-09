"""
ontology.py
Synapsis — Layer 1: the ontology.
Seed list for the first pack (breast cancer).
Falls back to entity_resolver for entities outside the seed list.
"""

OBJECT_TYPES = {
    "GENE": "A gene",
    "PROTEIN": "A protein",
    "PATHWAY": "A biological pathway",
    "DRUG": "A therapeutic compound",
    "CELL_LINE": "A lab cell line",
    "DISEASE": "A disease",
    "TISSUE": "A tissue context",
    "STUDY": "A publication, trial, or dataset",
    "BIOMARKER": "A measurable indicator",
    "COMPOUND": "A chemical compound",
    "ORGANISM": "An organism",
}

LINK_TYPES = {
    "ACTIVATES":                ("GENE", "PROTEIN"),
    "INHIBITS":                 ("GENE", "PROTEIN"),
    "INCREASES_EXPRESSION":     ("GENE", "GENE"),
    "DECREASES_EXPRESSION":     ("GENE", "GENE"),
    "BINDS":                    ("DRUG", "PROTEIN"),
    "MODIFIES":                 ("PROTEIN", "PROTEIN"),
    "PART_OF_PATHWAY":          ("PROTEIN", "PATHWAY"),
    "MUTATED_IN":               ("GENE", "DISEASE"),
    "INCREASES_RISK_OF":        ("GENE", "DISEASE"),
    "DECREASES_RISK_OF":        ("GENE", "DISEASE"),
    "BIOMARKER_OF":             ("BIOMARKER", "DISEASE"),
    "REQUIRED_FOR":             ("PROTEIN", "PATHWAY"),
    "TARGETS":                  ("DRUG", "PROTEIN"),
    "ASSOCIATED_WITH":          (None, None),
}

SEED_OBJECTS = [
    ("BRCA1", "GENE"), ("BRCA2", "GENE"), ("TP53", "GENE"),
    ("ERBB2", "GENE"), ("HER2", "PROTEIN"),
    ("DNA_Repair", "PATHWAY"), ("HR_Repair", "PATHWAY"),
    ("Breast_Cancer", "DISEASE"),
    ("Trastuzumab", "DRUG"),
    ("SKBR3", "CELL_LINE"), ("MDA_MB_231", "CELL_LINE"),
    ("HER2_Expression", "BIOMARKER"),
]

ALIASES = {
    "HER2": "ERBB2", "HER-2": "ERBB2", "HER-2/neu": "ERBB2",
    "BRCA-1": "BRCA1", "BRCA-2": "BRCA2",
    "p53": "TP53", "P53": "TP53",
    "homologous_recombination_repair": "HR_Repair",
    "HR_repair": "HR_Repair",
    "DNA_repair": "DNA_Repair",
    "breast_cancer": "Breast_Cancer",
    "Herceptin": "Trastuzumab",
}

STATE_WORDS = {
    "mutation": "mutated", "mutations": "mutated", "mutated": "mutated",
    "mutant": "mutated", "overexpression": "overexpressed",
    "overexpressed": "overexpressed", "loss": "loss_of_function",
    "deletion": "deleted", "amplification": "amplified",
    "phosphorylation": "phosphorylated",
}

GENERIC_WORDS = {
    "protein", "gene", "mechanism", "mechanisms",
    "pathway", "pathways", "signaling", "signalling",
}

PROPERTY_WORDS = {
    "aggressive", "progression", "development", "early", "late",
    "advanced", "metastatic", "invasive",
}


def _key(text):
    return " ".join(text.lower().replace("_", " ").split())


def _lookup(candidate):
    """Check ALIASES and SEED_OBJECTS. Return canonical id or None."""
    k = _key(candidate)
    for alias, canonical in ALIASES.items():
        if _key(alias) == k:
            return canonical
    for obj_name, _ in SEED_OBJECTS:
        if _key(obj_name) == k:
            return obj_name
    return None


def resolve_name(name, use_external=True):
    """
    Split a raw name into entity + state/property qualifiers.

    Order:
      1. Whole-name lookup in seed list
      2. Split into core + qualifiers, lookup core in seed
      3. Fall back to entity_resolver (external databases)

    Returns dict with: input, entity_id, status, state, property, source, reason
    """
    clean = (name or "").replace("_", " ").strip()
    out = {"input": name, "entity_id": None, "status": "unresolved",
           "state": None, "property": None, "source": None, "reason": None}

    if not clean:
        out["reason"] = "empty_name"
        return out

    # 1) Whole-name seed lookup
    hit = _lookup(clean)
    if hit:
        out["entity_id"] = hit
        out["status"] = "resolved"
        out["source"] = "seed"
        return out

    # 2) Split into core + state/property words
    core, props = [], []
    for tok in clean.split():
        low = tok.lower()
        if low in STATE_WORDS:
            out["state"] = STATE_WORDS[low]
        elif low in GENERIC_WORDS:
            continue
        elif low in PROPERTY_WORDS:
            props.append(low)
        else:
            core.append(tok)

    if props:
        out["property"] = " ".join(props)

    core_name = " ".join(core).strip()

    # 3) Seed lookup on core
    hit = _lookup(core_name)
    if hit:
        out["entity_id"] = hit
        out["status"] = "resolved"
        out["source"] = "seed"
        return out

    # 4) External fallback
    if use_external and core_name:
        try:
            from entity_resolver import resolve as external_resolve
            ext = external_resolve(core_name, seed_lookup=None, use_external=True)
            if ext and ext.get("status") in ("resolved", "seed"):
                out["entity_id"] = ext.get("entity_id")
                out["status"] = "resolved"
                out["source"] = ext.get("source")
                return out
            out["reason"] = (ext or {}).get("reason") or "external_returned_none"
        except Exception as e:
            out["reason"] = f"resolver_error:{type(e).__name__}"

    return out


def normalize_entity(name):
    r = resolve_name(name)
    return r["entity_id"] if r["status"] == "resolved" else name


def object_type_of(name):
    """
    Return the type of an entity. Seed list first, then infer from external source.
    """
    canonical = normalize_entity(name)
    for obj_name, obj_type in SEED_OBJECTS:
        if obj_name == canonical:
            return obj_type

    # Infer from external resolver source
    if canonical and ":" in str(canonical):
        prefix = canonical.split(":")[0]
        return {
            "HGNC": "GENE",
            "UNIPROT": "PROTEIN",
            "PUBCHEM": "COMPOUND",
            "NCBI": "ORGANISM",
            "MESH": "DISEASE",
        }.get(prefix)

    return None


def is_valid_link(relation, subj_type, obj_type):
    if relation not in LINK_TYPES:
        return False
    a, b = LINK_TYPES[relation]
    if a is None and b is None:
        return True
    # Relaxed check: if we know the types, enforce; if we don't, allow it.
    if subj_type is None or obj_type is None:
        return True
    return subj_type == a and obj_type == b


if __name__ == "__main__":
    print(f"Object types: {len(OBJECT_TYPES)}")
    print(f"Link types:   {len(LINK_TYPES)}")
    print(f"Seed objects: {len(SEED_OBJECTS)}")
    print(f"Aliases:      {len(ALIASES)}\n")

    print("=== Seed lookup ===")
    for t in ["HER2", "p53", "BRCA-1", "Herceptin"]:
        r = resolve_name(t, use_external=False)
        print(f"  {t:18s} -> {r['entity_id']}  ({r['source']}, {r['status']})")

    print("\n=== External fallback ===")
    for t in ["aspirin", "E. coli", "breast cancer", "some_random_xyz"]:
        r = resolve_name(t, use_external=True)
        print(f"  {t:18s} -> {r['entity_id']}  "
              f"({r['source']}, {r['status']}, reason={r['reason']})")

    print("\n=== Type inference ===")
    for t in ["BRCA1", "aspirin", "E. coli", "breast cancer"]:
        print(f"  {t:18s} -> {object_type_of(t)}")

    print("\n=== Link validity ===")
    for rel, s, o in [("INHIBITS", "GENE", "PROTEIN"),
                      ("BINDS", "DRUG", "PROTEIN"),
                      ("INCREASES_RISK_OF", "GENE", "DISEASE"),
                      ("DECREASES_RISK_OF", "GENE", "DISEASE")]:
        mark = "OK " if is_valid_link(rel, s, o) else "no "
        print(f"  {mark} {s} --{rel}--> {o}")
