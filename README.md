# Composio AI Product Ops Intern — Take-Home

Research agent that evaluates 100 apps across 10 categories for agent-toolkit
buildability: auth method, self-serve vs gated access, API surface, MCP
availability, and a buildability verdict — each backed by a docs URL.

**Live page:** <your deployed link>
**Case study:** see `report.html` / deployed link above

---

## What's in this repo

```
agent/
  research_agent.py     # runs the 100-app research pass (Groq compound + web_search)
  generate_report.py    # builds the HTML case study from results
data/
  results.jsonl         # raw output, one JSON object per app
.env.example             # template for required environment variables
.gitignore
README.md
```

## Setup

1. Clone the repo and install dependencies:
   ```bash
   git clone https://github.com/rishabhdkmjha/Composio.git
   cd Composio
   pip install -r requirements.txt
   ```

2. Copy the environment template and add your own Groq API key:
   ```bash
   cp .env.example .env
   ```
   Then open `.env` and set:
   ```
   GROQ_API_KEY=your_key_here
   ```
   Get a free key at [console.groq.com](https://console.groq.com).

   > **Note on security:** `.env` is gitignored and never committed. If you're
   > forking this repo, always use your own key — never commit `.env` itself,
   > only `.env.example` with placeholder values.

## Running the research agent

Run the full 100-app pass:
```bash
python agent/research_agent.py
```

Re-research specific apps only (useful for re-checking flagged/low-confidence rows,
or testing on a new app not in the original 100):
```bash
python agent/research_agent.py --ids <app-ids>
```

The agent is **resumable**: each result is appended to `data/results.jsonl`
as soon as it's produced, so a rate limit or bad response on one app doesn't
lose progress on the rest — re-running skips apps already completed.

## Generating the report

```bash
python agent/generate_report.py
```

This reads `data/results.jsonl` and produces the case-study HTML page
(findings matrix, headline patterns, verification results).

## How it works

- Each app gets its own call to `groq/compound`, an agentic system on Groq's
  free tier with an automatically-triggered `web_search` tool — instructed to
  search the app's current developer docs (not answer from memory) and reply
  in a fixed JSON schema: category, auth methods, self-serve/gated, API
  surface, MCP existence, buildability verdict, evidence URL, and a
  confidence field.
- Low-confidence rows and a random sample are manually cross-checked against
  real docs — see the Verification section on the case-study page for the
  before/after accuracy numbers and a list of what the agent got wrong.
- A Composio-native variant is also available: same schema and verification
  loop, but pointed at Composio's own hosted MCP server instead of a generic
  web-search tool.

## Verification

Accuracy was measured on a 14-app sample, hand-checked against real docs on:
`auth_methods`, `self_serve`, `mcp_exists`, `buildability_verdict`. Results
and honest hit/miss breakdown are shown on the case-study page under
"Verification."
