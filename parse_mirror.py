"""Parse the NGMCP wiki mirror (github.com/INDOLOGY/NGMCP-Descriptive-Catalogue, docs/*.html) into
data/records_mirror.jsonl, keeping only the reels that have no card in the local copy (data/records.jsonl).

The mirror pages are MediaWiki HTML: fields are '<b>Label</b> value', the excerpt parts are <h3> headings
(Beginning, End, Colophon, ...). They are rewritten into the 'Label:' / '«Colophon:»' layout of the local cards
and then parsed with parse_ngmcp.parse_text. Every colophon block (Colophon, Colophons, Colophon of the
commentary, ...; not sub-colophons) is kept, joined with ' || '.
Clone the mirror first:  git clone --depth 1 https://github.com/INDOLOGY/NGMCP-Descriptive-Catalogue.git \\
    /mnt2/kengo/E-texts/reference/ngmcp-mirror-src/repo
"""
import collections, difflib, html, json, os, re, unicodedata
import parse_ngmcp as P
from build_persons import reel_key

SRC = '/mnt2/kengo/E-texts/reference/ngmcp-mirror-src/repo/docs'
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'data', 'records_mirror.jsonl')
LABEL_FIX = {'Owner/Deliverer': 'Owner / Deliverer', 'Binding Hole(s)': 'Binding Hole',
             'Lines per Page': 'Lines per Folio', 'Used for edition': 'Used for Edition'}
COLO = re.compile(r'colophons?\b(?!.*sub)', re.I)


def to_card(raw):
    t = re.sub(r'<script.*?</script>|<style.*?</style>', '', raw, flags=re.S | re.I)
    i = t.find('<b>Reel No.</b>')  # drop the 'Manuscript culture infobox' before the first Reel No.
    if i > 0:
        t = t[i:]

    def heading(m):
        name = ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', m.group(2))).split())
        if m.group(1) == '2':
            if name.startswith('Manuscript Features'):
                return '\nManuscript Features:\n'
            if name.startswith(('Excerpts', 'Microfilm Details')):
                return f'\n{name}\n'
            return '\n'
        return f'\n«{name}:»\n'
    t = re.split(r'Retrieved from\s*"|<div class="printfooter"', t)[0]  # wiki footer: link and categories
    t = re.sub(r'<h([234])[^>]*>(.*?)</h\1>', heading, t, flags=re.S | re.I)
    t = re.sub(r'<b>\s*«\s*([^»<]*?)\s*:?\s*»\s*</b>', lambda m: f'\n«{m.group(1)}:»\n', t)

    def label(m):
        lab = ' '.join(m.group(1).split()).rstrip(':').strip()
        return f'\n{LABEL_FIX.get(lab, lab)}:'
    t = re.sub(r'<b>([^<]{1,40})</b>', label, t)
    t = re.sub(r'<br\s*/?>|</p>|</tr>|</div>|</blockquote>|</li>', '\n', t, flags=re.I)
    t = html.unescape(re.sub(r'<[^>]+>', '', t)).replace('ῑ', 'ī').replace('\xa0', ' ')
    return unicodedata.normalize('NFC', t)


def colophons(card):
    m = re.search(r'^\s*Excerpts\s*$', card, re.M)
    if not m:
        return ''
    ex = card[m.start():]
    mf = re.search(r'^\s*Microfilm Details', ex, re.M)
    ex = ex[:mf.start()] if mf else ex
    parts = re.split(r'«([^»]*)»', ex)
    blocks = [P.one_line(parts[i + 1]) for i in range(1, len(parts) - 1, 2) if COLO.search(parts[i])]
    return ' || '.join(b for b in blocks if b)


def mirror_key(rec, fname):
    """'A 1000-22 to A 1001-1' -> 'A 1000/22'; 'E 1774-3(30) Title.html' -> 'E 1774/3 (30)' (item of a bundle)."""
    s = re.split(r'=|\bto\b', rec.get('Reel No.') or '')[0]
    m = re.search(r'([A-Z]{1,2})\s*(\d+)\s*[/-]\s*(\d+)([a-z]?)(?![A-Za-z])', s) or \
        re.search(r'([A-Z]{1,2})\s*(\d+)\s*-\s*(\d+)([a-z]?)(?![A-Za-z])', fname)
    if not m:
        return 'mirror/' + fname
    k = f'{m.group(1)} {int(m.group(2))}/{int(m.group(3))}{m.group(4)}'
    item = re.match(r'[^(]*?\d\s*\((\d+)\)', fname)
    return k + (f' ({item.group(1)})' if item else '')


def fold(t):
    t = unicodedata.normalize('NFD', t or '').lower()
    return re.sub(r'[^a-z]', '', t)


def main():
    L = [json.loads(l) for l in open(os.path.join(HERE, 'data', 'records.jsonl'))]
    local = {reel_key(r) for r in L}
    by_inv = collections.defaultdict(list)
    for r in L:
        i = (r.get('Inventory No.') or '').strip(' :.')
        if re.fullmatch(r'\d+', i):
            by_inv[i].append(fold(r.get('Title')))
    n = kept = dup = 0
    seen = set()
    with open(OUT, 'w') as o:
        for f in sorted(os.listdir(SRC)):
            if not f.endswith('.html'):
                continue
            n += 1
            card = to_card(open(os.path.join(SRC, f), encoding='utf-8', errors='replace').read())
            rec = P.parse_text(card, 'mirror/' + unicodedata.normalize('NFC', f))
            rec['colophon'] = colophons(card)
            k = rec['_reel'] = mirror_key(rec, unicodedata.normalize('NFC', f))
            inv = (rec.get('Inventory No.') or '').strip(' :.')
            if k in local or k.split(' (')[0] in local or (len(by_inv.get(inv, [])) <= 3 and any(
                    difflib.SequenceMatcher(None, fold(rec.get('Title')), t).ratio() >= .7 for t in by_inv.get(inv, []))):
                dup += 1
                continue
            if k.startswith('mirror/'):  # index pages and two undated entries without a reel number
                continue
            seen.add(k)
            rec['_source_copy'] = 'NGMCP wiki mirror'
            o.write(json.dumps(rec, ensure_ascii=False) + '\n')
            kept += 1
    print(f'{n} mirror pages; {dup} already in the local copy; {kept} pages ({len(seen)} keys) added -> {OUT}')


if __name__ == '__main__':
    main()
