"""
pubmed.py
Synapsis — pull real abstracts from PubMed.

Uses the free NCBI E-utilities API.
No API key needed for low volume (3 requests/sec max).

Saves abstracts to a JSON file with PMIDs, titles, and abstract text.
"""

import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def _get(url):
    """Fetch a URL and return bytes."""
    req = urllib.request.Request(url, headers={"User-Agent": "Synapsis/0.4"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def search_pubmed(query, max_results=20, retmax=None):
    """
    Search PubMed with a query. Returns a list of PMIDs.
    """
    retmax = retmax or max_results
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": str(retmax),
        "retmode": "json",
        "sort": "relevance",
    }
    url = f"{EUTILS}/esearch.fcgi?" + urllib.parse.urlencode(params)
    data = json.loads(_get(url).decode("utf-8"))
    return data.get("esearchresult", {}).get("idlist", [])


def fetch_abstracts(pmids):
    """
    Given a list of PMIDs, fetch full records as XML and parse them.
    Returns a list of dicts:
        {"pmid": ..., "title": ..., "abstract": ..., "journal": ..., "year": ...}
    """
    if not pmids:
        return []
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
    }
    url = f"{EUTILS}/efetch.fcgi?" + urllib.parse.urlencode(params)
    xml_data = _get(url)

    root = ET.fromstring(xml_data)
    results = []

    for article in root.findall(".//PubmedArticle"):
        pmid_el = article.find(".//PMID")
        pmid = pmid_el.text if pmid_el is not None else ""

        title_el = article.find(".//ArticleTitle")
        title = "".join(title_el.itertext()).strip() if title_el is not None else ""

        # Abstract may be split into multiple <AbstractText> sections
        abstract_parts = []
        for ab in article.findall(".//Abstract/AbstractText"):
            label = ab.get("Label")
            text = "".join(ab.itertext()).strip()
            if label:
                abstract_parts.append(f"{label}: {text}")
            else:
                abstract_parts.append(text)
        abstract = " ".join(abstract_parts).strip()

        journal_el = article.find(".//Journal/Title")
        journal = journal_el.text if journal_el is not None else ""

        year_el = article.find(".//JournalIssue/PubDate/Year")
        if year_el is None:
            year_el = article.find(".//JournalIssue/PubDate/MedlineDate")
        year = year_el.text if year_el is not None else ""

        if abstract:
            results.append({
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "journal": journal,
                "year": year,
            })

    return results


def save_abstracts(abstracts, filename="abstracts.json"):
    with open(filename, "w") as f:
        json.dump(abstracts, f, indent=2)
    print(f"Saved {len(abstracts)} abstracts to {filename}")


def load_abstracts(filename="abstracts.json"):
    with open(filename, "r") as f:
        return json.load(f)


if __name__ == "__main__":
    QUERY = '("BRCA1" OR "BRCA2" OR "TP53" OR "HER2" OR "ERBB2") AND "breast cancer"'

    print("Searching PubMed...")
    print(f"Query: {QUERY}\n")

    pmids = search_pubmed(QUERY, max_results=20)
    print(f"Found {len(pmids)} PMIDs: {pmids[:5]}...\n")

    print("Fetching abstracts...")
    time.sleep(0.4)  # be polite to NCBI
    abstracts = fetch_abstracts(pmids)
    print(f"Got {len(abstracts)} abstracts with text\n")

    save_abstracts(abstracts, "abstracts.json")

    print("=" * 60)
    print("SAMPLE")
    print("=" * 60)
    if abstracts:
        a = abstracts[0]
        print(f"PMID: {a['pmid']}")
        print(f"Title: {a['title'][:100]}...")
        print(f"Journal: {a['journal']} ({a['year']})")
        print(f"Abstract: {a['abstract'][:300]}...")
    else:
        print("No abstracts retrieved.")
