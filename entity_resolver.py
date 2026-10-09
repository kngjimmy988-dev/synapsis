"""
entity_resolver.py  (v3 — fixed)
Synapsis — resolve scientific entities against public databases.

Principle: honesty is the goal.

Fixes since v2:
  - Genes without digits (APOE, CFTR, KRAS) now recognized as GENE.
  - 3-letter all-caps acronyms (CNN, MCI, DNA) rejected unless they're known genes.
  - For UNKNOWN type, DB label must contain the query.
"""

import json
import os
import re
import time
import urllib.parse
import urllib.request

CACHE_FILE = "entity_cache.json"


# ────────────────────────────────────────────────────────────
# CACHE
# ────────────────────────────────────────────────────────────
def _cache_key(name):
    return name.strip().lower().replace("_", " ")


def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


# ────────────────────────────────────────────────────────────
# HTTP
# ────────────────────────────────────────────────────────────
def _get(url, params=None, timeout=15):
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Synapsis/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")


# ────────────────────────────────────────────────────────────
# TYPE GUESSING
# ────────────────────────────────────────────────────────────
# Gene symbols WITH digits: BRCA1, TP53, HER2, CDH1
GENE_RE = re.compile(r"^[A-Z]{2,8}\d+[A-Z]?$")

# Genes with no digit. Kept small but covers common cases.
KNOWN_NO_DIGIT_GENES = {
    "APOE", "APOB", "APOA1", "APOA2", "CFTR", "KRAS", "NRAS", "HRAS",
    "MYC", "FOS", "JUN", "RB1", "VHL", "WT1", "NF1", "NF2", "RET",
    "MET", "ALK", "EGFR", "ERBB2", "MTOR", "PTEN", "SMAD4",
    "CDKN2A", "CDKN2B", "E2F1", "MYCN", "BCL2", "BCL6", "MCL1",
    "ACE", "AGT", "REN", "INS", "GCG", "LEP", "ADIPOQ", "PPARG",
    "TNF", "IL6", "IL1B", "IFNG", "TGFB1", "VEGFA", "HIF1A",
    "SOD1", "SOD2", "CAT", "GPX1", "NOS1", "NOS2", "NOS3",
    "ATM", "CHEK1", "CHEK2",
    "MLH1", "MSH2", "MSH6", "PMS2",
    # Note: BRCA1/BRCA2/TP53 handled by GENE_RE (they have digits)
}

ORGANISM_HINTS = {
    "coli", "aureus", "sapiens", "cerevisiae", "aeruginosa",
    "pneumoniae", "salmonella", "listeria", "candida", "bacillus",
}

DISEASE_HINTS = {
    "cancer", "carcinoma", "tumor", "tumour", "syndrome", "disease",
    "diabetes", "hypertension", "leukemia", "lymphoma", "melanoma",
    "neoplasms", "neoplasm", "infection", "disorder",
    "alzheimer", "parkinson", "arthritis", "asthma", "stroke",
}

CHEMICAL_HINTS = {
    "acid", "salt", "chloride", "oxide", "silver", "gold",
    "nanoparticle", "compound", "ion", "molecule", "peptide",
    "aspirin", "caffeine", "ibuprofen", "penicillin", "insulin",
    "chitosan", "glucose", "cholesterol", "dopamine", "serotonin",
}


def guess_type(name):
    if not name:
        return "UNKNOWN"
    clean = name.strip().replace("_", " ")
    low = clean.lower()
    compact = clean.replace(" ", "").replace("-", "").upper()

    # 1) Known no-digit gene symbols
    if compact in KNOWN_NO_DIGIT_GENES:
        return "GENE"

    # 2) Organism hints
    for hint in ORGANISM_HINTS:
        if hint in low:
            return "ORGANISM"

    # 3) Disease hints
    for hint in DISEASE_HINTS:
        if hint in low:
            return "DISEASE"

    # 4) Chemical hints
    for hint in CHEMICAL_HINTS:
        if hint in low:
            return "COMPOUND"

    # 5) Genes with digits
    if GENE_RE.match(compact):
        return "GENE"

    return "UNKNOWN"


