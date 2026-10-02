"""Normalise the raw catalogue fields (parse_html.py) into typed values and controlled vocabularies.

Every function takes the raw string and returns a dict of normalised columns; anything that cannot be
read is left NULL and reported through `issues` (field, problem), so the raw value is never lost.
"""
import difflib, os, re, sys, unicodedata

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from build_persons import parse_date  # noqa: E402  (same era rules as the prosopography)


def fold(s):
    s = unicodedata.normalize('NFD', (s or '').lower())
    return ''.join(c for c in s if not unicodedata.combining(c)).replace('ṃ', 'm')


def parts(s):
    return [p.strip(' .?*()') for p in re.split(r',|;|/|\+|&|\band\b|\bamd\b|-(?=[A-Z])', s or '') if p.strip(' .?*()')]


NUMWORD = {'none': 0, 'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4}


def first_int(s):
    m = re.search(r'\d+', s or '')
    return int(m.group()) if m else None


# ---------------------------------------------------------------- reel numbers
REEL = re.compile(r'(?<![A-Za-z])([A-Z])\s*[-.]?\s*(\d{1,4})\s*[/-]\s*(\d{1,3})\s*([a-z]{0,4})(?![a-z])')


def reels(raw):
    """All reel references in a «Reel No.» value with their relation to the first one.

    'A 1/1 = A 3/1' -> identical; 'B 105/17 - B 106/1' -> continued; others -> also."""
    out = []
    s = re.sub(r'\(.*?\)', ' ', raw or '')
    for m in REEL.finditer(s):
        rel = 'primary' if not out else 'also'
        if out:
            between = s[out[-1]['end']:m.start()]
            rel = 'identical' if '=' in between else 'continued' if re.search(r'[-_–]|to', between) else 'also'
        out.append({'series': m.group(1), 'reel': int(m.group(2)), 'entry': int(m.group(3)),
                    'marker': m.group(4), 'rel': rel, 'end': m.end()})
    return out


def reel_label(series, reel, entry, marker=''):
    return f'{series} {reel}/{entry}{marker or ""}'


def reel_from_file(fname):
    m = re.search(r'([A-Z])\s*(\d{1,4})-(\d{1,3})\s*([a-z]{0,4})(?![a-z])', fname)
    return {'series': m.group(1), 'reel': int(m.group(2)), 'entry': int(m.group(3)), 'marker': m.group(4)} if m else None


# ---------------------------------------------------------------- vocabularies
# code -> (name, folded stems); codes follow the title-list tables where they exist
SCRIPTS = {
    'D': ('Devanagari', r'^d$|de?v|^de[an]|^den|nagar|^nāgar|nagri|utkirn'),
    'W': ('Newari', r'^w$|new|nev|ranjana|bhujim|pracalit'),
    'M': ('Maithili', r'^m$|maith'),
    'B': ('Bengali', r'beng|magadh'),
    'G': ('Transitional Gupta', r'gupta'),
    'T': ('Tibetan', r'tibet'),
    'S': ('South Indian', r'telug|tailang|grantha'),
    'Ku': ('Kuṭilā', r'kutil'),
    'Nn': ('Nandināgarī', r'nandi'),
    'Gi': ('Gilgit/Bamiyan', r'gilgit|girgit|bamiyan'),
}
SCRIPT_ORDER = ['Nn', 'Gi', 'Ku', 'G', 'B', 'M', 'T', 'S', 'W', 'D']  # first match wins per part
NEWARI_STYLE = [('pracalita', r'pracal'), ('bhujiṃmola', r'bhujim'), ('rañjanā', r'ranjan'), ('old', r'\bold\b|pracin')]

LANGUAGES = {
    'S': ('Sanskrit', r'^s$|^s[a-z]{1,5}kr|sansr|sanskr'),
    'W': ('Newari', r'newa|nevar'),
    'N': ('Nepali', r'nepa|neapl|^napal'),
    'H': ('Hindi', r'hind'),
    'M': ('Maithili', r'maith'),
    'Y': ('Prakrit', r'pra?kr|prakt'),
    'B': ('Bengali', r'beng'),
    'T': ('Tibetan', r'tibet'),
    'R': ('Marathi', r'marat'),
    'I': ('Persian', r'persi|pharas|farsi'),
    'A': ('Avadhi', r'avan?dh'),
    'G': ('Gujarati', r'gujar|gurjar'),
    'E': ('English', r'englis'),
    'P': ('Pali', r'^pali'),
}

MATERIALS = {  # code -> name; codes P, T, N, B, R, D as in the title list; paper (no code there) = 'paper'
    'paper': 'paper', 'P': 'palm-leaf', 'T': 'Thyāsaphu (paper leporello)', 'N': 'Nīlapattra (blue paper)',
    'B': 'Bhūrjapattra (birch bark)', 'R': 'paper roll', 'D': 'printed book', 'cloth': 'cloth',
}


def norm_script(raw):
    issues, codes = [], []
    f = fold(raw)
    for p in parts(f) or ([f] if f.strip() else []):
        for c in SCRIPT_ORDER:
            if re.search(SCRIPTS[c][1], p):
                if c not in codes:
                    codes.append(c)
                break
    style = [n for n, pat in NEWARI_STYLE if re.search(pat, f)]
    if raw and raw.strip() and not codes:
        issues.append(('script', 'unrecognised script'))
    if re.search(r'thyasap|paper', f):
        issues.append(('script', 'material given as script'))
    return {'script_codes': ' '.join(codes) or None, 'script_style': ', '.join(style) or None}, issues


def norm_language(raw):
    issues, codes = [], []
    f = fold(raw)
    for p in parts(f) + ([f] if not parts(f) and f.strip() else []):
        for c, (_, pat) in LANGUAGES.items():
            if re.search(pat, p) and c not in codes:
                codes.append(c)
    if raw and raw.strip() and not codes:
        issues.append(('language', 'language unknown' if raw.strip() == '?' else 'subject given as language'
                       if re.search(r'sastra|jyotis|tantra|karmak', f) else 'unrecognised language'))
    return {'language_codes': ' '.join(codes) or None}, issues


def norm_material(raw):
    f = fold(raw)
    issues = []
    code = None
    if re.search(r'palm|tala', f):
        code = 'P'
    elif re.search(r'th?y?a?a?s[ap]?h?p?h?u|t?hasaphu|tyasaphu|thayasap|leporel|^paper t$', f):
        code = 'T'
    elif re.search(r'nila', f):
        code = 'N'
    elif 'bhurj' in f:
        code = 'B'
    elif 'roll' in f:
        code = 'R'
    elif 'cloth' in f:
        code = 'cloth'
    elif re.search(r'p\s*a?p?[ae]?[rp]|pape|pper|aper|pa?er|nepal|indi', f):
        code = 'paper'
    elif f.strip() == 'p':
        issues.append(('material', 'bare code P (palm-leaf in the title list, but often paper here)'))
    elif 'complete' in f:
        issues.append(('material', 'state given as material'))
    elif re.search(r'nagari|newari', f):
        issues.append(('material', 'script given as material'))
    elif f.strip():
        issues.append(('material', 'unrecognised material'))
    if code and ('palm' in f and 'paper' in f):
        code = 'P'
        issues.append(('material', 'palm-leaf and paper'))
    origin = [o for o, pat in (('Nepali', r'nepa|nepe|neja'), ('Indian', r'indi|idian|^ne\. ka|ma\. ka')) if re.search(pat, f)]
    fmt = None
    if code == 'T':
        fmt = 'leporello'
    elif re.search(r'loose', f):
        fmt = 'loose'
    elif re.search(r'book|bound|notebook|exercise', f):
        fmt = 'book'
    return {'material_code': code, 'material': MATERIALS.get(code) if code else None,
            'paper_origin': ', '.join(origin) or None, 'format': fmt}, issues


STATE_CODE = re.compile(r'^\s*([CI])?([DU])?\s*$')  # the title list's codes: Complete/Incomplete, Damaged/Undamaged


def norm_state(raw):
    m = STATE_CODE.match(raw or '')
    if m and (raw or '').strip():
        return {'complete': {'C': 1, 'I': 0}.get(m.group(1)), 'damaged': {'D': 1, 'U': 0}.get(m.group(2))}, []
    f = fold(raw)
    complete = None
    if re.search(r'incompl|inompl|not complete|missing|lacking|partial|fragment', f):
        complete = 0
    elif 'complete' in f or 'compete' in f:
        complete = 1
    damaged = None
    if re.search(r'undamag|not damag|no damag|without damag|good condition', f):
        damaged = 0
    elif re.search(r'damag|broken|torn|insect|worm|stain|faded|burnt|fragile|illegible|hole', f):
        damaged = 1
    issues = [] if complete is not None or not f.strip() else [('state', 'completeness not stated')]
    return {'complete': complete, 'damaged': damaged}, issues


# '24.5', '22. 5', '22,5', '26 0' (space for the point), '1,057' (thousands), '24.0.0'
NUM = r'(\d{1,3},\d{3}(?:\.\d+|\s\d(?!\d))?|\d+(?:\s*[.,]\s*\d+|\s\d(?!\d))?)(?:\.\d*)*\.?'


def _num(s):
    if re.match(r'\d{1,3},\d{3}', s):
        s = s.replace(',', '')
    return float(re.sub(r'\s*[.,\s]\s*', '.', s.strip()))


def norm_size(raw):
    s = raw or ''
    m = re.search(NUM + r'\s*(?:cm)?\s*[x×X*]\s*' + NUM, s)
    if not m:
        return {'width_cm': None, 'height_cm': None}, ([('size', 'unreadable size')] if re.search(r'\d', s) else [])
    w, h = _num(m.group(1)), _num(m.group(2))
    issues = []
    if not (1 <= w and 1 <= h):
        issues.append(('size', f'implausible size {w} x {h}'))
    elif max(w, h) > 150:
        issues.append(('size', f'very long ({max(w, h)} cm): a roll?'))
    if 'mm' in s[m.end():m.end() + 6]:
        w, h = w / 10, h / 10
    return {'width_cm': w, 'height_cm': h}, issues


def norm_folios(raw):
    s = raw or ''
    m = re.match(r'\s*[\d\s+\-–]*=\s*(\d+)', s)  # '150-3=147', '405+1=406'
    n = int(m.group(1)) if m else None
    m = re.match(r'\s*(\d+)\s*\+\s*(\d+)\b(?!\s*=)', s)  # '18 + 2'
    if n is None and m:
        n = int(m.group(1)) + int(m.group(2))
    if n is None:
        m = re.match(r'\s*\*?\s*(\d+)', s)  # '*22': folio numbers supplied by the cataloguer
        n = int(m.group(1)) if m else None
    issues = []
    if n is None and s.strip():
        mm = re.search(r'total number of folios is (\d+)', s)
        n = int(mm.group(1)) if mm else None
        if n is None:
            issues.append(('folios', 'no folio count'))
    pages = 1 if re.search(r'\bpages?\b|\bpp\b', s, re.I) else 0
    return {'folio_count': n, 'counted_in_pages': pages}, issues


def norm_lines(raw):
    s = re.sub(r'\(.*?\)', '', raw or '')
    nums = [int(x) for x in re.findall(r'\d+', s.split('Pagination')[0])[:4] if 0 < int(x) < 80]
    if not nums:
        return {'lines_min': None, 'lines_max': None}, ([('lines_per_folio', 'no line count')] if (raw or '').strip() else [])
    return {'lines_min': min(nums), 'lines_max': max(nums)}, []


def norm_binding(raw):
    f = fold(raw).strip()
    if not f or f in ('-', 'x'):
        return {'binding_holes': None}, []
    if re.match(r'(folios|exposures|complete)', f):
        return {'binding_holes': None}, [('binding_hole', 'other field given as binding hole')]
    m = re.match(r'(\d+)', f)
    if m:
        n = int(m.group(1))
        return ({'binding_holes': n}, []) if n <= 6 else ({'binding_holes': None}, [('binding_hole', 'implausible count')])
    for w, n in NUMWORD.items():
        if re.match(w + r'\b', f):
            return {'binding_holes': n}, []
    if 'binding hole' in f or re.search(r'cent|middle|left|right|rectang|square|circular|cetre|senter', f):
        return {'binding_holes': 1}, []  # a position without a number describes one hole
    return {'binding_holes': None}, [('binding_hole', 'unreadable')]


# ---------------------------------------------------------------- dates of copying
MONTHS = [
    ('caitra', r'cait|caita'), ('vaiśākha', r'vais[a]?kh|baisakh|vaisa'), ('jyeṣṭha', r'jy?e[sṣ]?[tṭ]h|jesth|jeth'),
    ('āṣāḍha', r'a[sṣ]a[dḍ]h|asar'), ('śrāvaṇa', r'sraval?n|sravan|saun'), ('bhādrapada', r'bhadr|bhado'),
    ('āśvina', r'asv[iī]n|asoj|asvi|asvay'), ('kārttika', r'kart?t?ik'), ('mārgaśīrṣa', r'marg|mangsir|agrahay'),
    ('pauṣa', r'paus|pus\b'), ('māgha', r'magh'), ('phālguna', r'phal?g|phagu'),
]
PAKSA = [('śukla', r'sukla|sud[iī]|sudi|\bsu\b|sukl|sita|sukla'), ('kṛṣṇa', r'kr?s?na|krsna|krishna|bad[iī]|vad[iī]|\bva\b|asita')]
WEEKDAYS = [
    ('Sunday', r'ravi|aditya|arka|bhanu|surya'), ('Monday', r'soma|candra|indu'),
    ('Tuesday', r'mangal|kuja|bhauma|angarak'), ('Wednesday', r'budha|saumya'),
    ('Thursday', r'brhasp|guru|jiva|vrhasp|brhaspat|brihasp'), ('Friday', r'sukra|bhrgu|bhargava|bhrigu'),
    ('Saturday', r'sani|sanai|sauri|manda'),
]
TITHI_NAMES = ['pratipad', 'dvitīyā', 'tṛtīyā', 'caturthī', 'pañcamī', 'ṣaṣṭhī', 'saptamī', 'aṣṭamī', 'navamī',
               'daśamī', 'ekādaśī', 'dvādaśī', 'trayodaśī', 'caturdaśī', 'pūrṇimā/amāvāsyā']
TITHI_PAT = [r'prati?pa|pratipat|parev', r'dvitiy|dviti', r'trtiy|tritiy|trtiya', r'caturth|cauth', r'pancam|panchami',
             r'sast|sasth|sasthi|chath', r'saptam', r'astam', r'navam', r'dasam', r'ekadas', r'dvadas', r'trayodas|teras',
             r'caturdas|cauda', r'purnim|amavas|purnam|aunsi']


def norm_date(raw, script=''):
    s = raw or ''
    f = fold(s)
    d = parse_date(s, script) if s.strip() else None
    out = {'era': None, 'era_year': None, 'year_ce': None, 'era_inferred': None,
           'month': None, 'paksa': None, 'tithi': None, 'weekday': None, 'date_uncertain': None}
    issues = []
    if d:
        out.update(era=d['era'], era_year=d['year'], year_ce=d['ce'], era_inferred=int(d['inferred']))
        out['date_uncertain'] = int(bool(re.search(r'\?|ca\.|circa|approx|probab|perhaps|possibl', f)))
    elif s.strip() and re.search(r'\d', s):
        issues.append(('date_of_copying', 'date not read'))
    for name, pat in MONTHS:
        if re.search(pat, f):
            out['month'] = name
            break
    for name, pat in PAKSA:
        if re.search(pat, f):
            out['paksa'] = name
            break
    for name, pat in WEEKDAYS:
        if re.search(r'(?:' + pat + r')\w*\s*(?:var|dina|vasar|din\b)|\b(?:' + pat + r')\b', f):
            out['weekday'] = name
            break
    if out['month'] or out['paksa']:
        tail = f
        if out['paksa']:
            m = re.search('|'.join(p for n, p in PAKSA if n == out['paksa']), f)
            tail = f[m.end():] if m else f
        m = re.match(r'\W*(\d{1,2})\b', tail)
        if m and 1 <= int(m.group(1)) <= 30:
            out['tithi'] = int(m.group(1))
        else:
            for i, pat in enumerate(TITHI_PAT):
                if re.search(pat, tail):
                    out['tithi'] = i + 1
                    break
    return out, issues


# ---------------------------------------------------------------- calendar dates (filming, cataloguing)
def norm_day(raw, field):
    """'21-05-1973', '7-6-72', '10.09.1990', '00-00-2000', 'Summer 2002' -> ISO 'YYYY[-MM[-DD]]'."""
    s = re.sub(r'[-./]?\s*\((\d{2})\)', r'-\1', (raw or '').strip())  # '17-7-(19)72', '20-12(19)71'
    if not s or re.match(r'(not|none|n\.?/?a|-+$|x$|\?+$)', s, re.I):
        return None, []
    m = re.search(r'(?:BS|VS)?\s*(20[0-6]\d)\s*[-./]\s*(\d{1,2})\s*[-./]\s*(\d{1,2})', s)
    if m:  # Bikram Saṃvat date (BS 2043-1-28): the CE year only (months 1-9 of VS y fall in y-57)
        return str(int(m.group(1)) - 57 + (1 if int(m.group(2)) >= 10 else 0)), []
    m = re.search(r'(\d{1,3})\s*[-–./]\s*(\d{1,3})\s*[-–./]?\s*(\d{2,4})', s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
        y = int(y)
        if y < 100:
            y += 1900 if y > 30 else 2000
        elif y < 1000:  # '085'
            y = 1900 + y % 100
        if d > 31 and mo <= 12:  # some years were typed first
            d, y = y % 100, d if d > 1900 else y
        if not 1960 <= y <= 2025:
            return None, [(field, 'implausible year')]
        if mo == 0 or d == 0:
            return f'{y:04d}', []
        if mo > 12 and d <= 12:
            d, mo = mo, d
        if mo > 12 or d > 31:
            return f'{y:04d}', [(field, 'impossible day or month')]
        return f'{y:04d}-{mo:02d}-{d:02d}', []
    m = re.search(r'\b(19[6-9]\d|20[0-2]\d)\b', s)
    if m:
        return m.group(1), []
    return None, [(field, 'unreadable date')]


# ---------------------------------------------------------------- other fields
def norm_inventory(raw):
    s = (raw or '').strip()
    f = fold(s)
    out = {'inventory_no': None, 'inventory_new': 0}
    if re.search(r'new', f):
        out['inventory_new'] = 1
    m = re.match(r'\D{0,6}?(\d{3,7})\b', s)
    if m and not f.startswith('mtm'):
        out['inventory_no'] = int(m.group(1))
    issues = [] if out['inventory_no'] or out['inventory_new'] or not s or s in ('?', '-') else [('inventory_no', 'unreadable')]
    return out, issues


def norm_accession(raw):
    m = re.search(r'(\d+)\s*[-/]\s*(\d+)', raw or '')
    return {'acc1': int(m.group(1)), 'acc2': int(m.group(2))} if m else {'acc1': None, 'acc2': None}


DEPOSIT = [('NAK', r'^nak|national arch|^n\.?a\.?$'), ('Kaiser Library', r'k[ae][iy]?s[h]?[ae]r|kesar'),
           ('Tribhuvan University Library', r'tribhuvana'), ('Kathmandu', r'^k(ath|tm)'), ('Patan', r'patan|pata?na'),
           ('Bhaktapur', r'bhakta'), ('Kirtipur', r'kirti')]


def norm_deposit(raw):
    f = fold(raw).strip()
    for name, pat in DEPOSIT:
        if re.search(pat, f):
            return name
    return (raw or '').strip() or None


def norm_yesno(raw):
    f = fold(raw).strip()
    if not f or f in ('no/yes', 'yes/no'):  # the template's unfilled choice
        return None
    if f.startswith('no'):
        return 0
    if f.startswith('yes') or 'edition' in f or f.startswith('ed.'):
        return 1
    return None


def norm_film(raw):
    f = fold(raw)
    return 'negative/positive' if 'negative/positive' in f else 'positive' if f.startswith('pos') else \
        'negative' if f.startswith('neg') else None


def norm_used_copy(raw):
    f = fold(raw)
    return ' / '.join(n for n in ('Kathmandu', 'Berlin', 'Hamburg') if fold(n) in f) or None


# ---------------------------------------------------------------- subjects
class Subjects:
    """Match subject text against the title list's subject vocabulary (abbreviation, name)."""
    ALIAS = {'saiva tantra': 'ŚT', 'saivatantra': 'ŚT', 'vaisnava tantra': 'VT', 'vaisnavatantra': 'VT',
             'bauddha tantra': ['B', 'T'], 'bauddhatantra': ['B', 'T'], 'bauddhadharani': ['B', 'Dhā'],
             'bauddha dharani': ['B', 'Dhā'], 'bauddhastotra': ['B', 'St'], 'bauddha stotra': ['B', 'St'],
             'bauddhakarmakanda': ['B', 'Kk'], 'bauddha karmakanda': ['B', 'Kk'], 'bauddhasutra': 'BS',
             'dharmasastra': 'Dh', 'nataka': 'N', 'natya': 'N', 'natyasastra': 'N', 'kavya': 'Kā', 'sahitya': 'Sā',
             'jyotisa': 'J', 'jyotisha': 'J', 'ayurveda': 'Āy', 'vyakarana': 'Vy', 'kosa': 'Ko', 'kosha': 'Ko',
             'mahatmya': 'Pu', 'tantra': 'T', 'stotra': 'St', 'karmakanda': 'Kk', 'purana': 'Pu', 'vedanta': 'Ved',
             'darsana': 'D', 'niti': 'Nī', 'chandas': 'Ch', 'chandahsastra': 'Ch', 'sangita': 'Sg', 'samgita': 'Sg',
             'silpa': 'Śi', 'silpasastra': 'Śi', 'vastu': 'Vā', 'vastusastra': 'Vā', 'mimamsa': 'Mīm',
             'nyaya': 'Ny', 'samkhya': 'Skh', 'sankhya': 'Skh', 'yoga': 'Yo', 'veda': 'V', 'upanisad': 'Up',
             'ramayana': 'Rām', 'mahabharata': 'Mbh', 'itihasa': 'Iti', 'katha': 'K', 'jataka': 'Jā', 'jaina': 'Jai',
             'avadana': 'Av', 'asvayurveda': 'Āy', 'hastyayurveda': 'Āy', 'nitisastra': 'Nī', 'bhakti': 'Bh', 'dharani': 'Dhā', 'mantra': 'M', 'ganita': 'G', 'kamasastra': 'Kām',
             'vaisesika': 'Vai', 'agama': 'Ā', 'subhasita': 'Su', 'document': 'Doc', 'vividha': 'Viv',
             'alankara': 'Al', 'alamkara': 'Al', 'bauddha': 'B', 'citra': 'Ci', 'periodical': 'Pe'}

    def __init__(self, rows):  # rows: (id, abbreviation, subject)
        self.by_abbr = {a: i for i, a, _ in rows}
        self.names = {}
        for i, a, name in rows:
            self.names[re.sub(r'[^a-z]', '', fold(re.split(r'[\s(—,-]', name)[0]))] = a

    def __call__(self, raw):
        f = fold(re.sub(r'\(.*?\)|;.*', '', raw or ''))
        abbrs = []
        for p in re.split(r',|/|\+|&|\band\b', f):
            p = p.strip(' .?*:')
            if not p:
                continue
            key = re.sub(r'[^a-z ]', '', p).strip()
            hit = self.ALIAS.get(key) or self.ALIAS.get(key.replace(' ', '')) or self.names.get(key.replace(' ', ''))
            if not hit:
                close = difflib.get_close_matches(key.replace(' ', ''), list(self.ALIAS) + list(self.names), 1, 0.85)
                if close:
                    hit = self.ALIAS.get(close[0]) or self.names.get(close[0])
            if not hit:  # 'Jyautiṣa', 'Nītiśāstra', 'Vedāntadarśana', 'Tāntrikakarmakāṇḍa', 'Śāktatantra'
                k2 = re.sub(r'(sastra|darsana)$', '', key.replace(' ', '')).replace('jyautis', 'jyotis')
                k2 = re.sub(r'^(tantrika|sakta|sakti)', '', k2) or 'tantra'
                hit = self.ALIAS.get(k2) or self.names.get(k2)
                if hit and re.match(r'tantrika', key):
                    hit = [hit, 'T'] if isinstance(hit, str) else hit + ['T']
            if not hit and p.strip() in {a.lower() for a in self.by_abbr}:  # an abbreviation ('Kk')
                hit = next(a for a in self.by_abbr if a.lower() == p.strip())
            if not hit and key.startswith('bauddha'):
                rest = key[7:].strip()
                hit = ['B'] + ([self.ALIAS[rest]] if rest in self.ALIAS else [])
            for a in ([hit] if isinstance(hit, str) else hit or []):
                a = a if isinstance(a, str) else a[0]
                if a in self.by_abbr and a not in abbrs:
                    abbrs.append(a)
        issues = [] if abbrs or not f.strip() else [('subject', 'subject not in the title-list vocabulary')]
        return [self.by_abbr[a] for a in abbrs], issues
