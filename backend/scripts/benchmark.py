"""Compare Ollama models on extraction quality and speed (plan section 7 'selection method').

Usage (from backend/):
  python scripts/benchmark.py --models mistral:7b qwen2.5:7b [--limit 2]
Writes docs/benchmarks/benchmark-<timestamp>.json and prints a markdown table.
Metrics per model: JSON validity rate, expected-skill recall (golden set), average seconds.
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
from app.services.analysis.gap import normalize  # noqa: E402
from app.services.analysis.service import extract_profile, extract_requirements  # noqa: E402
from app.services.llm.client import LLMError, OllamaClient  # noqa: E402

SAMPLES = ROOT / "data" / "samples"


def recall(expected: list[str], found: list[str]) -> float:
    got = {normalize(s) for s in found}
    hits = sum(1 for e in expected if normalize(e) in got)
    return hits / len(expected) if expected else 1.0


def run_model(model: str, expected: dict, limit: int | None) -> dict:
    settings.evaluator_model = model
    llm = OllamaClient()
    rows = []
    resumes = list(expected["resumes"].items())[:limit]
    jds = list(expected["jds"].items())[:limit]
    for name, skills in resumes:
        text = (SAMPLES / "resumes" / f"{name}.txt").read_text()
        t = time.time()
        try:
            profile = extract_profile(llm, text)
            found = [s.name for s in profile.skills] + [t for p in profile.projects for t in p.tech_stack]
            rows.append({"kind": "resume", "name": name, "valid": True, "recall": recall(skills, found), "seconds": time.time() - t})
        except LLMError as exc:
            rows.append({"kind": "resume", "name": name, "valid": False, "recall": 0.0, "seconds": time.time() - t, "error": str(exc)})
        print(f"  [{model}] resume {name}: {rows[-1]}", flush=True)
    for name, exp in jds:
        text = (SAMPLES / "jds" / f"{name}.txt").read_text()
        t = time.time()
        try:
            req = extract_requirements(llm, text)
            rec = (recall(exp["must"], req.must_have_skills) + recall(exp["nice"], req.nice_to_have_skills)) / 2
            tech = {normalize(x) for x in exp["must"] + exp["nice"]}
            leaked = any(normalize(s) in tech for s in req.soft_skills)
            rows.append({"kind": "jd", "name": name, "valid": True, "recall": rec, "seconds": time.time() - t, "tech_in_soft_skills": leaked})
        except LLMError as exc:
            rows.append({"kind": "jd", "name": name, "valid": False, "recall": 0.0, "seconds": time.time() - t, "error": str(exc)})
        print(f"  [{model}] jd {name}: {rows[-1]}", flush=True)
    n = len(rows)
    return {
        "model": model,
        "valid_rate": sum(r["valid"] for r in rows) / n,
        "avg_recall": sum(r["recall"] for r in rows) / n,
        "avg_seconds": sum(r["seconds"] for r in rows) / n,
        "rows": rows,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--limit", type=int, default=None, help="only the first N resumes and JDs")
    args = ap.parse_args()
    expected = json.loads((SAMPLES / "expected.json").read_text())
    results = [run_model(m, expected, args.limit) for m in args.models]

    out = ROOT / "docs" / "benchmarks" / f"benchmark-{datetime.now():%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps(results, indent=2))
    print("\n| Model | JSON valid | Skill recall | Avg seconds |\n|---|---|---|---|")
    for r in results:
        print(f"| {r['model']} | {r['valid_rate']:.0%} | {r['avg_recall']:.0%} | {r['avg_seconds']:.0f} |")
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()
