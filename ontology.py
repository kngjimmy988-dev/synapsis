"""
ontology.py
Synapsis — Layer 1: the ontology (shared knowledge map).
First pack: biomedicine (HER2 / BRCA breast cancer).
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
    "BIOMARKER_OF":             ("BIOMARKER", "DISEASE"),
    "REQUIRED_FOR":             ("PROTEIN", "PATHWAY"),
    "TARGETS":                  ("DRUG", "PROTEIN"),
    "ASSOCIATED_WITH":          (None, None),
}

SEED_OBJECTS = [
    ("BRCA1", "GENE"), ("BRCA2", "GENE"), ("TP53", "GENE"),
    ("ERBB2", "GENE"),
    ("HER2", "PROTEIN"),
    ("DNA_Repair", "PATHWAY"),
    ("HR_Repair", "PATHWAY"),
    ("Breast_Cancer", "DISEASE"),
    ("Trastuzumab", "DRUG"),
    ("SKBR3", "CELL_LINE"),
    ("MDA_MB_231", "CELL_LINE"),
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


def normalize_entity(name):
    return ALIASES.get(name, name)


def object_type_of(name):
    canonical = normalize_entity(name)
    for obj_name, obj_type in SEED_OBJECTS:
        if obj_name == canonical:
            return obj_type
    return None


def is_valid_link(relation, subj_type, obj_type):
    if relation not in LINK_TYPES:
        return False
    a, b = LINK_TYPES[relation]
    if a is None and b is None:
        return True
    return subj_type == a and obj_type == b


if __name__ == "__main__":
    print(f"Object types: {len(OBJECT_TYPES)}")
    print(f"Link types:   {len(LINK_TYPES)}")
    print(f"Seed objects: {len(SEED_OBJECTS)}")
    print(f"Aliases:      {len(ALIASES)}\n")
    for t in ["HER2", "HER-2/neu", "p53", "Herceptin", "BRCA-1"]:
        print(f"  {t:15s} -> {normalize_entity(t)}")
    print()
    for rel, s, o in [("INHIBITS", "GENE", "PROTEIN"),
                       ("BINDS", "DRUG", "PROTEIN"),
                       ("BINDS", "GENE", "PROTEIN"),
                       ("INCREASES_RISK_OF", "GENE", "DISEASE")]:
        mark = "OK " if is_valid_link(rel, s, o) else "no "
        print(f"  {mark} {s} --{rel}--> {o}")
