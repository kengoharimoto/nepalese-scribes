"""Parse Bendall's Cambridge catalogue (1883) from its Chandra OCR into entries.

C. Bendall, Catalogue of the Buddhist Sanskrit Manuscripts in the University Library, Cambridge
(Cambridge 1883; reprint Delhi 1992). OCR: data/bendall1883_ocr.md, made with chandra-ocr-2
(--paginate_output --no-images) from the 300 dpi scan 'Bendall 1992 cat of buddh ms AD-OCR.pdf'
in /qnap/kengo/dox/Books_and_Articles_on_iCloud (work files in /mnt2/kengo/ocr-bendall).
In that scan pp. 239-240 (Add. 1680 XVI-XXX) come before p. 241 (Add. 1680 I-XV), and p. 238 is
repeated as p. 241; repeated paragraphs are dropped and parts sorted. Run as a script for a summary.

An entry starts at a line holding only an «Add.» number ('### Add. 866.', 'Add. 1638. 3.',
'Add. 1446—47.') followed by the physical description ('Palm-leaf; 202 leaves, 6 lines, 21 × 2 in.;
early Devanāgarī hand ...; dated Nepal Saṃvat 128 (A.D. 1008).').
"""
import json, os, re, sys, unicodedata

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'bendall1883_ocr.md')
PAGE = re.compile(r'^(\d+)-{20,}\s*$', re.M)
HEAD = re.compile(r'^\s*(?:#+\s*)?\**\s*Add\.?\s*(\d{3,4})((?:\s*[.,]\s*\d{1,2}|\s*[—–-]\s*\d{1,4})?)\s*\.?\s*\**\s*$')
DESC = re.compile(r'^\s*(?:\*\*)?(Palm[- ]?leaf|Paper|Birch|Bhūrja|Board|Cloth|Wood|Copper|Black paper|Blue paper)', re.I)
DEV = re.compile(r'[ऀ-ॿ]')

FRAC = {'½': .5, '¼': .25, '¾': .75, '⅓': 1 / 3, '⅔': 2 / 3, '⅛': .125, '⅜': .375, '⅝': .625, '⅞': .875}


def nfc(s):
    return unicodedata.normalize('NFC', s)


def inches(s):
    """'14', '6½', '7\\frac{1}{2}', '12 3/4' -> float."""
    s = s.replace('$', '').strip()
    m = re.match(r'(\d+)\s*(?:\\frac\{(\d+)\}\{(\d+)\}|\s(\d)/(\d)|([½¼¾⅓⅔⅛⅜⅝⅞]))?', s)
    if not m:
        return None
    v = float(m.group(1))
    if m.group(2):
        v += int(m.group(2)) / int(m.group(3))
    elif m.group(4):
        v += int(m.group(4)) / int(m.group(5))
    elif m.group(6):
        v += FRAC[m.group(6)]
    return round(v, 3)


NUMIN = r'(\d+\s*(?:\\frac\{\d+\}\{\d+\}|[½¼¾⅓⅔⅛⅜⅝⅞]|\s\d/\d)?)'
ERAS = [('NS', r'N\.\s*[sS]\.|Nepal(?:a)?\s+Sa[mṃ]vat|Nepāla\s+Sa[mṃ]vat|Newār\s+era'),
        ('VS', r'V\.\s*[sS]\.|Vikram[aā](?:ditya)?\s+Sa[mṃ]vat|Saṃvat(?=\s+\d{4})'),
        ('ŚS', r'[ÇŚ]\.\s*[sS]\.|[ÇŚ]aka(?:\s+era)?'),
        ('LS', r'L\.\s*[sS]\.|Lakshma[nṇ]a\s+Sa[mṃ]vat|Lakṣmaṇa\s+Sa[mṃ]vat'),
        ('HS', r'[ÇŚṢS]r[iī]harsha\)?\s+[Ss]a[mṃ]vat|Harsha\s+(?:era|[Ss]a[mṃ]vat)')]
OFFSET = {'NS': 880, 'VS': -57, 'ŚS': 78, 'LS': 1119, 'HS': 606}
ROMAN = {'I': 1, 'V': 5, 'X': 10}


def roman(s):
    s = s.upper()
    t = 0
    for i, c in enumerate(s):
        v = ROMAN.get(c, 0)
        t += -v if i + 1 < len(s) and ROMAN.get(s[i + 1], 0) > v else v
    return t


