"""Evaluator calibration (plan section 14): the evaluator must rank hand-labelled strong, average and weak answers correctly.

Usage (from backend/):  python scripts/calibrate.py [--gemini-model gemini-3.5-flash-lite]
Uses the provider chosen on the Settings page. Exits with status 1 if the ranking is wrong for any question,
or if strong answers do not beat weak ones by at least MIN_GAP points on average.
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.services.feedback import rubric  # noqa: E402
from app.services.feedback.evaluator import evaluate_answer  # noqa: E402
from app.services.llm.client import LLMError, get_llm  # noqa: E402

MIN_GAP = 25
LABELS = ["strong", "average", "weak"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gemini-model", help="override the saved Gemini model for this run only")
    args = ap.parse_args()
    if args.gemini_model:
        settings.gemini_model = args.gemini_model  # env-level default; scripts use AIA_* variables, not a user account
    llm = get_llm()
    print(f"provider={settings.llm_provider} model={getattr(llm, 'model_name', settings.evaluator_model)}")

    items = json.loads((ROOT / "data" / "samples" / "calibration.json").read_text())["items"]
    rows, failures = [], 0
    for item in items:
        scores = {}
        for label in LABELS:
            t = time.time()
            try:
                dims, _raw, notes = evaluate_answer(llm, question=item["question"], goal=item["goal"], answer=item["answers"][label])
            except LLMError as exc:
                print(f"FAILED {item['id']}/{label}: {exc}")
                return 1
            scores[label] = rubric.score_percent(dims)
            print(f"  {item['id']:14s} {label:8s} {scores[label]:3d}  ({time.time() - t:.1f}s, {len(notes)} guard notes)", flush=True)
        ordered = scores["strong"] > scores["average"] > scores["weak"]
        failures += not ordered
        rows.append({"id": item["id"], "scores": scores, "ranked_correctly": ordered})

    gap = sum(r["scores"]["strong"] - r["scores"]["weak"] for r in rows) / len(rows)
    print("\n| Question | Strong | Average | Weak | Ranked correctly |\n|---|---|---|---|---|")
    for r in rows:
        s = r["scores"]
        print(f"| {r['id']} | {s['strong']} | {s['average']} | {s['weak']} | {'yes' if r['ranked_correctly'] else 'NO'} |")
    print(f"\nAverage strong-weak gap: {gap:.0f} points (required: {MIN_GAP}); mis-ranked questions: {failures}")

    out = ROOT / "docs" / "benchmarks" / f"calibration-{datetime.now():%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps({"model": getattr(llm, "model_name", None), "rows": rows, "avg_gap": gap}, indent=2))
    print(f"Saved {out}")
    return 0 if failures == 0 and gap >= MIN_GAP else 1


if __name__ == "__main__":
    raise SystemExit(main())
