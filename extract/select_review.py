"""Pick colophons whose Flash reading needs a second (Opus) reading -> extract/review_list.jsonl
Criteria: a person at low confidence; doubt expressed in notes; the catalogue's Scribe/King not found among
the extracted persons; or the extracted CE date differing from the catalogue date by more than 2 years."""
import json, os, re, sys, collections, difflib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
from build_persons import split_names, name_key, parse_date

FIRST = os.path.join(HERE, 'out_gflash')
DOUBT = re.compile(r'uncertain|unclear|corrupt|conflict|doubt|ambigu|illegib|cannot be|could not|not certain|'
                   r'unsure|unknown era|disagree|discrepan|inconsisten|possibly|perhaps', re.I)


def keys(o, roles):
    return {name_key(p['name'], 'king' if 'king' in roles else '') for p in o['persons'] if set(p['roles']) & roles}


def match(catname, ks, role=''):
    k = name_key(catname, role)
    return any(k[:6] == x[:6] or k in x or x in k or difflib.SequenceMatcher(None, k, x).ratio() >= .8
               for x in ks if x)


reasons, out = collections.Counter(), []
for l in open(os.path.join(HERE, 'worklist.jsonl')):
    r = json.loads(l)
    fid = r['reel'].replace(' ', '_').replace('/', '-')
    p = os.path.join(FIRST, fid + '.json')
    if not os.path.exists(p):
        continue
    o = json.load(open(p))
    why = []
    if any(x['confidence'] == 'low' for x in o['persons']):
        why.append('low_conf')
    if DOUBT.search(o.get('notes', '')):
        why.append('doubt_in_notes')
    f = r['fields']
    if any(not match(n, keys(o, {'scribe'})) for n in split_names(f['Scribe'])):
        why.append('scribe_mismatch')
    if any(not match(n, keys(o, {'king', 'queen'}), 'king') for n in split_names(f['King'])):
        why.append('king_mismatch')
    cd = parse_date(f['Date of Copying'], r['script'])
    m = re.match(r'\s*(\d{3,4})', o['date'].get('ce_approx') or '')
    if cd and m and abs(int(m.group(1)) - cd['ce']) > 2:
        why.append('date_mismatch')
    if why:
        reasons.update(why)
        r['review_reasons'] = why
        out.append(r)
with open(os.path.join(HERE, 'review_list.jsonl'), 'w') as o:
    o.writelines(json.dumps(r, ensure_ascii=False) + '\n' for r in out)
n = len(os.listdir(FIRST))
print(f'{len(out)} of {n} selected for review', dict(reasons))