# ────────────────────────────────────────────────────────────
# DATABASE LOOKUPS
# ────────────────────────────────────────────────────────────
def try_hgnc(name):
    try:
        url = "https://rest.genenames.org/fetch/symbol/" + urllib.parse.quote(name.upper())
        data = _get(url)
        parsed = json.loads(data)
        docs = parsed.get("response", {}).get("docs", [])
        if docs:
            hgnc_id = docs[0].get("hgnc_id", "")
            symbol = docs[0].get("symbol", name.upper())
            if hgnc_id:
                return (hgnc_id, "GENE", symbol)
    except Exception:
        pass
    return None


def try_uniprot_human(name):
    try:
        query = f'(gene_exact:{name.upper()}) AND (organism_id:9606) AND (reviewed:true)'
        data = _get(
            "https://rest.uniprot.org/uniprotkb/search",
            {"query": query, "format": "json", "size": "1"},
        )
        parsed = json.loads(data)
        results = parsed.get("results", [])
        if results:
            acc = results[0].get("primaryAccession", "")
            if acc:
                return (f"UNIPROT:{acc}", "PROTEIN", name.upper())
    except Exception:
        pass
    return None


def try_pubchem(name):
    try:
        url = (f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
               f"{urllib.parse.quote(name)}/cids/JSON")
        data = _get(url)
        parsed = json.loads(data)
        if "Fault" in parsed:
            return None
        cids = parsed.get("IdentifierList", {}).get("CID", [])
        if cids:
            return (f"PUBCHEM:{cids[0]}", "COMPOUND", name)
    except Exception:
        pass
    return None


def try_ncbi_taxonomy(name):
    try:
        data = _get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            {"db": "taxonomy", "term": name, "retmode": "json", "retmax": "1"},
        )
        parsed = json.loads(data)
        ids = parsed.get("esearchresult", {}).get("idlist", [])
        if ids:
            return (f"NCBI:{ids[0]}", "ORGANISM", name)
    except Exception:
        pass
    return None


def try_mesh(name):
    try:
        data = _get(
            "https://id.nlm.nih.gov/mesh/lookup/descriptor",
            {"label": name, "match": "contains", "limit": "1"},
        )
        parsed = json.loads(data)
        if parsed and isinstance(parsed, list):
            resource = parsed[0].get("resource", "")
            label = parsed[0].get("label", name)
            mesh_id = resource.rsplit("/", 1)[-1]
            if mesh_id:
                return (f"MESH:{mesh_id}", "DISEASE", label)
    except Exception:
        pass
    return None


# ────────────────────────────────────────────────────────────
# TYPED DISPATCH
# ────────────────────────────────────────────────────────────
def _label_contains(returned_label, query):
    """Check that the DB's returned label actually contains the query (loose)."""
    if not returned_label or not query:
        return False
    a = returned_label.lower().replace("_", " ").strip()
    b = query.lower().replace("_", " ").strip()
    return b in a or a in b


