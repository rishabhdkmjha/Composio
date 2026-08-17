"""
Pass 0 -- the naive baseline: same schema, but a PLAIN Groq model (no
compound, no tools). It answers purely from training memory.

This exists on purpose so the report can honestly show:
  Pass 0 (memory only, openai/gpt-oss-120b) -> lowest accuracy, stale/guessed answers
  Pass 1 (agent + groq/compound web_search)  -> higher accuracy, grounded in live docs
  Pass 2 (human spot-check)                  -> corrected sample, final trustworthiness number

Run this on the SAME sample you'll verify by hand later (see verify.py), so the
comparison in the report is apples-to-apples.

Usage:
  export GROQ_API_KEY=gsk_...
  python agent/baseline_naive.py --ids 3,12,27,41,56,73,88,92  (same ids as your sample)
"""
import os, sys, json, time, argparse
from pathlib import Path

try:
    from groq import Groq
except ImportError:
    sys.exit("Run: pip install groq --break-system-packages")

ROOT = Path(__file__).resolve().parent.parent
APPS_PATH = ROOT / "data" / "apps.json"
OUT_PATH = ROOT / "data" / "baseline.jsonl"

# Plain (non-compound) model -- no tools available, so this is genuinely memory-only.
# gpt-oss-120b is the current recommended general-purpose model on Groq
# (llama-3.3-70b-versatile was deprecated in June 2026).
MODEL = "openai/gpt-oss-120b"

# Same schema as research_agent.py, deliberately -- so fields diff cleanly later
SYSTEM_PROMPT = """You are a product-ops research analyst. Answer from your own \
knowledge only -- you have NO tools available, so do not claim to have checked docs. \
Return ONLY a single JSON object, no markdown fences, matching exactly:
{
  "category_one_liner": "...",
  "auth_methods": ["OAuth2" | "API key" | "Basic" | "Token" | "Other" | "Unclear"],
  "self_serve": "self-serve" | "gated" | "partial" | "unclear",
  "gating_reason": "...",
  "api_surface": "...",
  "mcp_exists": true | false | "unclear",
  "mcp_evidence": "...",
  "buildability_verdict": "buildable today" | "buildable with workaround" | "blocked",
  "main_blocker": "...",
  "evidence_url": "<your best guess, may be wrong/outdated -- that's expected here>",
  "confidence": "high" | "medium" | "low"
}"""


def extract_json(raw: str) -> str:
    raw = raw.strip().strip("`")
    if raw.lower().startswith("json"):
        raw = raw[4:].strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        raw = raw[start : end + 1]
    return raw


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", type=str, required=True, help="comma-separated app ids, should match your verify sample")
    args = parser.parse_args()

    apps = {a["id"]: a for a in json.loads(APPS_PATH.read_text())}
    wanted = [int(x) for x in args.ids.split(",")]

    client = Groq()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        for i, app_id in enumerate(wanted, 1):
            app = apps[app_id]
            print(f"[{i}/{len(wanted)}] baseline (no tools) for #{app_id} {app['app']} ...", end=" ", flush=True)
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"App: {app['app']} ({app['hint']}), category: {app['category']}"},
                ],
                temperature=0.2,
                max_tokens=1000,
            )
            raw = resp.choices[0].message.content or ""
            try:
                parsed = json.loads(extract_json(raw))
            except json.JSONDecodeError:
                parsed = {"parse_error": True, "raw_output": raw}
            parsed["id"] = app_id
            parsed["app"] = app["app"]
            f.write(json.dumps(parsed) + "\n")
            f.flush()
            print("OK")
            time.sleep(1.5)


if __name__ == "__main__":
    main()
