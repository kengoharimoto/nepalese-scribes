"""Licchavi inscriptions -> extract/worklist_licchavi.jsonl, one record per inscription.

Source: /mnt2/kengo/E-texts/1_sanskr/7_inscriptions/licchavi/content*.txt, one inscription per file (198;
content0.txt is the index page). Each entry: a header 'No. 35. Kathmandu, Hāṃḍigāuṃ ...' (the edition's own
number), an English description, a concordance (Gn. = Gnoli, DV = D. Vajracarya, HJ, R. = Regmi), TEXT and
NOTES. The king-named files and subfolders of the same directory repeat these entries and are not used.
"""
import glob, json, os, re

SRC = '/mnt2/kengo/E-texts/1_sanskr/7_inscriptions/licchavi'
HERE = os.path.dirname(os.path.abspath(__file__))
HEAD = re.compile(r'^\s*(?:No\.\s*)?(\d{1,3})(?:\(\d+\))?\.?\s+(.*)$')


def label(n):
    return f'Licchavi inscr. {n}'


def concordance(text):
    out = {}
    for key, pat in (('Gn', r'\bGn\.?\s*([IVXLC\d]+[a-z]?)'), ('DV', r'\bDV\.?\s*(\d+[a-z]?)'),
                     ('HJ', r'\bHJ\.?\s*([IVXL\d]+)'), ('R', r'\bR\.\s*(\d+)')):
        m = re.search(pat, text[:3000])
        if m:
            out[key] = m.group(1)
    return out


def entries():
    out = {}
    for f in glob.glob(os.path.join(SRC, 'content*.txt')):
        t = open(f, encoding='utf-8-sig', errors='replace').read().replace('\r', '')
        lines = [l for l in t.split('\n') if l.strip()]
        m = HEAD.match(lines[0]) if lines else None
        if not m:
            continue  # the index page (content0.txt)
        n = int(m.group(1))
        head = re.sub(r'\s+', ' ', m.group(2)).strip(' .')
        if n in out and len(out[n]['text']) >= len(t):
            continue
        sm = re.search(r'Saṃvat\s*\[?(\d[\d\]\[]*)', head)
        out[n] = {'no': n, 'file': os.path.basename(f), 'head': head, 'text': t.strip(),
                  'samvat': re.sub(r'[\[\]]', '', sm.group(1)) if sm else '', 'conc': concordance(t)}
    return [out[k] for k in sorted(out)]


def clip(t, n=14000):
    return t if len(t) <= n else t[:9000] + '\n[...]\n' + t[-(n - 9000):]


if __name__ == '__main__':
    es = entries()
    with open(os.path.join(HERE, 'worklist_licchavi.jsonl'), 'w') as o:
        for e in es:
            o.write(json.dumps({'reel': label(e['no']), 'title': e['head'], 'script': '',
                                'fields': {'Date of Copying': ('saṃvat ' + e['samvat']) if e['samvat'] else ''},
                                'colophon': clip(e['text']), 'ce': None}, ensure_ascii=False) + '\n')
    print(len(es), 'inscriptions;', sum(1 for e in es if e['samvat']), 'with a saṃvat in the header;',
          'missing numbers:', [i for i in range(1, max(e['no'] for e in es) + 1) if i not in {e['no'] for e in es}])
