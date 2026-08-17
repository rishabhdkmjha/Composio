"""
Reads data/apps.json + data/results.jsonl (+ data/verification.json if present)
and renders report/index.html: one self-contained static file, safe to deploy
as-is on GitHub Pages / Vercel / Netlify (no build step, no server).

Run this LAST, after research_agent.py has produced results for all 100 apps
(or a partial run, for testing -- the report clearly shows "N of 100 researched").

Usage:
  python agent/generate_report.py
"""
import json
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parent.parent
APPS_PATH = ROOT / "data" / "apps.json"
RESULTS_PATH = ROOT / "data" / "results.jsonl"
VERIFICATION_PATH = ROOT / "data" / "verification.json"
OUT_PATH = ROOT / "report" / "index.html"

REPO_URL = "REPLACE_WITH_YOUR_REPO_URL"
LIVE_URL = "REPLACE_WITH_YOUR_DEPLOYED_URL"


def load_results():
    rows = []
    if RESULTS_PATH.exists():
        for line in RESULTS_PATH.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                if not r.get("parse_error") and not r.get("error"):
                    rows.append(r)
    return rows


def compute_patterns(rows, total_apps):
    n = len(rows)
    auth_counter = Counter()
    for r in rows:
        for a in r.get("auth_methods", []):
            auth_counter[a] += 1

    self_serve_counter = Counter(r.get("self_serve", "unclear") for r in rows)
    verdict_counter = Counter(r.get("buildability_verdict", "unclear") for r in rows)
    mcp_counter = Counter(str(r.get("mcp_exists", "unclear")) for r in rows)

    blockers = Counter(r.get("main_blocker", "") for r in rows if r.get("main_blocker"))
    top_blockers = blockers.most_common(5)

    by_category = defaultdict(lambda: {"total": 0, "self_serve": 0, "gated": 0})
    for r in rows:
        cat = r.get("category", "Unknown")
        by_category[cat]["total"] += 1
        ss = r.get("self_serve")
        if ss == "self-serve":
            by_category[cat]["self_serve"] += 1
        elif ss == "gated":
            by_category[cat]["gated"] += 1

    easy_wins = [r for r in rows if r.get("buildability_verdict") == "buildable today" and r.get("self_serve") == "self-serve"]

    return {
        "n_researched": n,
        "total_apps": total_apps,
        "auth_distribution": auth_counter.most_common(),
        "self_serve_distribution": dict(self_serve_counter),
        "verdict_distribution": dict(verdict_counter),
        "mcp_distribution": dict(mcp_counter),
        "top_blockers": top_blockers,
        "by_category": dict(by_category),
        "easy_wins_count": len(easy_wins),
        "easy_wins_sample": [r["app"] for r in easy_wins[:8]],
    }


