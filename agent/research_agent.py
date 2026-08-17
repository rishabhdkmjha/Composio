"""
Research agent rewritten to call a plain Groq model and an explicit
Tavily search per app.

Behavior:
 - For each app in `data/apps.json` the script makes a single Tavily
   search request and collects the top few snippets.
 - It then calls a plain Groq-compatible model (e.g. `openai/gpt-oss-20b`)
   with the app details plus the few snippets as evidence, asking the
   model to reply with the fixed JSON schema only.
 - Results are appended to `data/results.jsonl` as they complete so
   runs are resumable.

Environment:
 - Set `GROQ_API_KEY` (used by the Groq client library).
 - Set `TAVILY_API_KEY` and optionally `TAVILY_API_URL` (defaults to
     https://api.tavily.com/search). The Tavily API shape may differ in
   your environment; this wrapper is intentionally minimal and robust.

Usage:
  python agent/research_agent.py

"""

import os
import sys
import json
import time
import argparse
from pathlib import Path

try:
    import requests
except Exception:
    sys.exit("Run: pip install requests")

try:
    from groq import Groq
except ImportError:
    sys.exit("Run: pip install groq --break-system-packages")

ROOT = Path(__file__).resolve().parent.parent
APPS_PATH = ROOT / "data" / "apps.json"
RESULTS_PATH = ROOT / "data" / "results.jsonl"

# Use a plain (non-compound) Groq model that does NOT perform automatic
# tool invocation. Example: openai/gpt-oss-20b (fast/cheap TPM profile).
MODEL = os.getenv("RESEARCH_MODEL", "openai/gpt-oss-20b")

SYSTEM_PROMPT = """You are a product-ops research analyst. You will be
provided a short description of an app and a small set of search snippets
extracted from public developer/docs pages. Rely ONLY on the provided
snippets (they are the canonical evidence for this run). Do NOT attempt to
call any external tools. Answer ONLY with a single JSON object matching
the exact schema described below, with no extra text or markdown fences.

Schema:
{
  "category_one_liner": "<what the product does, one line>",
  "auth_methods": ["OAuth2" | "API key" | "Basic" | "Token" | "Other" | "Unclear"],
  "self_serve": "self-serve" | "gated" | "partial" | "unclear",
  "gating_reason": "<why gated/partial; empty if self-serve>",
  "api_surface": "<REST/GraphQL/etc, and roughly how broad -- 'narrow','moderate','broad'>",
  "mcp_exists": true | false | "unclear",
  "mcp_evidence": "<if true, one-line evidence; empty otherwise>",
  "buildability_verdict": "buildable today" | "buildable with workaround" | "blocked",
  "main_blocker": "<single biggest blocker; empty if buildable>",
  "evidence_url": "<the single best docs URL from the snippets>",
  "confidence": "high" | "medium" | "low"
}
"""
# Make the model output the JSON object immediately as the first character.
# This discourages preamble or chain-of-thought text before the JSON.
SYSTEM_PROMPT += "\nOutput the JSON object immediately as your first character. Do not include any reasoning, explanation, or preamble before or after it." 


def load_apps():
    return json.loads(APPS_PATH.read_text())


def already_done_ids():
    if not RESULTS_PATH.exists():
        return set()
    done = set()
    for line in RESULTS_PATH.read_text().splitlines():
        if line.strip():
            try:
                done.add(json.loads(line)["id"])
            except Exception:
                pass
    return done


