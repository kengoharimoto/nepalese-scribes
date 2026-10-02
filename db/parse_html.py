"""Parse the NGMCP catalogue HTML entries into raw fields and excerpt sections.

Each entry follows the catalogue template: a header (inventory, reel, title, ...), «Manuscript Details»,
«Excerpts» (with «Beginning:», «End:», «Colophon:» ... subsections), «Microfilm Details», then
«Catalogued by», «Date» and «Bibliography». Labels are matched through ALIASES (typos, line breaks
inside labels, missing colons); values are kept verbatim apart from whitespace.
"""
import html, os, re, unicodedata

SRC = '/mnt2/kengo/E-texts/NGMCP'

# canonical field -> label spellings found in the files
ALIASES = {
    'inventory_no': ['Inventory No.', 'Inventory No', 'Inv. No.'],
    'mtm_inventory_no': ['MTM Inventory No.', 'MTMInventory No.', 'MTM Inventory No'],
    'mtm_title': ['MTM titles', 'MTM title', 'MTM Title', 'MTM Detail'],
    'reel_no': ['Reel No.', 'Reel No', 'Reel no.'],
    'title': ['Title'],
    'alt_title': ['Alternative Title', 'Sanskritised title', 'Sanskritised Title'],
    'remarks': ['Remarks', 'Remark'],
    'author': ['Author'],
    'commentator': ['Commentator'],
    'subject': ['Subject'],
    'language': ['Language', 'Lunguage'],
    'text_features': ['Text Features'],
    'reference': ['Reference', 'References'],
    'acknowledgement': ['Acknowledgement', 'Acknowledgements'],
    'script': ['Script'],
    'material': ['Material'],
    'state': ['State'],
    'size': ['Size'],
    'binding_hole': ['Binding Hole', 'Binding Holes'],
    'folios': ['Folios', 'Pages'],
    'lines_per_folio': ['Lines per Folio', 'Lines per folio', 'Lines per Folio/Page', 'Lines per Page'],
    'foliation': ['Foliation', 'Pagination'],
    'marginal_title': ['Marginal Title', 'Marginal title'],
    'illustrations': ['Illustrations', 'Illustration'],
    'scribe': ['Scribe'],
    'date_of_copying': ['Date of Copying'],
    'place_of_copying': ['Place of Copying'],
    'king': ['King'],
    'donor': ['Donor'],
    'owner_deliverer': ['Owner / Deliverer', 'Owner/Deliverer', 'Owner / deliverer'],
    'owner_of_ms': ['Owner of MS'],
    'place_of_deposit': ['Place of Deposit', 'Place of Deposite'],
    'accession_no': ['Accession No.', 'Accession No'],
    'edited_ms': ['Edited MS'],
    'used_for_edition': ['Used for Edition', 'Use for Edition', 'Used for Edited', 'Used For Edition',
                         'Used for edition', 'USed for Edition', 'Uses of MS'],
    'manuscript_features': ['Manuscript Features', 'Manuscript Feature'],
    'stamp': ['Stamp'],
    'date_of_filming': ['Date of Filming'],
    'exposures': ['Exposures'],
    'slides': ['Slides'],
    'used_copy': ['Used Copy', 'Copy Used'],
    'type_of_film': ['Type of Film'],
}
LABEL = {}
for k, vs in ALIASES.items():
    for v in vs:
        LABEL[' '.join(v.lower().split())] = k


def _pat(v):
    return r'\s*'.join(re.escape(w) for w in v.split()) if v.endswith('.') else \
        r'\s+'.join(re.escape(w) for w in v.split())


_ALL = '|'.join(_pat(v) for v in sorted({v for vs in ALIASES.values() for v in vs}, key=len, reverse=True))
# a label starts a line (or follows a tab) and is followed by a colon or a tab; a label run on after a
# number ('8Lines per Folio: 12Foliation: ...') needs the colon
LAB = re.compile(r'(?:(?:^|(?<=\t))[ \t]*(' + _ALL + r')[ \t]*(?::|\t|(?=\n))'
                 r'|(?<=\d)(' + _ALL + r')[ \t]*:)', re.M)

SECTIONS = [  # (name, regexp of the heading line)
    ('ms', r'^\s*Manuscript\s+Details\s*$'),
    ('excerpts', r'^\s*Excerpts\s*:?\s*$'),
    ('microfilm', r'^\s*Microfilm\s+Details\s*$'),
    ('catalogued', r'^\s*Catalogued\s+by\b'),
    ('bibliography', r'^\s*Bibliogra\w*'),
]


def clean(path):
    t = open(path, encoding='utf-8', errors='replace').read()
    t = re.sub(r'<!--.*?-->|<script.*?</script>|<style.*?</style>|<title>.*?</title>', '', t, flags=re.S | re.I)
    t = re.sub(r'<br\s*/?>|</p>|</tr>|</div>|</h\d>|</li>', '\n', t, flags=re.I)
    t = re.sub(r'</t[dh]>', '\t', t, flags=re.I)
    t = html.unescape(re.sub(r'<[^>]+>', '', t))
    t = t.replace('ῑ', 'ī').replace('\xa0', ' ').replace('\r', '')
    t = re.sub(r'Document created with wvWare.*', '', t)
    # headings run into the previous field ('no/yes Manuscript FeaturesExcerpts «Beginning:» ...')
    t = re.sub(r'(?<=\S)[ \t]*(Manuscript\s+Features?\b|Excerpts(?=\s*«)|Microfilm\s+Details\b)', r'\n\1', t)
    t = re.sub(r'(Manuscript\s+Features?)[ \t]*(Excerpts)', r'\1\n\2', t)
    t = re.sub(r'^(Excerpts)[ \t]*(?=«)', r'\1\n', t, flags=re.M)
    return unicodedata.normalize('NFC', t)


