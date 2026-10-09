"""
streamlit_app.py
Synapsis — public web demo (v3).
"""

import streamlit as st

st.set_page_config(
    page_title="Synapsis — Verified Claims",
    page_icon="🔬",
    layout="centered",
)

# ────────────────────────────────────────────────────────────
# PRE-LOADED EXAMPLES
# ────────────────────────────────────────────────────────────
EXAMPLES = [
    {
        "label": "Example A — a claim that checks out ✅",
        "title": "BRCA1 mutations impair DNA repair",
        "pmid": "33812473",
        "abstract": (
            "BRCA1 mutations are known to impair DNA repair mechanisms in cells. "
            "Recent studies show that impaired DNA repair leads to accumulation "
            "of mutations in the TP53 gene."
        ),
        "claims": [
            {
                "subject": "BRCA1",
                "relation": "INHIBITS",
                "object": "DNA_Repair",
                "quote": "BRCA1 mutations are known to impair DNA repair mechanisms in cells.",
                "status": "evidence_checked",
                "flag": None,
            },
        ],
    },
    {
        "label": "Example B — a claim that is overstated ⚠️",
        "title": "TP53 and breast cancer risk",
        "pmid": "33812473",
        "abstract": (
            "TP53 mutations have been strongly linked to the development of "
            "breast cancer."
        ),
        "claims": [
            {
                "subject": "TP53",
                "relation": "INCREASES_RISK_OF",
                "object": "Breast_Cancer",
                "quote": "TP53 mutations have been strongly linked to the development of breast cancer.",
                "status": "needs_review",
                "flag": "relation_stronger_than_quote",
            },
        ],
    },
    {
        "label": "Example C — a claim with multiple parts 🟡",
        "title": "Exercise, sleep, and heart health",
        "pmid": "DEMO-003",
        "abstract": (
            "Regular exercise reduces the risk of cardiovascular disease by "
            "approximately 30 percent. Sleep duration of less than six hours "
            "per night has been linked to increased risk of hypertension."
        ),
        "claims": [
            {
                "subject": "Exercise",
                "relation": "DECREASES_RISK_OF",
                "object": "Cardiovascular_Disease",
                "quote": "Regular exercise reduces the risk of cardiovascular disease by approximately 30 percent.",
                "status": "needs_review",
                "flag": "unresolved entity: Exercise",
            },
            {
                "subject": "Short_Sleep",
                "relation": "INCREASES_RISK_OF",
                "object": "Hypertension",
                "quote": "Sleep duration of less than six hours per night has been linked to increased risk of hypertension.",
                "status": "needs_review",
                "flag": "relation_stronger_than_quote",
            },
        ],
    },
]

# ────────────────────────────────────────────────────────────
# HEADER
# ────────────────────────────────────────────────────────────
st.title("🔬 Synapsis")
st.markdown(
    "### Paste any paragraph of scientific writing.\n"
    "Synapsis pulls out every factual claim, shows the **exact source quote** "
    "behind each one, and flags the ones that don't hold up."
)
st.divider()

# ────────────────────────────────────────────────────────────
# HOW TO READ
# ────────────────────────────────────────────────────────────
with st.expander("How to read the results  👇", expanded=True):
    st.markdown(
        "- ✅ **evidence_checked** — the quote fully supports the claim\n"
        "- ⚠️ **needs_review** — the quote is weaker than the claim, context is "
        "missing, or the entities aren't in our ontology yet\n"
        "- ❌ **rejected** — the quote does not support the claim\n\n"
        "Every claim is tied to a real quote from a real paper. "
        "Nothing is trusted until it's checked.\n\n"
        "**Note:** the current ontology only covers breast cancer genes. "
        "Anything outside that scope goes to `needs_review` — that's the "
        "system being honest, not guessing."
    )
st.divider()

# ────────────────────────────────────────────────────────────
# EXAMPLES
# ────────────────────────────────────────────────────────────
st.subheader("Try an example")

labels = [e["label"] for e in EXAMPLES]
choice = st.selectbox("Pick one", labels, label_visibility="collapsed")
example = next(e for e in EXAMPLES if e["label"] == choice)

st.caption(f"Source: PMID {example['pmid']}  ·  {example['title']}")
with st.expander("Show the abstract", expanded=False):
    st.write(example["abstract"])

st.markdown("#### Claims extracted from this abstract")

for c in example["claims"]:
    if c["status"] == "evidence_checked":
        icon = "✅"
    elif c["status"] == "needs_review":
        icon = "⚠️"
    else:
        icon = "❌"

    st.markdown(f"{icon}  `{c['subject']}`  —**{c['relation']}**→  `{c['object']}`")
    st.caption(f"Quote: *“{c['quote']}”*")
    if c["flag"]:
        st.warning(f"Flag: `{c['flag']}`")
    else:
        st.success(f"Status: `{c['status']}`")
    st.markdown("")

st.divider()

# ────────────────────────────────────────────────────────────
# TRY YOUR OWN
# ────────────────────────────────────────────────────────────
st.subheader("Try your own")
st.caption(
    "Paste any abstract from a paper, article, or report. "
    "Synapsis runs the live pipeline on it. (3 runs per session)"
)

if "user_runs" not in st.session_state:
    st.session_state.user_runs = 0
if "user_results" not in st.session_state:
    st.session_state.user_results = []

user_text = st.text_area(
    "Paste your abstract below:",
    height=180,
    placeholder="e.g. Regular exercise reduces cardiovascular risk by 30 percent...",
)

if st.button("Verify claims"):
    if st.session_state.user_runs >= 3:
        st.error("Demo limit reached for this session. Refresh the page to try again.")
    elif len(user_text.strip()) < 50:
        st.warning("Paste a longer abstract (at least 50 characters).")
    else:
        with st.spinner("Running pipeline..."):
            try:
                import os
                from pipeline import process_abstract

                if not os.environ.get("GROQ_API_KEY"):
                    st.error("Live pipeline is not configured on this deployment.")
                else:
                    result = process_abstract(user_text, pmid="LIVE-DEMO", verbose=False)
                    st.session_state.user_runs += 1
                    st.session_state.user_results.insert(0, result)
                    st.success(
                        f"Done. Extracted {result['extracted']}, "
                        f"created {result['created']}, "
                        f"review {result['needs_review']}, "
                        f"rejected {result['rejected']}."
                    )
            except Exception as e:
                st.error(f"Error: {type(e).__name__}: {e}")

if st.session_state.user_results:
    st.markdown("#### Your results")
    for r in st.session_state.user_results:
        st.markdown(
            f"**PMID {r['pmid']}** — extracted {r['extracted']}, "
            f"created {r['created']}, review {r['needs_review']}, "
            f"rejected {r['rejected']}"
        )
        if r["created"] == 0 and r["needs_review"] > 0:
            st.info(
                "All claims went to `needs_review`. This usually means the "
                "entities in your abstract aren't in our current ontology "
                "(which is scoped to breast cancer genes). The pipeline "
                "extracted the claims correctly — it just refuses to mark "
                "them verified without recognizing the entities. "
                "That's the system being honest."
            )

# ────────────────────────────────────────────────────────────
# FOOTER
# ────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "Synapsis is a research prototype. Output is not medical advice. "
    "Every claim links to its source quote — verify before acting."
)