def tavily_search(query: str, top_k: int = 3):
    """Call Tavily search and return a list of top snippets.

    This wrapper is intentionally tolerant: it expects the Tavily API to
    return JSON with a `results` list containing `title`, `url`, and
    `snippet` keys. If the real Tavily API differs, set `TAVILY_API_URL`
    to the correct endpoint and adapt payload parsing.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY is not set in the environment")
    url = os.getenv("TAVILY_API_URL", "https://api.tavily.com/search")
    payload = {"query": query, "top_k": top_k}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        # Don't fail the whole run for a single search failure; return empty list
        print(f"Tavily search failed: {e}")
        return []

    results = []
    # Try a few common shapes
    candidates = data.get("results") or data.get("hits") or data.get("data") or []
    for item in candidates[:top_k]:
        title = item.get("title") or item.get("headline") or ""
        url_ = item.get("url") or item.get("link") or ""
        snippet = item.get("snippet") or item.get("summary") or item.get("text") or ""
        results.append({"title": title, "url": url_, "snippet": snippet})

    return results


def extract_json(raw: str) -> str:
    raw = raw.strip().strip("`")
    if raw.lower().startswith("json"):
        raw = raw[4:].strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        raw = raw[start : end + 1]
    return raw


def research_one(client, app, snippets_top_k: int = 3):
    # Build a short query and perform one Tavily search
    query = f"{app['app']} developer API docs {app.get('hint','') or ''}"
    snippets = tavily_search(query, top_k=snippets_top_k)

    snippets_text = "\n\n".join(
        [f"{i+1}. {s['title']} — {s['url']}\n{s['snippet']}" for i, s in enumerate(snippets)]
    )

    user_prompt = (
        f"Research this app for an agent-toolkit buildability assessment:\n"
        f"Name: {app['app']}\n"
        f"Category: {app['category']}\n"
        f"Hint: {app.get('hint','')}\n\n"
        f"We ran a single Tavily search and here are the top snippets (use only these):\n\n{snippets_text}\n\n"
        f"Based on ONLY the snippets above, determine auth method(s), whether "
        f"credentials are self-serve or gated, the API surface, whether an MCP "
        f"server exists (official or community), a buildability verdict, and the best "
        f"single evidence URL from the snippets. Reply with the JSON object only."
    )

    # Call a plain Groq-compatible model (no automatic tools)
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.15,
        max_tokens=1500,
    )

    raw = resp.choices[0].message.content or ""
    finish_reason = getattr(resp.choices[0], "finish_reason", None)

    try:
        parsed = json.loads(extract_json(raw))
    except json.JSONDecodeError:
        parsed = {"parse_error": True, "raw_output": raw, "finish_reason": finish_reason}

    parsed["id"] = app["id"]
    parsed["app"] = app["app"]
    parsed["category"] = app["category"]
    parsed["researched_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if snippets:
        parsed["_snippets_used"] = [s.get("url") for s in snippets]

    return parsed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="research only the first N apps")
    parser.add_argument("--ids", type=str, default=None, help="comma-separated app ids to (re-)research")
    parser.add_argument("--force", action="store_true", help="re-research even if already in results.jsonl")
    parser.add_argument("--snippets", type=int, default=3, help="how many Tavily snippets to pass to the model")
    args = parser.parse_args()

    apps = load_apps()
    if args.ids:
        wanted = {int(x) for x in args.ids.split(",")}
        apps = [a for a in apps if a["id"] in wanted]
    if args.limit:
        apps = apps[: args.limit]

    done = set() if args.force else already_done_ids()
    todo = [a for a in apps if a["id"] not in done]

    if not todo:
        print("Nothing to do -- all requested apps already have results.")
        return

    client = Groq()  # reads GROQ_API_KEY from env
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(RESULTS_PATH, "a", encoding="utf-8") as f:
        for i, app in enumerate(todo, 1):
            print(f"[{i}/{len(todo)}] researching #{app['id']} {app['app']} ...", end=" ", flush=True)
            try:
                result = research_one(client, app, snippets_top_k=args.snippets)
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
                f.flush()
                status = "OK" if not result.get("parse_error") else "PARSE ERROR"
                print(status)
            except Exception as e:
                print(f"FAILED: {e}")
                f.write(json.dumps({"id": app["id"], "app": app["app"], "error": str(e)}) + "\n")
                f.flush()
            # pace requests a little to avoid throttling
            time.sleep(1.0)


if __name__ == "__main__":
    main()
