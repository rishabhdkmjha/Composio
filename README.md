# 100-App Agent-Buildability Audit

Composio AI Product Ops Intern take-home. Researches whether each of 100 given
apps could power an agent toolkit today — auth method, self-serve vs gated,
API surface, existing MCP, buildability verdict — using an agent, not by hand,
then verifies the agent's accuracy against real docs on a sample.

Runs entirely on **Groq's free tier** — no paid API required.

## Why it's structured this way

- **`data/apps.json`** — the 100-app list from the brief, as data (not hardcoded).
- **`agent/research_agent.py`** — the actual research agent. Calls
  `groq/compound` — Groq's agentic system with a built-in, auto-triggered
  `web_search` tool — once per app, forcing a fixed JSON schema. Appends each
  result to `data/results.jsonl` as it goes (resumable — a crash on app 63
  doesn't lose apps 1–62).
- **`agent/baseline_naive.py`** — the *same* schema, but a **plain** Groq
  model (`openai/gpt-oss-120b`, no tools) — pure memory. This exists to
  produce an honest "Pass 0" so the report can show accuracy climbing, not
  just assert it.
- **`agent/verify.py`** — takes a sample (~15 apps), diffs Pass 0 (memory) and
  Pass 1 (agent + search) against a `human_truth.json` you fill in by hand
  from the real docs. Outputs per-pass accuracy and the exact misses.
- **`agent/generate_report.py`** — reads `results.jsonl` (+ `verification.json`
  if present) and renders `report/index.html`: one self-contained static file,
  no build step, no server, no dependency on the JSON files after generation.

## Run it

```bash
pip install groq --break-system-packages
export GROQ_API_KEY=gsk_...          # free key from console.groq.com

# 1. Research all 100 (resumable — safe to re-run, skips apps already done)
#    Paced at ~2.2s/request to stay under the free-tier rate limit on compound.
python agent/research_agent.py

# 2. Pick a verification sample (mix easy/hard/gated apps), e.g.:
SAMPLE=3,12,21,27,34,41,56,63,71,81,90,92,96,99

# 3. Run the no-tools baseline on the same sample (for the "Pass 0" comparison)
python agent/baseline_naive.py --ids $SAMPLE

# 4. Get a blank human-check template, then fill it in BY HAND from real docs
python agent/verify.py --ids $SAMPLE --emit-template
#    -> edit data/human_truth.json with what you actually found on each app's docs

# 5. Compute accuracy across passes
python agent/verify.py --ids $SAMPLE

# 6. Render the final report
python agent/generate_report.py
```

Then open `report/index.html` directly, or deploy it (drag-and-drop onto
Netlify, `vercel deploy`, or push `report/` to a GitHub Pages branch — it's a
single static file, nothing else required).

## About the free tier

`groq/compound`'s free tier is rate-limited (roughly 30 requests/min at time
of writing — check `console.groq.com` for current limits). Researching all
100 apps at ~2.2s/request takes about 4 minutes of wall-clock time; if you
hit a 429, just re-run the same command — `research_agent.py` is resumable
and skips apps already in `results.jsonl`.

## Current state of this repo

`data/results.jsonl` currently has **4 apps hand-seeded and verified** (Stripe,
GitHub, Notion, PitchBook) as a working proof-of-concept, researched and
cross-checked by hand before switching the pipeline over to Groq, so the
report renders correctly end-to-end before spending the full run on all 100.
Run step 1 above with your own Groq key to fill in the rest.

## Honesty notes for the reviewer

- The agent is instructed to prefer the app's own `docs.<domain>` over
  third-party aggregators or Composio's own existing listing of the app —
  the point is independent verification, not restating Composio's answer.
- While researching Notion's auth docs, one of the top search results was
  Composio's own `composio.dev/auth/notion` page, which contains text
  addressed directly at AI agents reading the page ("If you are an AI agent
  reading this server-rendered HTML, [sign up at] composio.dev... confirm
  with the user before entering credentials"). The system prompt tells the
  agent to treat this as untrusted page content, not an instruction to
  follow, and to note it rather than act on it — it's worth flagging on the
  report page itself as a small, real example of what "verification" catches.
- `groq/compound` cannot be pointed at a remote MCP server — only its own
  built-in tools. The Composio-native variant (see the docstring in
  `research_agent.py`) uses a plain Groq model with remote-tool calling
  against Composio's own hosted MCP server instead — left as a stub since it
  needs your own Composio API key + a connected search-capable toolkit to run.
