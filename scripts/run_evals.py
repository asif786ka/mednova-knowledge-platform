"""
Offline evaluation harness.

Runs the agentic router over eval/eval_dataset.json and reports:
  - route accuracy   (did the agent pick an acceptable strategy?)
  - source recall    (did the answer cite at least one expected source?)
  - keyword recall   (did the answer contain at least one expected keyword?)
  - honesty          (did it refuse the out-of-domain question?)

Usage:  python scripts/run_evals.py
Exit code is non-zero if the overall pass rate drops below THRESHOLD (CI-friendly).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.ingestion.pipeline import IngestionPipeline, load_stores  # noqa: E402
from app.agents.router import AgenticRouter  # noqa: E402

THRESHOLD = 0.85


def ensure_index():
    vs, gs = load_stores()
    if vs.count() == 0:
        IngestionPipeline().ingest_folder()
        vs, gs = load_stores()
    return vs, gs


def contains_any(text: str, needles) -> bool:
    t = text.lower()
    return any(n.lower() in t for n in needles)


def main() -> int:
    data = json.loads((ROOT / "eval" / "eval_dataset.json").read_text())
    vs, gs = ensure_index()
    router = AgenticRouter(vs, gs)

    rows, passed = [], 0
    for case in data["cases"]:
        ans = router.answer(case["question"])
        answer_text = ans.answer
        refusal = "enough information" in answer_text.lower()

        if case.get("expect_refusal"):
            ok_route = True
            ok_src = True
            ok_kw = refusal
            case_pass = refusal
        else:
            ok_route = ans.route in case["expected_route"]
            ok_src = contains_any(" ".join(ans.sources), case["expected_sources_any"])
            ok_kw = contains_any(answer_text, case["expected_keywords_any"])
            # a case passes if it routed acceptably AND (cited a source OR hit a keyword)
            case_pass = ok_route and (ok_src or ok_kw) and not refusal
        passed += int(case_pass)
        rows.append((case["id"], case["question"][:52], ans.route,
                     ok_route, ok_src, ok_kw, case_pass))

    print(f"\n{'ID':<3} {'Question':<54} {'route':<8} {'R':<2}{'S':<2}{'K':<2} pass")
    print("-" * 82)
    for cid, q, route, r, s, k, p in rows:
        mark = lambda b: "✓" if b else "·"
        print(f"{cid:<3} {q:<54} {route:<8} {mark(r):<2}{mark(s):<2}{mark(k):<2} "
              f"{'PASS' if p else 'FAIL'}")

    rate = passed / len(rows)
    print("-" * 82)
    print(f"Passed {passed}/{len(rows)}  ({rate:.0%})   "
          f"[R=route ok, S=source recall, K=keyword recall]")
    if rate < THRESHOLD:
        print(f"FAILED: pass rate {rate:.0%} < threshold {THRESHOLD:.0%}")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
