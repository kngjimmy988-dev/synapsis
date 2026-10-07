"""
experiment_record.py
Synapsis — pre-registered experiment record.
Every virtual experiment is designed and logged BEFORE it runs.
"""

import json
from datetime import datetime, timezone

ENGINES = [
    "data_test", "forecasting", "docking",
    "pathway_sim", "quantum_lab", "learned_predictor",
]

STATUSES = ["planned", "running", "completed", "failed", "skipped"]


def make_experiment(claim_id, engine, prediction, data_source,
                    pass_criteria, fail_criteria,
                    budget_seconds=60, independence_note="", run=None):
    if engine not in ENGINES:
        raise ValueError(f"Engine '{engine}' invalid. Allowed: {ENGINES}")
    return {
        "claim_id": claim_id,
        "engine": engine,
        "prediction": prediction,
        "data_source": data_source,
        "independence_note": independence_note,
        "pass_criteria": pass_criteria,
        "fail_criteria": fail_criteria,
        "budget_seconds": budget_seconds,
        "status": "planned",
        "registered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "result": None,
        "run": run or {},
    }


def record_result(experiment, result_value, verdict, note=""):
    if verdict not in ("PASS", "FAIL", "INCONCLUSIVE"):
        raise ValueError("verdict must be PASS, FAIL, or INCONCLUSIVE")
    exp = dict(experiment)
    exp["status"] = "completed"
    exp["result"] = {
        "value": result_value,
        "verdict": verdict,
        "note": note,
        "completed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return exp


def to_card(experiment):
    e = experiment
    lines = [
        "─" * 60,
        f"EXPERIMENT  |  engine: {e['engine']}  |  claim #{e['claim_id']}",
        "─" * 60,
        f"Prediction  : {e['prediction']}",
        f"Data source : {e['data_source']}",
        f"Independence: {e['independence_note'] or '(not stated)'}",
        f"Pass if     : {e['pass_criteria']}",
        f"Fail if     : {e['fail_criteria']}",
        f"Status      : {e['status']}",
    ]
    if e.get("result"):
        r = e["result"]
        lines += [f"Result      : {r['value']}",
                  f"Verdict     : {r['verdict']}",
                  f"Note        : {r['note']}"]
    lines.append("─" * 60)
    return "\n".join(lines)


if __name__ == "__main__":
    exp = make_experiment(
        claim_id=1, engine="quantum_lab",
        prediction="VQE on 2 simulated qubits finds H2 ground-state energy",
        data_source="STO-3G Hamiltonian, bond length 0.735 A",
        independence_note="Reference energy from exact diagonalization, not VQE",
        pass_criteria="engine energy within 1e-4 Ha of classical reference",
        fail_criteria="engine energy differs by more than 1e-4 Ha",
        budget_seconds=30,
    )
    print(to_card(exp))
    exp = record_result(exp,
                        result_value="-1.137306 Ha (total, with nuclear repulsion)",
                        verdict="PASS",
                        note="H2 toy problem; matches classical reference")
    print("\nAfter running:\n")
    print(to_card(exp))
