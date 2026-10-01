"""Select reels whose colophon may name people/dates -> extract/worklist.jsonl"""
import json, re, os, sys, collections
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from build_persons import reel_key, D

KW = re.compile(r'likh|lekh|lipi|coy[aā]|sa[mṃ]vat|sambat|sa[mṃ]\.?\s*\d|\bsa\s\d|śreyo|dāna|yajamān|pustak|'
                r'nepāla|rājye|bhūp|malla|kāyastha|ṭhakkur|vajrācār|daivajña|upādhyāy|śāke|varṣe', re.I)
byreel = collections.OrderedDict()
for l in open(D('records.jsonl')):
    r = json.loads(l)
    k = reel_key(r)
    old = byreel.get(k)
    if old is None or len(r.get('colophon') or '') > len(old.get('colophon') or ''):
        if old:  # keep catalogue fields filled in either file
            for f in ('Scribe', 'Date of Copying', 'Place of Copying', 'King', 'Donor'):
                r[f] = r.get(f) or old.get(f, '')
        byreel[k] = r
n = 0
with open(os.path.join(os.path.dirname(__file__), 'worklist.jsonl'), 'w') as o:
    for k, r in byreel.items():
        col = r.get('colophon') or ''
        if not col or not KW.search(col):
            continue
        fields = {f: r.get(f, '') for f in ('Scribe', 'Date of Copying', 'Place of Copying', 'King', 'Donor')}
        o.write(json.dumps({'reel': k, 'title': r.get('Title', ''), 'script': r.get('Script', ''),
                            'fields': fields, 'colophon': col[:5000]}, ensure_ascii=False) + '\n')
        n += 1
print(n, 'reels in worklist')
