"""
quote_verifier.py
Synapsis — deterministic quote check. No LLM. Pure string matching.
"""

import re
import unicodedata


def normalize(text):
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def verify_quote(quote, source_text, min_length=20):
    if not quote or not source_text:
        return {"verified": False, "reason": "missing quote or source", "method": "none"}

    q = normalize(quote)
    s = normalize(source_text)

    if len(q) < min_length:
        return {"verified": False,
                "reason": f"quote too short ({len(q)} chars, min {min_length})",
                "method": "length"}

    if q in s:
        return {"verified": True, "reason": "exact match after normalization", "method": "exact"}

    q_words = q.split()
    if len(q_words) >= 5:
        pattern = r"\s+".join(re.escape(w) for w in q_words)
        if re.search(pattern, s):
            return {"verified": True, "reason": "word-sequence match", "method": "word_sequence"}
        missing = [w for w in q_words if w not in s]
        if len(missing) <= max(1, len(q_words) // 10):
            return {"verified": True,
                    "reason": f"partial match ({len(missing)} of {len(q_words)} words missing)",
                    "method": "partial"}

    return {"verified": False, "reason": "quote not found in source", "method": "none"}


def apply_verification(claim, source_text):
    if claim["status"] != "extracted":
        return claim, {"verified": False,
                       "reason": f"claim already at status '{claim['status']}'",
                       "method": "skip"}
    quote = claim.get("source", {}).get("quote", "")
    result = verify_quote(quote, source_text)
    if result["verified"]:
        claim = dict(claim)
        claim["status"] = "quote_verified"
    return claim, result


if __name__ == "__main__":
    source = """
    BRCA1 mutations are known to impair DNA repair mechanisms in cells.
    Recent studies show that impaired DNA repair leads to accumulation of
    mutations in the TP53 gene.
    """
    print("Good :", verify_quote("BRCA1 mutations are known to impair DNA repair mechanisms in cells.", source))
    print("Bad  :", verify_quote("BRCA1 causes cancer in every patient immediately.", source))
    print("Fake :", verify_quote("The moon is made of cheese and DNA repairs itself.", source))