def parse_desc(d):
    o = {'material': None, 'leaves': None, 'lines_min': None, 'lines_max': None, 'width_in': None, 'height_in': None,
         'hand': None, 'era': None, 'era_year': None, 'year_ce': None, 'century': None, 'date_text': None}
    m = DESC.match(d)
    if m:
        mat = m.group(1).lower().replace(' ', '-')
        o['material'] = 'palm-leaf' if mat.startswith('palm') else 'birch-bark' if mat.startswith(('birch', 'bhūrja')) else \
            mat.replace('-', ' ')
    m = re.search(r'(\d+)\s+(?:remaining\s+|unnumbered\s+|large\s+)?(?:leaves|leaf|sheets?)\b', d)
    o['leaves'] = int(m.group(1)) if m else None
    m = re.search(r'(\d+)\s*(?:[—–-]\s*(\d+)|,\s*(\d+))?\s+lines', d)
    if m:
        o['lines_min'] = int(m.group(1))
        o['lines_max'] = int(m.group(2) or m.group(3) or m.group(1))
    m = re.search(r'\$?\s*' + NUMIN + r'\s*\$?\s*(?:×|x|\\times)\s*\$?\s*' + NUMIN + r'\s*\$?\s*in', d)
    if m:
        o['width_in'], o['height_in'] = inches(m.group(1)), inches(m.group(2))
    parts = [p.strip() for p in re.split(r';', d)]
    rest = [p for p in parts[1:] if not re.search(r'leaves|lines|\bin\.', p)]
    hand = [p for p in rest if not re.match(r'(dated|written|circa|c\.)', p, re.I)]
    o['hand'] = '; '.join(hand).rstrip('.') or None
    dm = re.search(r'((?:apparently\s+|probably\s+)?(?:dated|(?:written|copied)\s+(?:in\s+)?(?:A\.\s*D\.\s*)?\d)\b.*)$', d, re.I | re.S)
    o['date_text'] = dm.group(1).strip().rstrip('.') if dm else None
    for era, pat in ERAS:
        m = re.search(r'(?:' + pat + r')\s*(\d{2,4})', d)
        if m:
            o['era'], o['era_year'] = era, int(m.group(1))
            o['year_ce'] = o['era_year'] + OFFSET[era]
            break
    m = re.search(r'A\.\s*D\.\s*(\d{3,4})', d)
    if m:
        o['year_ce'] = int(m.group(1))  # Bendall's own conversion wins
    elif not o['era']:
        m = re.search(r'(?:written|copied|dated)\s+(?:in\s+)?(1[0-9]{3})\b', d)
        if m:
            o['year_ce'], o['era'], o['era_year'] = int(m.group(1)), 'CE', int(m.group(1))
    m = re.search(r'\b([XVI]{1,5})(?:th|st|nd|rd)?\.?\s*(?:[—–-]\s*([XVI]{1,5})(?:th|st|nd|rd)?\.?)?\s*cent', d, re.I)
    if m:
        o['century'] = roman(m.group(2) or m.group(1))
    elif o['year_ce']:
        o['century'] = (o['year_ce'] - 1) // 100 + 1
    if o['hand'] and re.search(r'\bmodern\b', o['hand'], re.I) and not o['century']:
        o['century'] = 19
    return o


def is_dev(p):
    letters = [c for c in p if c.isalpha()]
    return letters and sum(1 for c in letters if DEV.match(c)) / len(letters) > .5


def excerpt_kind(label):
    l = label.lower()
    for k, pat in (('colophon', r'colophon|subscription|particulars|date|scribe|written'), ('ends', r'\bends?\b|conclu'),
                   ('begins', r'begin|commenc|opening')):
        if re.search(pat, l):
            return k
    return 'other'


PART = re.compile(r'^(?:#+\s*)?\**([IVX]{1,6})\.?(?:\s*(?:[—–,-]|\.?\s*and)\s*([IVX]{1,6})\.)?(?<=\.)\s*(.*)$', re.S)
DESCRIPTIVE = re.compile(r'\b(?:leaf|leaves|lines|cent\.?|century|dated|\d+\s*(?:×|x|\\times).*?in\.?)\b|×', re.I)


def material_of(d):
    m = re.search(r'palm|birch|bhūrja|paper', d[:80], re.I)
    if not m:
        return None
    w = m.group().lower()
    return 'palm-leaf' if w == 'palm' else 'birch-bark' if w in ('birch', 'bhūrja') else \
        'black paper' if re.search(r'black\s+paper', d[:80], re.I) else 'paper'


def titles_in(paras):
    out = []
    for p in paras:
        t = re.sub(r'^#+\s*|\*', '', p).strip().rstrip('.')
        if p.startswith('#') or (len(t) < 120 and re.search(r'[A-ZĀĪŪṚṢŚÇṆṬḌ]{4,}', t) and not is_dev(t)):
            out.append(t)
        else:
            break
    return out


def excerpts_of(paras, part=None):
    out, label = [], ''
    for p in paras:
        if is_dev(p):
            out.append({'part': part, 'label': label, 'kind': excerpt_kind(label), 'text': re.sub(r'\s*\n\s*', ' ', p)})
        else:
            label = re.sub(r'\s+', ' ', p)[-200:]
    return out


def describe(d):
    o = parse_desc(d)
    o['material'] = o['material'] or material_of(d)
    return o