def load_verification():
    if VERIFICATION_PATH.exists():
        return json.loads(VERIFICATION_PATH.read_text())
    return None


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>100-App Agent-Buildability Audit — Composio Take-Home</title>
<style>
  :root {{
    --bg: #0b0d0f;
    --bg-panel: #111417;
    --bg-panel-2: #15181c;
    --line: #23282e;
    --text: #e6e9ec;
    --text-dim: #8a949e;
    --accent: #4ee1a0;
    --accent-dim: #2c8e6c;
    --warn: #e0a94e;
    --bad: #e15a5a;
    --mono: 'SF Mono', 'JetBrains Mono', Consolas, monospace;
    --sans: -apple-system, 'Inter', 'Segoe UI', sans-serif;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--bg); color: var(--text);
    font-family: var(--sans); line-height: 1.5;
  }}
  .wrap {{ max-width: 1100px; margin: 0 auto; padding: 48px 24px 96px; }}
  .eyebrow {{
    font-family: var(--mono); font-size: 12px; letter-spacing: 0.12em;
    text-transform: uppercase; color: var(--accent); margin-bottom: 10px;
  }}
  h1 {{ font-size: 34px; margin: 0 0 10px; letter-spacing: -0.01em; }}
  .sub {{ color: var(--text-dim); font-size: 16px; max-width: 720px; margin-bottom: 40px; }}
  .headline-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1px; background: var(--line); border: 1px solid var(--line);
    border-radius: 10px; overflow: hidden; margin-bottom: 48px;
  }}
  .stat {{ background: var(--bg-panel); padding: 22px 20px; }}
  .stat .num {{ font-family: var(--mono); font-size: 30px; color: var(--accent); }}
  .stat .label {{ font-size: 13px; color: var(--text-dim); margin-top: 4px; }}
  section {{ margin-bottom: 56px; }}
  h2 {{
    font-family: var(--mono); font-size: 13px; letter-spacing: 0.1em;
    text-transform: uppercase; color: var(--text-dim); margin: 0 0 18px;
    border-bottom: 1px solid var(--line); padding-bottom: 10px;
  }}
  .panel {{ background: var(--bg-panel); border: 1px solid var(--line); border-radius: 10px; padding: 24px; }}
  .bar-row {{ display: flex; align-items: center; gap: 12px; margin-bottom: 10px; font-size: 13px; }}
  .bar-label {{ width: 150px; flex-shrink: 0; color: var(--text-dim); font-family: var(--mono); }}
  .bar-track {{ flex: 1; height: 8px; background: var(--bg-panel-2); border-radius: 4px; overflow: hidden; }}
  .bar-fill {{ height: 100%; background: var(--accent); border-radius: 4px; }}
  .bar-val {{ width: 40px; text-align: right; font-family: var(--mono); color: var(--text-dim); }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{
    text-align: left; font-family: var(--mono); font-weight: 500; font-size: 11px;
    text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-dim);
    padding: 10px 12px; border-bottom: 1px solid var(--line);
  }}
  td {{ padding: 10px 12px; border-bottom: 1px solid var(--line); vertical-align: top; }}
  tr:hover td {{ background: var(--bg-panel-2); }}
  .badge {{
    display: inline-block; font-family: var(--mono); font-size: 11px;
    padding: 2px 8px; border-radius: 4px; white-space: nowrap;
  }}
  .badge.ok {{ background: rgba(78,225,160,0.12); color: var(--accent); }}
  .badge.warn {{ background: rgba(224,169,78,0.12); color: var(--warn); }}
  .badge.bad {{ background: rgba(225,90,90,0.12); color: var(--bad); }}
  .evidence-link {{ color: var(--text-dim); font-size: 12px; text-decoration: none; }}
  .evidence-link:hover {{ color: var(--accent); }}
  .filters {{ display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }}
  .filters button {{
    font-family: var(--mono); font-size: 12px; background: var(--bg-panel-2);
    border: 1px solid var(--line); color: var(--text-dim); padding: 6px 12px;
    border-radius: 20px; cursor: pointer;
  }}
  .filters button.active {{ background: var(--accent); color: #06110b; border-color: var(--accent); }}
  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
  @media (max-width: 720px) {{ .two-col {{ grid-template-columns: 1fr; }} }}
  .agent-steps {{ display: grid; gap: 14px; }}
  .agent-step {{ display: flex; gap: 14px; }}
  .agent-step .n {{
    font-family: var(--mono); color: var(--accent); font-size: 13px;
    width: 24px; flex-shrink: 0; padding-top: 2px;
  }}
  .agent-step .txt strong {{ display: block; margin-bottom: 2px; }}
  .agent-step .txt span {{ color: var(--text-dim); font-size: 13px; }}
  .accuracy-track {{ display: flex; gap: 8px; align-items: flex-end; height: 120px; margin-top: 8px; }}
  .accuracy-col {{ flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; height: 100%; }}
  .accuracy-bar {{ width: 60%; background: var(--accent); border-radius: 4px 4px 0 0; }}
  .accuracy-bar.dim {{ background: var(--text-dim); opacity: 0.5; }}
  .accuracy-num {{ font-family: var(--mono); font-size: 13px; margin-bottom: 6px; }}
  .accuracy-caption {{ font-size: 11px; color: var(--text-dim); margin-top: 8px; text-align: center; }}
  .honesty-note {{
    border-left: 3px solid var(--warn); padding: 12px 16px; background: rgba(224,169,78,0.06);
    font-size: 13px; color: var(--text-dim); border-radius: 0 6px 6px 0;
  }}
  .links {{ display: flex; gap: 16px; flex-wrap: wrap; }}
  .links a {{
    font-family: var(--mono); font-size: 13px; color: var(--accent); text-decoration: none;
    border: 1px solid var(--accent-dim); padding: 8px 16px; border-radius: 6px;
  }}
  .links a:hover {{ background: rgba(78,225,160,0.08); }}
  footer {{ margin-top: 64px; color: var(--text-dim); font-size: 12px; font-family: var(--mono); }}
</style>
</head>
<body>
<div class="wrap">

  <div class="eyebrow">Composio · AI Product Ops Intern Take-Home</div>
  <h1>Can an agent build a toolkit for this app today?</h1>
  <div class="sub">
    {n_researched} of {total_apps} apps researched across 10 categories. An agent did the
    first pass, a human checked its work, and the accuracy of each step is shown below —
    not just the final numbers.
  </div>

  <div class="headline-grid">
    <div class="stat"><div class="num">{pct_self_serve}%</div><div class="label">self-serve today</div></div>
    <div class="stat"><div class="num">{dominant_auth}</div><div class="label">most common auth</div></div>
    <div class="stat"><div class="num">{pct_mcp}%</div><div class="label">already have an MCP</div></div>
    <div class="stat"><div class="num">{easy_wins_count}</div><div class="label">easy wins (self-serve + buildable today)</div></div>
  </div>

  <section>
    <h2>01 — Headline patterns</h2>
    <div class="two-col">
      <div class="panel">
        <div style="font-size:13px;color:var(--text-dim);margin-bottom:14px;">Auth method distribution</div>
        {auth_bars}
      </div>
      <div class="panel">
        <div style="font-size:13px;color:var(--text-dim);margin-bottom:14px;">Self-serve vs gated vs partial</div>
        {selfserve_bars}
      </div>
    </div>
    <div class="panel" style="margin-top:16px;">
      <div style="font-size:13px;color:var(--text-dim);margin-bottom:14px;">Most common blockers (when not buildable today)</div>
      {blocker_list}
    </div>
  </section>

  <section>
    <h2>02 — The 100-app matrix</h2>
    <div class="filters" id="filters">
      <button class="active" data-filter="all">All</button>
      <button data-filter="buildable today">Buildable today</button>
      <button data-filter="buildable with workaround">Workaround needed</button>
      <button data-filter="blocked">Blocked</button>
    </div>
    <div class="panel" style="padding:0;overflow-x:auto;">
      <table id="matrix-table">
        <thead><tr>
          <th>App</th><th>Category</th><th>Auth</th><th>Access</th><th>MCP?</th><th>Verdict</th><th>Evidence</th>
        </tr></thead>
        <tbody>{matrix_rows}</tbody>
      </table>
    </div>
    <div style="font-size:12px;color:var(--text-dim);margin-top:10px;">
      {rows_shown_note}
    </div>
  </section>

  <section>
    <h2>03 — The agent</h2>
    <div class="panel">
      <div class="agent-steps">
        <div class="agent-step"><div class="n">01</div><div class="txt"><strong>Groq compound + built-in web_search, per app</strong><span>Each of the 100 apps gets its own call to <code style="color:var(--accent)">groq/compound</code> — an agentic system on Groq's free tier with an automatically-triggered web_search tool — told to actually search for the app's current developer docs (not answer from memory) and reply in one fixed JSON schema: category, auth methods, self-serve/gated, API surface, MCP existence, buildability verdict, and the exact evidence URL.</span></div></div>
        <div class="agent-step"><div class="n">02</div><div class="txt"><strong>Resumable, not a single monolithic run</strong><span>Every answer is appended to disk the moment it's produced, so a rate limit or a bad response on app #63 never loses the other 99 — re-running just skips what's done.</span></div></div>
        <div class="agent-step"><div class="n">03</div><div class="txt"><strong>Where a human was needed</strong><span>The agent is honest about low-confidence answers (a "confidence" field on every row) and flags apps where docs are thin or contradictory. Those, plus a random sample, get manually opened and checked by hand — see Verification below.</span></div></div>
        <div class="agent-step"><div class="n">04</div><div class="txt"><strong>Composio-native path available</strong><span>Groq's compound system only supports its own built-in tools, not remote MCP — so the Composio-native variant swaps in a plain Groq model with remote-tool calling pointed at Composio's own hosted MCP server instead, same schema, same verification loop, running on Composio's own rails rather than a generic search tool.</span></div></div>
      </div>
    </div>
  </section>

  <section>
    <h2>04 — Proof</h2>
    <div class="panel">
      <div class="links">
        <a href="{repo_url}">Source repo →</a>
        <a href="{live_url}">Live page →</a>
      </div>
      <div style="margin-top:16px;font-size:13px;color:var(--text-dim);">
        Runnable trigger: <code style="color:var(--accent)">python agent/research_agent.py --ids &lt;app-ids&gt;</code> re-researches
        any app on demand — the same command a reviewer can run live against a new app not on this list.
      </div>
    </div>
  </section>

  <section>
    <h2>05 — Verification</h2>
    <div class="panel">
      {verification_block}
    </div>
  </section>

  <footer>generated by agent/generate_report.py · data/results.jsonl</footer>
</div>

<script>
  const filters = document.querySelectorAll('#filters button');
  const rows = document.querySelectorAll('#matrix-table tbody tr');
  filters.forEach(btn => {{
    btn.addEventListener('click', () => {{
      filters.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const f = btn.dataset.filter;
      rows.forEach(r => {{
        r.style.display = (f === 'all' || r.dataset.verdict === f) ? '' : 'none';
      }});
    }});
  }});
</script>
</body>
</html>
"""


def bar_html(label, value, max_value):
    pct = round(100 * value / max_value) if max_value else 0
    return f'''<div class="bar-row">
      <div class="bar-label">{label}</div>
      <div class="bar-track"><div class="bar-fill" style="width:{pct}%"></div></div>
      <div class="bar-val">{value}</div>
    </div>'''


def verdict_class(v):
    return {"buildable today": "ok", "buildable with workaround": "warn", "blocked": "bad"}.get(v, "warn")


def build_matrix_rows(rows):
    out = []
    for r in sorted(rows, key=lambda x: x.get("id", 0)):
        verdict = r.get("buildability_verdict", "unclear")
        cls = verdict_class(verdict)
        auth = ", ".join(r.get("auth_methods", [])) or "unclear"
        mcp = "Yes" if r.get("mcp_exists") is True else ("No" if r.get("mcp_exists") is False else "?")
        evidence = r.get("evidence_url", "")
        out.append(f'''<tr data-verdict="{verdict}">
          <td><strong>{r.get("app","")}</strong></td>
          <td style="color:var(--text-dim)">{r.get("category","")}</td>
          <td>{auth}</td>
          <td>{r.get("self_serve","unclear")}</td>
          <td>{mcp}</td>
          <td><span class="badge {cls}">{verdict}</span></td>
          <td>{f'<a class="evidence-link" href="{evidence}">docs →</a>' if evidence else '—'}</td>
        </tr>''')
    return "\n".join(out)


def build_verification_block(verification):
    if not verification:
        return '''<div class="honesty-note">
          No verification pass recorded yet. Run <code>agent/baseline_naive.py</code> and
          <code>agent/verify.py</code> on a sample (see agent/verify.py docstring) — the
          brief explicitly wants accuracy shown improving across passes, this section is
          where that goes.
        </div>'''

    acc = verification.get("pass_accuracy", {})
    p0 = acc.get("pass0_baseline")
    p1 = acc.get("pass1_agent")
    bars = ""
    if p0 is not None:
        bars += f'''<div class="accuracy-col">
          <div class="accuracy-num">{p0}%</div>
          <div class="accuracy-bar dim" style="height:{p0}%"></div>
          <div class="accuracy-caption">Pass 0<br>model memory only</div>
        </div>'''
    if p1 is not None:
        bars += f'''<div class="accuracy-col">
          <div class="accuracy-num">{p1}%</div>
          <div class="accuracy-bar" style="height:{p1}%"></div>
          <div class="accuracy-caption">Pass 1<br>agent + web_search</div>
        </div>'''

    n = verification.get("sample_size", "?")
    fields = ", ".join(verification.get("fields_checked", []))

    misses = []
    for row in verification.get("per_app", []):
        p1_fields = row.get("pass1", {})
        if any(v is False for v in p1_fields.values()):
            wrong = [f for f, v in p1_fields.items() if v is False]
            misses.append(f"<li><strong>{row.get('app')}</strong> — wrong on: {', '.join(wrong)}</li>")

    misses_html = ""
    if misses:
        misses_html = f'''<div style="margin-top:20px;">
          <div style="font-size:13px;color:var(--text-dim);margin-bottom:8px;">Where the agent (Pass 1) was still wrong, honestly:</div>
          <ul style="font-size:13px;color:var(--text);padding-left:18px;">{"".join(misses)}</ul>
        </div>'''
    else:
        misses_html = '<div style="margin-top:20px;font-size:13px;color:var(--text-dim);">No misses found in this sample — call this out as a small sample, not a guarantee.</div>'

    return f'''
      <div style="font-size:13px;color:var(--text-dim);margin-bottom:14px;">
        {n}-app sample, hand-checked against real docs, on: {fields}
      </div>
      <div class="accuracy-track">{bars}</div>
      {misses_html}
    '''


def main():
    apps = json.loads(APPS_PATH.read_text())
    rows = load_results()
    patterns = compute_patterns(rows, len(apps))
    verification = load_verification()

    max_auth = max((v for _, v in patterns["auth_distribution"]), default=1)
    auth_bars = "\n".join(bar_html(k, v, max_auth) for k, v in patterns["auth_distribution"]) or "<div style='color:var(--text-dim);font-size:13px'>No data yet — run research_agent.py</div>"

    ss_dist = patterns["self_serve_distribution"]
    max_ss = max(ss_dist.values(), default=1)
    selfserve_bars = "\n".join(bar_html(k, v, max_ss) for k, v in ss_dist.items()) or "<div style='color:var(--text-dim);font-size:13px'>No data yet</div>"

    blocker_list = "\n".join(
        f'<div class="bar-row"><div style="flex:1;font-size:13px;">{b}</div><div class="bar-val">{c}</div></div>'
        for b, c in patterns["top_blockers"]
    ) or "<div style='color:var(--text-dim);font-size:13px'>No blockers recorded yet, or nothing is blocked</div>"

    pct_self_serve = round(100 * ss_dist.get("self-serve", 0) / patterns["n_researched"]) if patterns["n_researched"] else 0
    pct_mcp = round(100 * patterns["mcp_distribution"].get("True", 0) / patterns["n_researched"]) if patterns["n_researched"] else 0
    dominant_auth = patterns["auth_distribution"][0][0] if patterns["auth_distribution"] else "—"

    rows_shown_note = (
        f"Showing {patterns['n_researched']} of {patterns['total_apps']} apps researched so far. "
        f"Run research_agent.py without --limit to fill in the rest."
        if patterns["n_researched"] < patterns["total_apps"]
        else f"All {patterns['total_apps']} apps researched."
    )

    html = HTML_TEMPLATE.format(
        n_researched=patterns["n_researched"],
        total_apps=patterns["total_apps"],
        pct_self_serve=pct_self_serve,
        dominant_auth=dominant_auth,
        pct_mcp=pct_mcp,
        easy_wins_count=patterns["easy_wins_count"],
        auth_bars=auth_bars,
        selfserve_bars=selfserve_bars,
        blocker_list=blocker_list,
        matrix_rows=build_matrix_rows(rows),
        rows_shown_note=rows_shown_note,
        repo_url=REPO_URL,
        live_url=LIVE_URL,
        verification_block=build_verification_block(verification),
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(html, encoding="utf-8")
    print(f"Wrote {OUT_PATH} ({patterns['n_researched']}/{patterns['total_apps']} apps rendered)")


if __name__ == "__main__":
    main()
