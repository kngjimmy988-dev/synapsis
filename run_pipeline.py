"""
run_pipeline.py
Synapsis — batch runner with rate-limit handling.

Loads abstracts from abstracts.json, runs each through the v0.3 pipeline,
retries on 429 (rate limit), collects results, and saves to run_results.json.
"""

import json
import os
import time
import traceback
from datetime import datetime, timezone

from pipeline import process_abstract
from claim_ledger import load_ledger

ABSTRACTS_FILE = "abstracts.json"
RESULTS_FILE = "run_results.json"

# Delay between abstracts (seconds). Groq free tier is ~30 req/min.
SLEEP_BETWEEN = 3.0

# Retry settings for 429s
MAX_RETRIES = 4
BACKOFF_START = 8   # seconds
BACKOFF_MULT = 2.0  # doubles each retry: 8, 16, 32, 64


def run_one_with_retry(abstract, pmid):
    """
    Run one abstract. On 429, wait and retry.
    Returns (result_dict, error_string_or_None).
    """
    wait = BACKOFF_START
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = process_abstract(abstract, pmid=pmid, verbose=False)
            return result, None
        except Exception as e:
            err_name = type(e).__name__
            err_msg = str(e)
            is_rate_limit = "429" in err_msg or "Too Many Requests" in err_msg

            if is_rate_limit and attempt < MAX_RETRIES:
                print(f"        [rate limit] waiting {wait}s then retrying "
                      f"(attempt {attempt}/{MAX_RETRIES})...")
                time.sleep(wait)
                wait *= BACKOFF_MULT
                continue

            # Out of retries, or a different error — give up on this one
            return None, f"{err_name}: {err_msg}"

    return None, "max retries exceeded"


def run_batch(abstracts, max_abstracts=None):
    if max_abstracts:
        abstracts = abstracts[:max_abstracts]

    print("=" * 60)
    print(f"BATCH RUN  |  {len(abstracts)} abstracts")
    print(f"Started: {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    print(f"Sleep between abstracts: {SLEEP_BETWEEN}s")
    print("=" * 60)

    results = []
    t0 = time.time()

    for i, a in enumerate(abstracts, 1):
        pmid = a.get("pmid", "UNKNOWN")
        title = (a.get("title") or "")[:60]
        print(f"\n[{i:02d}/{len(abstracts)}] PMID {pmid} — {title}...")

        t1 = time.time()
        result, error = run_one_with_retry(a["abstract"], pmid)
        elapsed = time.time() - t1

        if result is not None:
            result["elapsed_seconds"] = round(elapsed, 1)
            result["title"] = a.get("title", "")
            result["journal"] = a.get("journal", "")
            result["year"] = a.get("year", "")
            results.append(result)
            print(f"        extracted={result['extracted']}, "
                  f"created={result['created']}, "
                  f"dups={result['duplicates']}, "
                  f"review={result['needs_review']}, "
                  f"rejected={result['rejected']} "
                  f"({elapsed:.1f}s)")
        else:
            results.append({
                "pmid": pmid,
                "title": a.get("title", ""),
                "error": error,
                "traceback": "",
            })
            print(f"        ERROR: {error}")

        # Polite pause between abstracts
        if i < len(abstracts):
            time.sleep(SLEEP_BETWEEN)

    total_time = time.time() - t0
    print("\n" + "=" * 60)
    print(f"DONE — {len(results)} abstracts in {total_time/60:.1f} min")
    print("=" * 60)
    return results


def save_results(results, filename=RESULTS_FILE):
    with open(filename, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved results to {filename}")


def print_summary(results):
    totals = {
        "extracted": 0, "created": 0, "duplicates": 0,
        "needs_review": 0, "rejected": 0,
    }
    errors = 0
    for r in results:
        if "error" in r:
            errors += 1
            continue
        for k in totals:
            totals[k] += r.get(k, 0)

    print("\n" + "=" * 60)
    print("AGGREGATE SUMMARY")
    print("=" * 60)
    print(f"  Abstracts processed : {len(results) - errors}")
    print(f"  Errors              : {errors}")
    print(f"  Claims extracted    : {totals['extracted']}")
    print(f"  Claims created      : {totals['created']}")
    print(f"  Duplicates          : {totals['duplicates']}")
    print(f"  Needs review        : {totals['needs_review']}")
    print(f"  Rejected            : {totals['rejected']}")
    print("=" * 60)


if __name__ == "__main__":
    with open(ABSTRACTS_FILE, "r") as f:
        abstracts = json.load(f)
    print(f"Loaded {len(abstracts)} abstracts from {ABSTRACTS_FILE}")

    if os.path.exists("claim_ledger.json"):
        os.remove("claim_ledger.json")
        print("Cleared old claim_ledger.json")

    results = run_batch(abstracts)
    save_results(results)
    print_summary(results)
    print("\nDone. Results in run_results.json")
