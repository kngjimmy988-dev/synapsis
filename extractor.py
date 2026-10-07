"""
extractor.py
Synapsis — LLM fact extraction with quotes. Uses Groq.
Returns raw facts ready to be structured by pipeline.py.
"""

import os
import json
import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-120b"

CLOSED_RELATIONS = [
    "ACTIVATES", "INHIBITS", "INCREASES_EXPRESSION", "DECREASES_EXPRESSION",
    "BINDS", "MODIFIES", "PART_OF_PATHWAY", "MUTATED_IN",
    "INCREASES_RISK_OF", "BIOMARKER_OF", "REQUIRED_FOR",
    "TARGETS", "ASSOCIATED_WITH",
]


def build_prompt(abstract):
    return f"""You are extracting biological claims from a scientific abstract.

Return ONLY a JSON object with a single key "facts" whose value is an array.
Each fact MUST have exactly these fields:
  - "subject": the entity doing the action
  - "relation": MUST be one of {CLOSED_RELATIONS}
  - "object": the entity receiving the action
  - "quote": the EXACT sentence from the abstract that supports this fact.
  - "context": a short object with any of: species, cell_type, state, setting

IMPORTANT — choose the STRONGEST relation the quote supports:
  - A increases activity of B → ACTIVATES
  - A decreases activity of B → INHIBITS
  - A increases expression of gene B → INCREASES_EXPRESSION
  - A decreases expression of gene B → DECREASES_EXPRESSION
  - A is mutated in disease B → MUTATED_IN
  - A raises risk of / is strongly linked to disease B → INCREASES_RISK_OF
  - A is a measurable indicator of B → BIOMARKER_OF
  - A is a drug and acts on protein B → TARGETS
  - A physically interacts with B → BINDS
  - A is a component of pathway B → PART_OF_PATHWAY
  - Only use ASSOCIATED_WITH when the quote says nothing stronger than correlation

Rules:
  - Only extract what is explicitly supported by a sentence in the abstract.
  - The quote must appear word-for-word in the abstract.
  - If you cannot quote a sentence, do NOT return the fact.

Abstract:
\"\"\"
{abstract}
\"\"\"

Return ONLY valid JSON. Example:
{{"facts": [
  {{"subject": "BRCA1", "relation": "INHIBITS", "object": "DNA_Repair",
    "quote": "BRCA1 mutations impair DNA repair mechanisms in cells.",
    "context": {{"state": "mutated", "species": "human"}}}}
]}}
"""


def extract_facts(abstract, api_key=None):
    api_key = api_key or os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set in environment")

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": build_prompt(abstract)}],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    r = requests.post(GROQ_URL, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()
    raw = data["choices"][0]["message"]["content"]
    parsed = json.loads(raw)
    return parsed.get("facts", [])


if __name__ == "__main__":
    sample = """
    BRCA1 mutations are known to impair DNA repair mechanisms in cells.
    Recent studies show that impaired DNA repair leads to accumulation of
    mutations in the TP53 gene. TP53 mutations have been strongly linked
    to the development of breast cancer. Additionally, overexpression of
    the HER2 protein is associated with aggressive breast cancer progression.
    """
    facts = extract_facts(sample)
    print("=== EXTRACTED FACTS ===")
    for f in facts:
        print(f"\nSubject  : {f['subject']}")
        print(f"Relation : {f['relation']}")
        print(f"Object   : {f['object']}")
        print(f"Quote    : {f['quote']}")
        print(f"Context  : {f.get('context', {})}")
