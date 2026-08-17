import csv
from pathlib import Path
IN = Path('data/false_negative_offenders.csv')
OUT = Path('data/false_negative_summary.txt')
rows = []
with IN.open('r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for r in reader:
        rows.append(r)

counts = {}
for r in rows:
    c = (r.get('confidence') or '').strip().lower() or 'unknown'
    counts[c] = counts.get(c, 0) + 1

# sort by confidence then id
rows_sorted = sorted(rows, key=lambda r: (r.get('confidence') or '', int(r.get('id') or 0)))

lines = []
lines.append(f'Total offenders: {len(rows)}')
for k in sorted(counts.keys(), reverse=True):
    lines.append(f' - {k}: {counts[k]}')

lines.append('\nTop 12 offenders (id, app, confidence, evidence_url):')
for r in rows_sorted[:12]:
    lines.append(f"{r['id']}, {r['app']}, {r['confidence']}, {r['evidence_url']}")

OUT.write_text('\n'.join(lines), encoding='utf-8')
print(OUT)
