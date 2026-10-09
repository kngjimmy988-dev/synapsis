"""
streamlit_app.py
Synapsis — public web demo.

Pre-loaded examples + a live pipeline for user pasted abstracts.
"""

import json
import os
import streamlit as st

# --- page config -----------------------------------------------------
st.set_page_config(
    page_title="Synapsis — Verified Claims",
    page_icon="🔬",
    layout="centered",
)

# --- pre-loaded examples ---------------------------------------------
# These are real PubMed abstracts with pipeline output baked in,
# so the demo works even without an API key.
EXAMPLES = [
    {
        "title": "Breast cancer — BRCA1 and DNA repair",
        "pmid": "33812473",
        "abstract": (
            "BRCA1 mutations are known to impair DNA repair mechanisms in cells. "
            "Recent studies show that impaired DNA repair leads to accumulation of "
            "mutations in the TP53 gene. TP53 mutations have been strongly linked "
            "to the development of breast cancer. Additionally, overexpression of "
            "the HER2 protein is associated with aggressive breast cancer progression."
        ),
        "claims": [
            {
                "subject": "BRCA1", "relation": "INHIBITS", "object": "DNA_Repair",
                "quote": "BRCA1 mutations are known to impair DNA repair mechanisms in cells.",
                "status": "evidence_checked", "flag": None,
            },
            {
                "subject": "TP53", "relation": "INCREASES_RISK_OF", "object": "Breast_Cancer",
                "quote": "TP53 mutations have been strongly linked to the development of breast cancer.",
                "status": "needs_review", "flag": "relation_stronger_than_quote",
            },
            {
                "subject": "ERBB2", "relation": "ASSOCIATED_WITH", "object": "Breast_Cancer",
                "quote": "overexpression of the HER2 protein is associated with aggressive breast cancer progression.",
                "status": "evidence_checked", "flag": None,
            },
        ],
    },
    {
        "title": "TP53 — germline mutations and breast cancer risk",
        "pmid": "29522266",
        "abstract": (
            "Using Exome Aggregation Consortium control data, we confirm significant "
            "associations of heterozygous germ line mutations with BC for ATM, CDH1, "
            "CHEK2, PALB2, and TP53 (OR: 7.30, 95%CI: 1.22-43.68)."
        ),
        "claims": [
            {
                "subject": "TP53", "relation": "INCREASES_RISK_OF", "object": "Breast_Cancer",
                "quote": "significant associations of heterozygous germ line mutations with BC for ... TP53 (OR: 7.30)",
                "status": "evidence_checked", "flag": None,
            },
        ],
    },
    {
        "title": "BRCA1/BRCA2 — hereditary breast cancer",
        "pmid": "32241645",
        "abstract": (
            "Breast cancers occurring in the context of a hereditary mutation of a "
            "predisposition gene represent 5 to 10% of all breast cancers, 20 to 25% "
            "of which being due to a mutation in the BRCA1 or BRCA2 genes."
        ),
        "claims": [
            {
                "subject": "BRCA1", "relation": "INCREASES_RISK_OF", "object": "Breast_Cancer",
                "quote": "...20 to 25% of which being due to a mutation in the BRCA1 or BRCA2 genes.",
                "status": "evidence_checked", "flag": None,
            },
            {
                "subject": "BRCA2", "relation": "INCREASES_RISK_OF", "object": "Breast_Cancer",
                "quote": "...20 to 25% of which being due to a mutation in the BRCA1 or BRCA2 genes.",
                "status": "evidence_checked", "flag": None,
            },
        ],
    },
]

# --- status icons ----------------------------------------------------
STATUS_ICON = {
    "evidence_checked": "✅",
    "needs_review": "⚠️",
    "quote_verified": "🔵",
    "rejected": "❌",
}

# --- header ----------------------------------------------------------
st.title("🔬 Synapsis")
st.markdown(
    "**Verify scientific claims against their sources.** "
    "Every claim links to the exact quote it came from."
)
st.divider()

# --- example selection -----------------------------------------------
st.subheader("Examples")
example_titles = [e["title"] for e in EXAMPLES]
choice = st.selectbox("Pick an abstract", example_titles, label_visibility="collapsed")
example = next(e for e in EXAMPLES if e["title"] == choice)

# --- show the abstract ----------------------------------------------
st.markdown(f"**Source: PMID {example['pmid']}**")
with st.expander("Show abstract", expanded=False):
    st.write(example["abstract"])

# --- show the claims -------------------------------------------------
st.markdown("### Extracted claims")

for c in example["claims"]:
    icon = STATUS_ICON.get(c["status"], "•")
    header = f"{icon}  `{c['subject']}` --**{c['relation']}**--> `{c['object']}`"
    st.markdown(header)
    st.caption(f"Quote: *“{c['quote']}”*")
    if c["flag"]:
        st.warning(f"Flag: `{c['flag']}`")
    else:
        st.success(f"Status: `{c['status']}`")
    st.markdown("")

st.divider()

# --- try your own ---------------------------------------------------
st.subheader("Try your own")
st.caption("Paste a scientific abstract. Live pipeline runs on it (limited to 3 per session).")

if "user_runs" not in st.session_state:
    st.session_state.user_runs = 0
if "user_results" not in st.session_state:
    st.session_state.user_results = []

user_text = st.text_area("Paste abstract here:", height=180)

if st.button("Verify claims"):
    if st.session_state.user_runs >= 3:
        st.error("Demo limit reached for this session. Refresh to try again.")
    elif len(user_text.strip()) < 50:
        st.warning("Please paste a longer abstract (at least 50 characters).")
    else:
        with st.spinner("Running pipeline..."):
            try:
                from pipeline import process_abstract
                import os as _os
                if not _os.environ.get("GROQ_API_KEY"):
                    st.error("Live pipeline is not configured on this deployment.")
                else:
                    result = process_abstract(user_text, pmid="LIVE-DEMO", verbose=False)
                    st.session_state.user_runs += 1
                    st.session_state.user_results.insert(0, result)
                    st.success(f"Done. Extracted {result['extracted']}, "
                               f"created {result['created']}, "
                               f"review {result['needs_review']}, "
                               f"rejected {result['rejected']}.")
            except Exception as e:
                st.error(f"Error: {type(e).__name__}: {e}")

# --- show user results ----------------------------------------------
if st.session_state.user_results:
    st.markdown("### Your results")
    for r in st.session_state.user_results:
        st.markdown(f"**PMID {r['pmid']}** — extracted {r['extracted']}, "
                    f"created {r['created']}, review {r['needs_review']}, "
                    f"rejected {r['rejected']}")

# --- footer ----------------------------------------------------------
st.divider()
st.caption(
    "Synapsis is a research prototype. Output is not medical advice. "
    "Every claim links to its source quote — verify before acting."
)
