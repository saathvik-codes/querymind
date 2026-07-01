"""
QueryMind evaluation — tests whether the backend returns valid SQL results
for each case in eval_cases.json.

Run: python run_eval.py [--api http://localhost:8030]
"""
import argparse, json, sys, time
from pathlib import Path

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

CASES = json.loads((Path(__file__).parent / "eval_cases.json").read_text())


def check(case: dict, result: dict) -> tuple[bool, str]:
    if result.get("error"):
        return False, f"API error: {result['error']}"
    rows = result.get("rows", [])
    if not rows:
        return False, "No rows returned"

    # row count exact
    if "expected_row_count" in case:
        n = case["expected_row_count"]
        if len(rows) != n:
            return False, f"Expected {n} rows, got {len(rows)}"

    # row count minimum
    if "expected_row_count_gte" in case:
        n = case["expected_row_count_gte"]
        if len(rows) < n:
            return False, f"Expected ≥{n} rows, got {len(rows)}"

    # top result check
    if "expected_top_result" in case and "expected_column" in case:
        col = case["expected_column"]
        top = str(rows[0].get(col, ""))
        if case["expected_top_result"].lower() not in top.lower():
            return False, f"Top {col} was '{top}', expected to contain '{case['expected_top_result']}'"

    # column presence
    if "expected_contains_column" in case:
        kw = case["expected_contains_column"].lower()
        if not any(kw in k.lower() for k in rows[0].keys()):
            return False, f"Expected a column containing '{kw}' in {list(rows[0].keys())}"

    return True, "ok"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8030")
    args = parser.parse_args()

    passed = failed = 0
    for case in CASES:
        try:
            resp = requests.post(f"{args.api}/query", json={"question": case["question"]}, timeout=60)
            result = resp.json()
        except Exception as e:
            result = {"error": str(e), "rows": [], "sql": "", "answer": None}

        ok, reason = check(case, result)
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] #{case['id']}: {case['question'][:60]}")
        if not ok:
            print(f"       → {reason}")
            print(f"       → SQL: {result.get('sql','')[:120]}")
        else:
            passed += 1
            failed += (0 if ok else 1)
        if not ok:
            failed += 1
        time.sleep(0.5)

    total = len(CASES)
    print(f"\n{passed}/{total} passed ({100*passed//total}%)")


if __name__ == "__main__":
    main()