def resolve_external(name):
    if not name or len(name.strip()) < 2:
        return (None, ["skipped:name_too_short"])
    if len(name.strip()) > 80:
        return (None, ["skipped:name_too_long"])

    clean = name.strip()
    compact = clean.replace(" ", "").replace("-", "").upper()

    # Reject bare 3-letter all-caps acronyms unless they're known genes.
    if (len(compact) == 3
            and compact.isalpha()
            and compact.isupper()
            and compact not in KNOWN_NO_DIGIT_GENES):
        return (None, ["skipped:short_acronym"])

    kind = guess_type(name)
    tried = []

    if kind == "GENE":
        tried.append("hgnc")
        hit = try_hgnc(name)
        if hit:
            return (hit, tried)
        time.sleep(0.2)
        tried.append("uniprot")
        hit = try_uniprot_human(name)
        if hit:
            return (hit, tried)

    elif kind == "ORGANISM":
        tried.append("ncbi_taxonomy")
        time.sleep(0.2)
        hit = try_ncbi_taxonomy(name)
        if hit:
            return (hit, tried)

    elif kind == "DISEASE":
        tried.append("mesh")
        time.sleep(0.2)
        hit = try_mesh(name)
        if hit and _label_contains(hit[2], name):
            return (hit, tried)

    elif kind == "COMPOUND":
        tried.append("pubchem")
        time.sleep(0.2)
        hit = try_pubchem(name)
        if hit:
            return (hit, tried)

    else:
        # UNKNOWN: try MeSH, then PubChem. Require label to match query.
        tried.append("mesh")
        time.sleep(0.2)
        hit = try_mesh(name)
        if hit and _label_contains(hit[2], name):
            return (hit, tried)

        tried.append("pubchem")
        time.sleep(0.2)
        hit = try_pubchem(name)
        if hit and _label_contains(hit[2], name):
            return (hit, tried)

    return (None, tried)


# ────────────────────────────────────────────────────────────
# MAIN RESOLVE
# ────────────────────────────────────────────────────────────
def resolve(name, seed_lookup=None, use_external=True):
    if not name:
        return {"input": name, "entity_id": None, "source": None,
                "type": None, "label": None, "status": "unresolved",
                "reason": "empty_name", "tried": []}

    cache = load_cache()
    key = _cache_key(name)
    if key in cache:
        return cache[key]

    if seed_lookup:
        local = seed_lookup(name)
        if local and local.get("status") == "resolved":
            result = {
                "input": name,
                "entity_id": local["entity_id"],
                "source": "seed",
                "type": local.get("type"),
                "label": local["entity_id"],
                "status": "seed",
                "reason": None,
                "tried": ["seed"],
            }
            cache[key] = result
            save_cache(cache)
            return result

    if use_external:
        hit, tried = resolve_external(name)
        if hit:
            entity_id, entity_type, label = hit
            source = entity_id.split(":")[0]
            result = {
                "input": name,
                "entity_id": entity_id,
                "source": source,
                "type": entity_type,
                "label": label,
                "status": "resolved",
                "reason": None,
                "tried": tried,
            }
            cache[key] = result
            save_cache(cache)
            return result

        result = {
            "input": name,
            "entity_id": None,
            "source": None,
            "type": None,
            "label": None,
            "status": "unresolved",
            "reason": f"not_found_in_{'_or_'.join(tried) or 'any_db'}",
            "tried": tried,
        }
        cache[key] = result
        save_cache(cache)
        return result

    return {"input": name, "entity_id": None, "source": None,
            "type": None, "label": None, "status": "unresolved",
            "reason": "external_disabled", "tried": []}


# ────────────────────────────────────────────────────────────
# SELF-TEST
# ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== entity_resolver v3 self-test ===\n")

    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)

    tests = [
        "BRCA1",              # expect HGNC or UNIPROT
        "TP53",               # expect HGNC or UNIPROT
        "APOE",               # expect HGNC:613  (Bug 1 fix)
        "CFTR",               # expect HGNC
        "aspirin",            # expect PUBCHEM:2244
        "E. coli",            # expect NCBI:562
        "breast cancer",      # expect MESH
        "Alzheimer disease",  # expect MESH
        "CNN",                # expect unresolved (Bug 2 fix)
        "MCI",                # expect unresolved
        "chitosan",           # expect unresolved (polymer)
    ]

    for name in tests:
        r = resolve(name, use_external=True)
        print(f"  {name:22s} -> {str(r['entity_id']):22s} "
              f"({r['source']}, {r['type']}, {r['status']})")
        if r["reason"] and r["reason"] != "not_found_in_any_db":
            print(f"     reason: {r['reason']}  |  tried: {r['tried']}")

    print(f"\nCache saved to {CACHE_FILE}")