def ws(s):
    return re.sub(r'\s+', ' ', s or '').strip()


def split_sections(t):
    """Cut the text at the section headings; a heading that is missing leaves its text in the previous part."""
    cuts = [(0, 'header')]
    pos = 0
    for name, pat in SECTIONS:
        m = re.compile(pat, re.M | re.I).search(t, pos)
        if m:
            cuts.append((m.start(), name))
            pos = m.end()
    out = {}
    for i, (start, name) in enumerate(cuts):
        end = cuts[i + 1][0] if i + 1 < len(cuts) else len(t)
        out[name] = t[start:end]
    return out


MICROFILM = {'reel_no', 'date_of_filming', 'exposures', 'slides', 'used_copy', 'type_of_film', 'remarks'}


def fields(block, section):
    """Label -> value. «Manuscript Features» is free text and comes last in its section: inside it only
    «Stamp» and a microfilm block (when its heading is missing) are taken as labels."""
    out = {}
    ms, mode = [], section
    for m in LAB.finditer(block):
        key = LABEL[' '.join((m.group(1) or m.group(2)).lower().split())]
        if mode == 'features':
            if key == 'reel_no':
                mode = 'microfilm'
            elif key != 'stamp':
                continue
        elif mode == 'microfilm' and key not in MICROFILM:
            continue
        elif key == 'manuscript_features':
            mode = 'features'
        if mode == 'microfilm' and key in ('reel_no', 'remarks'):
            key = 'mf_' + key
        ms.append((m, key))
    for i, (m, key) in enumerate(ms):
        end = ms[i + 1][0].start() if i + 1 < len(ms) else len(block)
        val = block[m.end():end]
        val = val.strip() if key == 'manuscript_features' else ws(val)
        if not out.get(key):  # a repeated label keeps the first non-empty value
            out[key] = val
    return out


EXC_HEAD = re.compile(r'«\s*([^»]{0,80}?)\s*»')


def excerpt_kind(label):
    l = label.lower().replace('–', '-')
    l = re.sub(r'sub\s*[-:]?\s*', 'sub-', l)
    if 'sub-colophon' in l or 'subcolophon' in l:
        return 'sub-colophon'
    if 'colophon' in l:
        return 'colophon'
    if l.startswith('beginning') or 'beginning' in l:
        return 'beginning'
    if l.startswith('end') or 'end of' in l:
        return 'end'
    if 'transcript' in l or 'full text' in l or l.startswith('text'):
        return 'transcript'
    return 'other'


def excerpts(block):
    block = re.sub(r'^\s*Excerpts\s*:?\s*', '', block, flags=re.I)
    ms = list(EXC_HEAD.finditer(block))
    out = []
    lead = ws(block[:ms[0].start()] if ms else block)
    if lead:
        out.append({'label': '', 'kind': 'other', 'text': lead})
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(block)
        text = ws(block[m.end():end])
        label = ws(m.group(1)).rstrip(':').strip()
        out.append({'label': label, 'kind': excerpt_kind(label), 'text': text})
    return out


def parse(fname, src=SRC):
    t = clean(os.path.join(src, fname))
    sec = split_sections(t)
    rec = {'file': fname}
    for name in ('header', 'ms', 'microfilm'):
        for k, v in fields(sec.get(name, ''), name).items():
            if k not in rec or not rec[k]:
                rec[k] = v
    # labels that slipped into the excerpts block when a heading is missing
    if 'microfilm' not in sec and 'excerpts' in sec:
        m = re.search(r'^\s*Reel\s+No\.?\s*:', sec['excerpts'], re.M)
        if m:
            for k, v in fields(sec['excerpts'][m.start():], 'microfilm').items():
                rec.setdefault(k, v)
            sec['excerpts'] = sec['excerpts'][:m.start()]
    cat = sec.get('catalogued', '')
    m = re.match(r'\s*Catalogued\s+by\s*:?\s*(.*?)\s*(?:\n|\t|Date\b|$)', cat, re.S | re.I)
    rec['catalogued_by'] = ws(m.group(1)) if m else ''
    m = re.search(r'Date\s*:?\s*(.*)', cat, re.S)
    rest = ws(m.group(1)) if m else ''
    m = re.match(r'((?:[A-Za-z]+\s+)?[\d?]{1,4}(?:\s*[-–./]\s*[\d?]{1,4}){0,2})\s*(.*)', rest)
    rec['catalogue_date'], rec['catalogue_note'] = (m.group(1), m.group(2)) if m else ('', rest)
    bib = re.sub(r'^\s*Bibliogra\w*\s*:?', '', sec.get('bibliography', ''), flags=re.I)
    rec['bibliography'] = ws(bib)
    rec['excerpts'] = excerpts(sec.get('excerpts', ''))
    rec['sections_found'] = ','.join(k for k in sec if k != 'header')
    return rec


if __name__ == '__main__':
    import sys, json
    for f in sys.argv[1:]:
        print(json.dumps(parse(f), ensure_ascii=False, indent=1))
