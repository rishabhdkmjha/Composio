"""
Builds data/verification.json -- the accuracy story for the report:

  Pass 0 (baseline.jsonl):  no-tools model memory
  Pass 1 (results.jsonl):   web_search-grounded agent
  Pass 2 (human_truth):     YOU manually open the real docs for the sample and
                             fill in human_truth.json (see the printed template)

It compares Pass 0 vs Pass 2 and Pass 1 vs Pass 2 field-by-field on the fields
that matter most (auth_methods, self_serve, mcp_exists, buildability_verdict)
and reports per-pass accuracy, so the report can honestly say "went from X% to Y%".

Usage:
  # 1. Pick ~15 app ids as your verification sample (mix of easy/hard/gated apps)
  # 2. Run baseline_naive.py and research_agent.py --ids on that same sample
  # 3. python agent/verify.py --ids 3,12,27,... --emit-template   (writes a blank human_truth.json)
  # 4. Open human_truth.json, fill in the real answers by hand from actual docs
  # 5. python agent/verify.py --ids 3,12,27,...                    (computes accuracy)
"""
import json, argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "data" / "baseline.jsonl"
RESULTS = ROOT / "data" / "results.jsonl"
HUMAN_TRUTH = ROOT / "data" / "human_truth.json"
OUT = ROOT / "data" / "verification.json"

FIELDS_TO_CHECK = ["auth_methods", "self_serve", "mcp_exists", "buildability_verdict"]


def load_jsonl_by_id(path):
    out = {}
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            out[row["id"]] = row
    return out


def field_matches(a, b, field):
    va, vb = a.get(field), b.get(field)
    if field == "auth_methods":
        # order-insensitive set compare, case-insensitive
        sa = {str(x).lower() for x in (va or [])}
        sb = {str(x).lower() for x in (vb or [])}
        return sa == sb
    return str(va).strip().lower() == str(vb).strip().lower()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", type=str, required=True)
    parser.add_argument("--emit-template", action="store_true")
    args = parser.parse_args()
    ids = [int(x) for x in args.ids.split(",")]

    if args.emit_template:
        results = load_jsonl_by_id(RESULTS)
        template = {}
        for i in ids:
            r = results.get(i, {})
            template[str(i)] = {
                "app": r.get("app", ""),
                "auth_methods": ["<fill in from real docs>"],
                "self_serve": "<self-serve|gated|partial>",
                "mcp_exists": "<true|false>",
                "buildability_verdict": "<buildable today|buildable with workaround|blocked>",
                "notes": "<what you found by hand, any surprises>",
            }
        HUMAN_TRUTH.write_text(json.dumps(template, indent=2))
        print(f"Wrote blank template for {len(ids)} apps to {HUMAN_TRUTH}")
        print("Fill it in by hand from the real docs, then re-run without --emit-template.")
        return

    if not HUMAN_TRUTH.exists():
        print("No human_truth.json yet -- run with --emit-template first, fill it in, then re-run.")
        return

    baseline = load_jsonl_by_id(BASELINE)
    results = load_jsonl_by_id(RESULTS)
    human = json.loads(HUMAN_TRUTH.read_text())

    report = {"sample_size": len(ids), "fields_checked": FIELDS_TO_CHECK, "per_app": [], "pass_accuracy": {}}
    scores = {"pass0_baseline": [], "pass1_agent": []}

    for i in ids:
        truth = human.get(str(i))
        if not truth:
            continue
        b = baseline.get(i, {})
        r = results.get(i, {})
        row = {"id": i, "app": truth.get("app"), "pass0": {}, "pass1": {}}
        for field in FIELDS_TO_CHECK:
            m0 = field_matches(b, truth, field) if b else None
            m1 = field_matches(r, truth, field) if r else None
            row["pass0"][field] = m0
            row["pass1"][field] = m1
            if m0 is not None:
                scores["pass0_baseline"].append(m0)
            if m1 is not None:
                scores["pass1_agent"].append(m1)
        report["per_app"].append(row)

    for k, v in scores.items():
        report["pass_accuracy"][k] = round(100 * sum(v) / len(v), 1) if v else None

    OUT.write_text(json.dumps(report, indent=2))
    print(json.dumps(report["pass_accuracy"], indent=2))
    print(f"Full breakdown written to {OUT}")


if __name__ == "__main__":
    main()
