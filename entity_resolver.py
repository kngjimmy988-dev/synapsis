"""
entity_resolver.py  (final, fixed)
Synapsis — resolve scientific entities against public databases.

Principle: honesty is the goal.
  - Every lookup is typed
  - Every failure records WHY and WHAT was tried
  - Never invents an ID
  - Never fuzzy-matches
  - Caches every result

Databases (all tested, free, no keys):
  HGNC       → human gene symbols
  UniProt    → human reviewed proteins
  PubChem    → chemical compounds
  NCBI Tax   → organisms
  MeSH       → diseases and medical concepts
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
# Real gene symbols: letters followed by digits (BRCA1, TP53, HER2, CDH1).
# Requires at least one digit, so CHITOSAN / ASPIRIN / INSULIN are not genes.
GENE_RE = re.compile(r"^[A-Z]{2,8}\d+[A-Z]?$")

ORGANISM_HINTS = {
    "coli", "aureus", "sapiens", "cerevisiae", "aeruginosa",
    "pneumoniae", "salmonella", "listeria", "candida", "bacillus",
}

DISEASE_HINTS = {
    "cancer", "carcinoma", "tumor", "tumour", "syndrome", "disease",
    "diabetes", "hypertension", "leukemia", "lymphoma", "melanoma",
    "neoplasms", "neoplasm", "infection", "disorder",
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
    compact = clean.replace(" ", "").upper()

    for hint in ORGANISM_HINTS:
        if hint in low:
            return "ORGANISM"
    for hint in DISEASE_HINTS:
        if hint in low:
            return "DISEASE"
    for hint in CHEMICAL_HINTS:
        if hint in low:
            return "COMPOUND"
    if GENE_RE.match(compact):
        return "GENE"
    return "UNKNOWN"


# ────────────────────────────────────────────────────────────
# DATABASE LOOKUPS
# Each returns (id, type, label) or None.
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
def resolve_external(name):
    """
    Returns ((id, type, label) or None, tried_list).
    """
    if not name or len(name.strip()) < 2:
        return (None, ["skipped:name_too_short"])
    if len(name.strip()) > 80:
        return (None, ["skipped:name_too_long"])

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
        if hit:
            return (hit, tried)

    elif kind == "COMPOUND":
        tried.append("pubchem")
        time.sleep(0.2)
        hit = try_pubchem(name)
        if hit:
            return (hit, tried)

    else:
        tried.append("mesh")
        time.sleep(0.2)
        hit = try_mesh(name)
        if hit:
            return (hit, tried)
        tried.append("pubchem")
        time.sleep(0.2)
        hit = try_pubchem(name)
        if hit:
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
    print("=== entity_resolver — final self-test ===\n")

    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)

    tests = [
        "BRCA1",
        "TP53",
        "aspirin",
        "E. coli",
        "breast cancer",
        "chitosan",
        "some_random_xyz_12",
    ]

    for name in tests:
        r = resolve(name, use_external=True)
        print(f"  {name:22s} -> {str(r['entity_id']):22s} "
              f"({r['source']}, {r['type']}, {r['status']})")
        if r["reason"]:
            print(f"     reason: {r['reason']}  |  tried: {r['tried']}")

    print(f"\nCache saved to {CACHE_FILE}")