def parse(path=SRC):
    text = nfc(open(path, encoding='utf-8').read())
    end = re.search(r'^#+\s*INDEX\s+I\b', text, re.M)
    text = text[:end.start()] if end else text
    lines = text.split('\n')
    page, pages = 1, []
    for ln in lines:
        m = PAGE.match(ln)
        if m:
            page = int(m.group(1)) + 1  # the marker closes page n (0-based in chandra) -> next page
        pages.append(page)
    heads = [(i, m) for i, ln in enumerate(lines) for m in [HEAD.match(ln)] if m]
    first = next(k for k, (i, m) in enumerate(heads)
                 if [l for l in lines[i + 1:i + 6] if l.strip() and not PAGE.match(l)][:1]
                 and DESC.match([l for l in lines[i + 1:i + 6] if l.strip() and not PAGE.match(l)][0]))
    heads = heads[first:]  # the introductions cite MSS on lines of their own too
    blocks = {}
    for k, (i, m) in enumerate(heads):
        j = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
        sub = re.sub(r'\s', '', m.group(2) or '').lstrip('.,')
        no = m.group(1) + ('.' + sub if sub and not sub.startswith(('—', '–', '-')) else sub.replace('–', '—'))
        body = '\n'.join(l for l in lines[i + 1:j] if not PAGE.match(l)).strip()
        body = re.sub(r'\n-{3,}\n.*?(?=\n\n|\Z)', '\n', body, flags=re.S)  # footnotes after '---'
        paras = [p.strip() for p in re.split(r'\n\s*\n', body) if p.strip()]
        if no in blocks:  # a page scanned twice / out of order (Add. 1680): keep paragraphs not seen yet
            seen = set(blocks[no]['paras'])
            blocks[no]['paras'] += [p for p in paras if p not in seen]
            blocks[no]['repeated'] = 1
        else:
            blocks[no] = {'add_num': int(m.group(1)), 'pdf_page': pages[i], 'paras': paras, 'repeated': 0}
    entries = []
    for no, b in blocks.items():
        paras = b['paras']
        desc = re.sub(r'\s+', ' ', paras[0]) if paras else ''
        e = {'add_no': no, 'add_num': b['add_num'], 'pdf_page': b['pdf_page'], 'description': desc,
             'pages_out_of_order': b['repeated']}
        e.update(describe(desc) if not PART.match(desc) else describe(''))
        # numbered parts (composite entries: Add. 1680 I-XXX, 1699 I-IV ...)
        idx = [k for k, p in enumerate(paras) if PART.match(p)]
        parts = []
        composite = not DESC.match(desc)  # no physical description of its own: a bundle of parts
        if composite and any(roman(PART.match(paras[k]).group(1)) == 1 for k in idx):
            for n, k in enumerate(idx):
                stop = idx[n + 1] if n + 1 < len(idx) else len(paras)
                pm = PART.match(paras[k])
                rest = re.sub(r'\s+', ' ', pm.group(3)).strip()
                seg = ([rest] if rest else []) + paras[k + 1:stop]
                pdesc = next((x for x in seg[:2] if DESCRIPTIVE.search(x) and not x.startswith('#')), '')
                ptitles = titles_in([x for x in seg if x != pdesc][:3])
                pt = {'part': roman(pm.group(1)), 'part_to': roman(pm.group(2)) if pm.group(2) else None,
                      'description': re.sub(r'\s+', ' ', pdesc) or None,
                      'title': re.sub(r'\s+', ' ', ' | '.join(ptitles)) or None,
                      'text': '\n\n'.join(seg)}
                pt.update(describe(pdesc))
                pt['material'] = pt['material'] or material_of(desc)  # 'a mass of palm-leaves ...'
                pt['excerpts'] = excerpts_of(seg, pt['part'])
                parts.append(pt)
            parts.sort(key=lambda x: x['part'])
            dedup = {}
            for pt in parts:  # a part heading repeated across the reordered pages
                if pt['part'] not in dedup or len(pt['text']) > len(dedup[pt['part']]['text']):
                    dedup[pt['part']] = pt
            parts = list(dedup.values())
        e['parts'] = parts
        if parts:
            e['title'] = ' | '.join(p['title'] for p in parts if p['title']) or None
            e['excerpts'] = [x for p in parts for x in p['excerpts']]
            if not e['year_ce']:
                ys = [p['year_ce'] for p in parts if p['year_ce']]
                e['year_ce'] = min(ys) if ys else None
        else:
            e['title'] = re.sub(r'\s+', ' ', ' | '.join(titles_in(paras[1:4]))) or None
            e['excerpts'] = excerpts_of(paras[1:])
        e['text'] = '\n\n'.join(paras)
        entries.append(e)
    return entries


if __name__ == '__main__':
    es = parse()
    print(len(es), 'entries,', sum(len(e['parts']) for e in es), 'parts;', sum(1 for e in es if e['year_ce']), 'dated;', sum(1 for e in es if e['title']), 'titled')
    if len(sys.argv) > 1:
        json.dump(es, open(sys.argv[1], 'w'), ensure_ascii=False, indent=1)
