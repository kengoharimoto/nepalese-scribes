"""Parse NGMCP catalogue HTML entries into records.jsonl (one record per file)."""
import re, html, os, json, sys, unicodedata

SRC = '/mnt2/kengo/E-texts/NGMCP'
OUT = os.path.join(os.path.dirname(__file__), 'data', 'records.jsonl')

FIELDS = ['Inventory No.', 'Reel No.', 'Title', 'Remarks', 'Author', 'Commentator', 'Subject',
          'Language', 'Text Features', 'Reference', 'Acknowledgement', 'Script', 'Material',
          'State', 'Size', 'Binding Hole', 'Folios', 'Lines per Folio', 'Foliation',
          'Illustrations', 'Scribe', 'Date of Copying', 'Place of Copying', 'King', 'Donor',
          'Owner / Deliverer', 'Owner of MS', 'Place of Deposit', 'Place of Deposite',
          'Accession No.', 'Edited MS', 'Manuscript Features', 'Excerpts', 'Microfilm Details',
          'Date of Filming', 'Exposures', 'Used Copy', 'Type of Film', 'Remarks', 'Catalogued by',
          'Date', 'Slides', 'Used for Edition', 'MTM Inventory No.', 'Stamp']
def _lab(f):
    return r'\s+'.join(re.escape(w) for w in f.split())  # labels may wrap across lines


LAB = re.compile(r'(?:^|(?<=\s))(' + '|'.join(_lab(f) for f in sorted(set(FIELDS), key=len, reverse=True)) + r')[ \t]*:', re.M)


def clean(f):
    t = open(f, encoding='utf-8', errors='replace').read()
    t = re.sub(r'<script.*?</script>|<style.*?</style>', '', t, flags=re.S | re.I)
    t = re.sub(r'<br\s*/?>|</p>|</tr>|</div>', '\n', t, flags=re.I)
    t = re.sub(r'</t[dh]>', '\t', t, flags=re.I)
    t = html.unescape(re.sub(r'<[^>]+>', '', t))
    t = t.replace('ῑ', 'ī').replace('\xa0', ' ')  # Greek iota-macron used for ī
    return unicodedata.normalize('NFC', t)


def one_line(s):
    return re.sub(r'\s+', ' ', s).strip()


def parse(f):
    t = clean(os.path.join(SRC, f))
    rec = {'file': f}
    excerpt_start = None
    m = re.search(r'^\s*Excerpts\s*$', t, re.M)
    if m:
        excerpt_start = m.start()
    # labels are searched only in the header (before Excerpts) and in the microfilm block
    ms = [x for x in LAB.finditer(t) if excerpt_start is None or x.start() < excerpt_start
          or re.search(r'Microfilm Details', t[excerpt_start:x.start()])]
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(t)
        if excerpt_start and m.start() < excerpt_start < end:
            end = excerpt_start
        key = ' '.join(m.group(1).split())
        val = t[m.end():end]
        if key in rec and rec[key]:
            continue
        rec[key] = one_line(val) if key not in ('Manuscript Features',) else val.strip()
    if excerpt_start:
        mf = re.search(r'^\s*Microfilm Details', t[excerpt_start:], re.M)
        ex = t[excerpt_start: excerpt_start + mf.start() if mf else len(t)]
        rec['excerpts'] = ex
        # colophon block(s)
        cm = re.search(r'«\s*Colophons?\s*:?\s*»(.*?)(?=«|Microfilm\s+Details|Bibliography|Document created with|$)', ex, re.S | re.I)
        if cm:
            rec['colophon'] = one_line(cm.group(1))
    return rec


if __name__ == '__main__':
    files = sorted(f for f in os.listdir(SRC) if f.endswith('.html'))
    with open(OUT, 'w') as o:
        for f in files:
            o.write(json.dumps(parse(f), ensure_ascii=False) + '\n')
    print(len(files), 'records ->', OUT)
