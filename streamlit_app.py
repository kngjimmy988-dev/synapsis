"""
streamlit_app.py
Synapsis — public web demo (v4 — plain English).
"""

import streamlit as st

st.set_page_config(
    page_title="Synapsis — Verified Claims",
    page_icon="🔬",
    layout="centered",
)

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
                "status": "Verified",
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
                "status": "Needs a look",
                "flag": "the quote says 'linked to', the claim says 'increases risk'",
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
                "status": "Needs a look",
                "flag": "'Exercise' isn't in the current list of known entities",
            },
            {
                "subject": "Short_Sleep",
                "relation": "INCREASES_RISK_OF",
                "object": "Hypertension",
                "quote": "Sleep duration of less than six hours per night has been linked to increased risk of hypertension.",
                "status": "Needs a look",
                "flag": "the quote says 'linked to', the claim says 'increases risk'",
            },
        ],
    },
]

ICON = {
    "Verified": "✅",
    "Needs a look": "⚠️",
    "Failed": "❌",
}

st.title("🔬 Synapsis")
st.markdown(
    "### Paste any paragraph of scientific writing.\n"
    "Synapsis pulls out every factual claim and checks it against the exact "
    "source quote. It tells you which claims hold up, and which need a closer look."
)
st.divider()

with st.expander("How to read the results  👇", expanded=True):
    st.markdown(
        "- ✅ **Verified** — the quote supports the claim\n"
        "- ⚠️ **Needs a look** — the tool couldn't confirm it (usually the entities "
        "aren't in its current list, or the quote is weaker than the claim)\n"
        "- ❌ **Failed** — the quote does not support the claim\n\n"
        "Every claim is tied to a real quote from a real paper. "
        "Nothing is trusted until it's checked."
    )
st.divider()

st.subheader("Try an example")
labels = [e["label"] for e in EXAMPLES]
choice = st.selectbox("Pick one", labels, label_visibility="collapsed")
example = next(e for e in EXAMPLES if e["label"] == choice)

st.caption(f"Source: PMID {example['pmid']}  ·  {example['title']}")
with st.expander("Show the abstract", expanded=False):
    st.write(example["abstract"])

st.markdown("#### Claims found in this abstract")
for c in example["claims"]:
    icon = ICON.get(c["status"], "•")
    st.markdown(f"{icon}  `{c['subject']}`  —**{c['relation']}**→  `{c['object']}`")
    st.caption(f"Quote: *“{c['quote']}”*")
    if c["flag"]:
        st.warning(f"Why: {c['flag']}")
    else:
        st.success(f"Status: {c['status']}")
    st.markdown("")

st.divider()

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

if st.button("Check claims"):
    if st.session_state.user_runs >= 3:
        st.error("Demo limit reached for this session. Refresh to try again.")
    elif len(user_text.strip()) < 50:
        st.warning("Paste a longer abstract (at least 50 characters).")
    else:
        with st.spinner("Checking..."):
            try:
                import os
                from pipeline import process_abstract

                if not os.environ.get("GROQ_API_KEY"):
                    st.error("The live pipeline is not configured on this deployment.")
                else:
                    result = process_abstract(user_text, pmid="LIVE-DEMO", verbose=False)
                    st.session_state.user_runs += 1
                    st.session_state.user_results.insert(0, result)
                    st.success(
                        f"Found {result['extracted']} claims.  "
                        f"{result['created']} Verified.  "
                        f"{result['needs_review']} need a look.  "
                        f"{result['rejected']} failed."
                    )
            except Exception as e:
                st.error(f"Error: {type(e).__name__}: {e}")

if st.session_state.user_results:
    st.markdown("#### Your results")
    for r in st.session_state.user_results:
        st.markdown(
            f"**PMID {r['pmid']}** — Found {r['extracted']}, "
            f"Verified {r['created']}, Needs a look {r['needs_review']}, "
            f"Failed {r['rejected']}"
        )
        if r["created"] == 0 and r["needs_review"] > 0:
            st.info(
                "None of the claims were verified. That usually means the "
                "entities in your abstract aren't in the current list "
                "(which covers genes, proteins, compounds, organisms, and "
                "diseases). The tool extracted the claims — it just wouldn't "
                "verify them without recognizing the entities. "
                "That's the tool being honest."
            )

st.divider()
st.caption(
    "Synapsis is a research prototype. Output is not medical advice. "
    "Every claim links to its source quote — verify before acting."
)
