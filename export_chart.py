"""Inline persons + linked manuscripts into the chart page -> out/nepalese_scribes.html"""
import json, os, collections
HERE = os.path.dirname(os.path.abspath(__file__))
D = lambda f: json.load(open(os.path.join(HERE, 'data', f)))
M, P, R, E = D('manuscripts.json'), D('persons.json'), D('relations.json'), D('estimates.json')
used = sorted({i for p in P for i in p['ms']})
remap = {old: new for new, old in enumerate(used)}
mss = []
for i in used:
    m = M[i]
    d = m['date']
    mss.append([m['reel'], m['title'], m['date_raw'][:70], d['ce'] if d else None,
                ((d['era'] or '') + ('?' if d['inferred'] else '')) if d else '', m['place'] or m['place_raw'][:50],
                m['script'], m['subject'], m['colophon'][:600], m['reading'], m['date_src'],
                m['notes'][:400], m['review'][:6], m['purpose'][:120],
                (lambda e: [e['from'], e['to'], e['conf'], e['basis'][:5]] if e else None)(E.get(str(i)))])
ROLE = {'scribe': 's', 'patron': 'p', 'king': 'k', 'other': 'o', 'kin': 'r'}
persons = []
for p in P:
    att = [[remap[a['ms']], ' '.join(a['roles']), ', '.join(a['titles']), a['residence'][:80],
            a['evidence'][:200], a['conf'], a['src'][0]] for a in p['att']]
    # a person with no dated MS gets the overlap (or, failing that, the hull) of the estimates of their MSS
    ests = [E[str(i)] for i in p['ms'] if str(i) in E]
    est = None
    if not p['from'] and ests:
        lo, hi = max(e['from'] for e in ests), min(e['to'] for e in ests)
        if lo > hi:
            lo, hi = min(e['from'] for e in ests), max(e['to'] for e in ests)
        conf = 'high' if all(e['conf'] == 'high' for e in ests) else 'medium' if any(e['conf'] != 'low' for e in ests) else 'low'
        est = [lo, hi, conf]
    persons.append([ROLE[p['role']], p['name'], [remap[i] for i in p['ms']], p['from'], p['to'],
                    1 if p['homonym_split'] else 0, [v for v in p['variants'] if v != p['name']][:6],
                    p['titles'][:8], att, est])
rels = [[r['from'], r['type'], r['to'], remap[r['ms']]] for r in R]
hist = collections.Counter((m['date']['ce'] // 10 * 10, m['date']['era'] or 'other') for m in M if m['date'])
nread = collections.Counter(m['reading'] for m in M if m['reading'])
data = {'mss': mss, 'persons': persons, 'rels': rels, 'hist': [[d, e, n] for (d, e), n in sorted(hist.items())],
        'stats': {'files': 13382, 'reels': len(M), 'dated': sum(1 for m in M if m['date']),
                  'flash': nread['flash'] + nread['opus'], 'opus': nread['opus'], 'estimated': len(E),
                  'undated_named': sum(1 for m in M if not m['date'] and m['persons'])}}
tpl = open(os.path.join(HERE, 'chart_template.html')).read()
os.makedirs(os.path.join(HERE, 'out'), exist_ok=True)
out = os.path.join(HERE, 'out', 'nepalese_scribes.html')
open(out, 'w').write(tpl.replace('/*DATA*/null', json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', r'<\/')))
print(out, os.path.getsize(out) // 1024, 'KB')
