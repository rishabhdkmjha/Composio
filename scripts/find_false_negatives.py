import json
from pathlib import Path
import csv

RESULTS = Path('data/results.jsonl')
OUT = Path('data/false_negative_offenders.csv')

def looks_like_docs(url):
    docs_indicators = ['docs.', '/docs', 'developer', 'api', 'developers', 'developer.', 'api-reference', 'rest', 'openapi', 'readme']
    if not url:
        return False
    url = url.lower()
    return any(ind in url for ind in docs_indicators)

rows = []
with RESULTS.open('r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        auth = obj.get('auth_methods')
        snippets = obj.get('_snippets_used') or []
        evidence = obj.get('evidence_url') or ''
        if isinstance(auth, list):
            unclear = any((str(a).lower() == 'unclear' or 'unclear' in str(a).lower()) for a in auth)
        else:
            unclear = str(auth).lower() == 'unclear'
        # docs present in snippets or evidence_url
        docs_found = any(looks_like_docs(s) for s in snippets) or looks_like_docs(evidence)
        if unclear and docs_found:
            rows.append({
                'id': obj.get('id'),
                'app': obj.get('app'),
                'auth_methods': json.dumps(obj.get('auth_methods')),
                'evidence_url': evidence,
                'snippets': json.dumps(snippets),
                'confidence': obj.get('confidence')
            })

OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open('w', newline='', encoding='utf-8') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=['id','app','auth_methods','evidence_url','snippets','confidence'])
    writer.writeheader()
    for r in rows:
        writer.writerow(r)

print(f'Wrote {len(rows)} offenders to {OUT}')
