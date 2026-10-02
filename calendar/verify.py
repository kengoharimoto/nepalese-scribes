"""Convert and verify colophon dates with the Pañcāṅga program of Yano & Fushimi (pancanga313_ns_test.pl).

verify(era, year, month, paksa, tithi, weekday, naksatra) finds the civil day (Kathmandu sunrise) of a dated
colophon and checks it against the stated weekday (and nakṣatra).

Standard reading per era (Śaka years expired; CE ≈ Śaka + 78):
  NS  Śaka = NS + 801 (Kārttika–Phālguna), + 802 (Caitra–Āśvina)   amānta months
  VS  Śaka = VS − 135 (Caitrādi)                                    pūrṇimānta months for the dark fortnight
  ŚS  Śaka = ŚS                                                     pūrṇimānta months for the dark fortnight
  AS  Aṃśuvarman ("Mānadeva") saṃvat: Śaka = AS + 498 (Kārttika–Phālguna), + 499 (Caitra–Āśvina);
      CE = AS + 576 (Kārttika to December), + 577 (January to Āśvina)   amānta
      After K. P. Malla, "Mānadeva Samvat: an investigation into an historical fraud", CNAS Journal 32.1
      (2005): not an era of its own but the Kārttikādi Śaka with 500 dropped, used from Aṃśuvarman's year 29.
      It fits the only two Licchavi-period dates with a weekday: saṃvat 31 Māgha śukla 13, Sunday, Puṣya
      (Aṃśuvarman's repoussé at Cāṅgu) = Sunday 4 Feb 608, and saṃvat 301 Vaiśākha śukla 7, Sunday, Puṣya
      (Suśrutasaṃhitā, NGMCP C 80/7) = Sunday 13 Apr 878; and NS 1 = AS 304, the traditional reckoning.
  LS  Śaka = LS + 1041 (Kielhorn, CE ≈ LS + 1119)                   not verified (see below)
  HS  Harṣa: Śaka = HS + 528; KS Kali: Śaka = KS − 3179              amānta
The month systems and year conventions were checked on the NGMCP dates themselves: with them, the stated
weekday agrees in about two thirds of fully stated NS, VS and Śaka dates (the rest are mostly misread or
miscopied elements), against one in seven by chance. Lakṣmaṇasena dates agree at chance level under every
epoch from LS + 1103 to + 1123, so LS dates are converted but never reported as verified.

A day fits when its sunrise tithi is the stated one (or the stated tithi is kṣaya within that day), its
weekday is the stated one, and the stated nakṣatra is current at sunrise or begins that day. One departure
from the standard reading is allowed, and named in `rule`:
  year       the current year (NS, VS, ŚS: one year earlier) / Kārttikādi VS / one year later
  months     the other month system (amānta <-> pūrṇimānta) for a dark-fortnight date
  tithi      the stated tithi begins after sunrise (current later that day) or ended that morning (expired)
Two departures together would fit one random date in about three, so they are not tried. Tested on the
NGMCP dates against the same dates with deliberately wrong weekdays, only some departures carry signal:
a tithi current later that day or expired (about 3 in 4 such fits genuine) and pūrṇimānta months where
amānta is standard (7 in 10). The others (current year, year + 1, Kārttikādi, amānta months for VS and Śaka)
fit wrong dates almost as often as right ones: they verify only together with a stated nakṣatra, and are
otherwise listed under `possible` while the date keeps the standard reading.

status
  verified          the standard reading fits the weekday (and the nakṣatra, if stated)
  verified-alt      one departure from it fits (rule): a strong one, or any one with the nakṣatra
  verified-weekday  the weekday fits (standard reading) but the stated nakṣatra does not
  unverified        a weekday is stated but nothing fits: the standard reading is used (`possible`: weak
                    departures that would fit)
  computed          nothing to check (no weekday, or a weekday without tithi or nakṣatra; LS dates)
  year-only         no month: CE year of the standard reading (± 1)
`ambiguous`: more than one day fits.
"""
import os, re, subprocess, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
PANCANGA = os.path.join(HERE, '..', 'pancanga313_ns_test.pl')
MASA = ['Caitra', 'Vaisakha', 'Jyaistha', 'Asadha', 'Sravana', 'Bhadrapada', 'Asvina', 'Karttika', 'Margasirsa',
        'Pausa', 'Magha', 'Phalguna']
MASA_IAST = ['Caitra', 'Vaiśākha', 'Jyeṣṭha', 'Āṣāḍha', 'Śrāvaṇa', 'Bhādrapada', 'Āśvina', 'Kārttika',
             'Mārgaśīrṣa', 'Pauṣa', 'Māgha', 'Phālguna']
MASA_PAT = [r'cait|चैत', r'vais|baisa|vaiś|वैशा|वैशा|बैशा|वैसा', r'jy?e[sṣ]?[tṭ]|jye|jeṭh|jeth|ज्ये|जेठ|जेष्ठ',
            r'a[sṣ]a[dḍ]h|asar|आषा|आसा|अषा|असा[ढर]', r'sr[aā]va|srav|saun|श्राव|श्रव|स्राव|सावन',
            r'bh[aā]dr|bhado|भाद्र|भाद्', r'asv[iī]n|asoj|asvay|asvi|आश्वि|अश्वि|आसो|असो|आश्व',
            r'kart|kārt|katti|कार्त|कात्ति|कार्ति|कातिक', r'marg|agrah|mangs|marga|मार्ग|मार्गशि|अग्रह|मंसि',
            r'pau[sṣ]|pus|poṣ|pos|पौष|पौस|पुष|पूष', r'm[aā]gh|माघ', r'ph[aā]lg|phagu|phalu|फाल्ग|फागु|फाल्गु']
NAK = ['Asvini', 'Bharani', 'Krttika', 'Rohini', 'Mrgasira', 'Ardra', 'Punarvasu', 'Pusya', 'Aslesa', 'Magha',
       'P-phalguni', 'U-phalguni', 'Hasta', 'Citra', 'Svati', 'Visakha', 'Anuradha', 'Jyestha', 'Mula', 'P-asadha',
       'U-asadha', 'Sravana', 'Dhanistha', 'Satabhisaj', 'P-bhadrapada', 'U-bhadrapada', 'Revati']
NAK_PAT = [r'asvin|aśvin', r'bhara', r'kr?tti|kṛtti', r'rohi', r'mr?ga|mṛga', r'ardr|ārdr', r'punar', r'pu[sṣ]y|tisy|tiṣy',
           r'asle|aśle|asre', None, r'p(?:urva|ūrva)?\W*ph?alg', r'u(?:ttara)?\W*ph?alg', r'hast', r'citr|citt',
           r'sv[aā]t', r'vi[sś][aā]kh|bisakh', r'anur', r'jye[sṣ][tṭ]h|jyes', r'm[uū]l', r'p(?:urva|ūrva)\W*[aā][sṣ][aā]',
           r'u(?:ttara)?\W*[aā][sṣ][aā]', r'[sś]rava|abhij', r'dhani|[sś]ravi[sṣ]', r'[sś]atabh|satabh|[sś]ata[bv]',
           r'p(?:urva|ūrva)\W*bh', r'u(?:ttara)?\W*bh', r'rev']
WEEK = [('Sunday', r'sun|ravi|[aā]ditya|arka|bh[aā]nu|s[uū]rya'), ('Monday', r'mon|soma|candra|indu'),
        ('Tuesday', r'tue|ma[nṅṃ]gal|kuja|bhauma|a[nṅ]g[aā]rak'), ('Wednesday', r'wed|budha|saumya'),
        ('Thursday', r'thu|br?hasp|bṛhasp|guru|j[iī]va|vrhasp'), ('Friday', r'fri|[sś]ukra|bhr?gu|bhṛgu|bh[aā]rgava'),
        ('Saturday', r'sat|[sś]ani|[sś]anai|sauri|manda')]
WEEK_DEV = [('Sunday', r'(?:रवि|आदित्य|अर्क|भानु|सूर्य)\S{0,3}\s*(?:वा|दि)'), ('Monday', r'(?:सोम|चन्द्र|इन्दु)\S{0,3}\s*(?:वा|दि)'),
            ('Tuesday', r'(?:मङ्गल|मंगल|मंगळ|कुज|भौम|अङ्गार)\S{0,3}\s*(?:वा|दि)'), ('Wednesday', r'(?:बुध|सौम्य)\S{0,3}\s*(?:वा|दि)'),
            ('Thursday', r'(?:बृहस्पति|वृहस्पति|गुरु|जीव)\S{0,3}\s*(?:वा|दि)'), ('Friday', r'(?:शुक्र|भृगु|भार्गव)\S{0,3}\s*(?:वा|दि)'),
            ('Saturday', r'(?:शनि|शनै|सौरि)\S{0,3}\s*(?:वा|दि)')]
TITHI = [r'prati?pa|prathama|parev', r'dvit[iī]y|dvit', r'tr?t[iī]y|tṛt', r'caturth|cauth', r'pa[nñ]cam',
         r'[sṣ]a[sṣ][tṭ]h', r'saptam', r'a[sṣ][tṭ]am', r'navam', r'da[sś]am', r'ek[aā]da[sś]', r'dv[aā]da[sś]',
         r'trayoda[sś]|teras', r'caturda[sś]|cauda', r'p[uū]r[nṇ]im|p[uū]r[nṇ]am|am[aā]v[aā]s|amāvas|darsa|darśa']
OFFSET = {'NS': None, 'VS': -135, 'ŚS': 0, 'LS': 1041, 'HS': 528, 'KS': -3179, 'AS': None}
# alternative year readings: Śaka-year shift, name
ALT = {'NS': [(-1, 'current year'), (1, 'year + 1')], 'VS': [(1, 'Kārttikādi'), (-1, 'current year')],
       'ŚS': [(-1, 'current year'), (1, 'year + 1')], 'LS': [], 'HS': [(1, 'year + 1'), (-1, 'year − 1')],
       'KS': [(1, 'year + 1'), (-1, 'year − 1')], 'AS': [(1, 'year + 1'), (-1, 'year − 1')]}
PURNIMANTA = {'VS', 'ŚS'}  # standard month system for the dark fortnight
UNVERIFIABLE = {'LS'}


def fold(s):
    """Lower case without diacritics on Latin letters; Devanāgarī is left intact (its vowel signs are combining)."""
    out = []
    for c in unicodedata.normalize('NFD', (s or '').lower()):
        if unicodedata.combining(c) and out and out[-1] < '\u0900':
            continue
        out.append(c)
    return unicodedata.normalize('NFC', ''.join(out))


def norm_era(s):
    f = fold(s).replace(' ', '')
    for era, pat in (('AS', r'^as$|^ms$|a[mṃ][sś]uvarma|m[aā]nadeva|licchavi'), ('NS', r'^ns|nepal|newar'), ('VS', r'^vs|vikram|samvat$'), ('ŚS', r'^ss|^śs|saka|sake'),
                     ('LS', r'^ls|laks'), ('HS', r'^hs|harsa|harṣa'), ('KS', r'^ks|kali')):
        if re.search(pat, f):
            return era
    return None


def norm_month(s):
    f = fold(s)
    adhika = bool(re.search(r'adhik|dvit[iī]ya|second|mala|intercal', f))
    for i, pat in enumerate(MASA_PAT):
        if re.search(pat, f):
            return i, adhika
    return None, adhika


def norm_paksa(s):
    f = fold(s)
    if re.search(r'[sś]ukl|sud[iī]|[sś]udi|\bsu\b|sita|bright|[sś]ud\b|shukla|शुक्ल|शुदि|सुदि|शुद्धि|शुद्दि|सुद्धि|शुद', f):
        return 's'
    if re.search(r'kr?[sṣ][nṇ]|bad[iī]|vad[iī]|\bva\b|asita|dark|krish|कृष्ण|वदि|बदि|वद्य|बद्य|कृस्न', f):
        return 'k'
    return None


def norm_tithi(s):
    f = fold(s)
    m = re.search(r'\d+', f)
    if m:
        t = int(m.group())
        return t if 1 <= t <= 30 else None
    for i, pat in enumerate(TITHI):
        if re.search(pat, f):
            return 30 if re.search(r'am[aā]v|darsa', f) else i + 1
    return None


def norm_weekday(s):
    f = fold(s)
    for name, pat in WEEK_DEV:  # Devanāgarī only with -vāra / -dina, so a name is not taken for a weekday
        if re.search(pat, s or ''):
            return name
    if re.search(r'[\u0900-\u097F]', s or '') and not re.search(r'[a-z]{3}', f):
        return None
    for name, pat in WEEK:
        if re.search(pat, f):
            return name
    return None


def norm_naksatra(s):
    f = fold(s)
    f = re.sub(r'yoga.*', '', f)  # the field often reads 'nakṣatra / yoga'
    for i, pat in enumerate(NAK_PAT):
        if pat and re.search(pat, f):
            return i
    if re.search(r'\bmagh', f):
        return 9
    return None


class Pancanga:
    def __init__(self):
        self.p = subprocess.Popen(['perl', os.path.join(HERE, 'panc_batch.pl')], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, text=True, env=dict(os.environ, PANCANGA=PANCANGA))
        self.cache = {}

    def ask(self, q):
        self.p.stdin.write(q + '\n')
        self.p.stdin.flush()
        return self.p.stdout.readline().split()

    def tithi_day(self, saka, masa, paksa, tithi):
        r = self.ask(f'T q {saka} {masa} {paksa} {tithi}')
        return float(r[5])

    def day(self, jd):
        if jd not in self.cache:
            r = self.ask(f'J q {jd}')
            masa = r[6]
            self.cache[jd] = {'date': (int(r[1]), int(r[2]), int(r[3])), 'weekday': r[4], 'saka': int(r[5]),
                              'adhika': masa.startswith('Adhika-'), 'masa': MASA.index(masa.replace('Adhika-', '')),
                              'paksa': 's' if r[7].startswith('S') else 'k', 'tithi': int(r[8]),
                              'nak': NAK.index(r[9]) if r[9] in NAK else None, 'jd': jd}
        return self.cache[jd]


_P = None


def pancanga():
    global _P
    if _P is None:
        _P = Pancanga()
    return _P


def saka_years(era, year, masa):
    if era in ('NS', 'AS'):  # Kārttikādi: Kārttika–Phālguna in one Śaka year, Caitra–Āśvina in the next
        base = year + {'NS': 801, 'AS': 498}[era] + (0 if masa is None or masa >= 7 else 1)
    else:
        base = year + OFFSET[era]
    return [(base, 0, 'standard')] + [(base + d, 1, why) for d, why in ALT.get(era, [])]


def ce_year(era, year, masa):
    """CE year of the standard reading (Śaka + 78, + 79 for the months after Pauṣa that fall in January–March).
    Without a month, the year that most of the era year falls in (NS + 880, VS − 57, ŚS + 78, ...): ± 1."""
    s = saka_years(era, year, 0 if masa is None else masa)[0][0]
    return s + 78 + (1 if masa is not None and masa >= 9 else 0)


def candidates(saka, masa, paksa, tithi):
    """Days of (amānta) masa/paksa in Śaka year `saka`, with the absolute tithi number (1-30) of each."""
    P = pancanga()
    t0 = (tithi if tithi else 1) + (15 if paksa == 'k' and (tithi or 0) <= 15 else 0)
    p0 = 'k' if t0 > 15 else 's'
    jd = P.tithi_day(saka, masa, p0, t0 - 15 if t0 > 15 else t0)
    out = []
    for d in range(-40, 41):  # the program's tithi day is approximate, and an adhika month may intervene
        x = P.day(jd + d)
        if x['masa'] == masa and (paksa is None or x['paksa'] == paksa):
            x = dict(x, abs_tithi=x['tithi'] + (15 if x['paksa'] == 'k' else 0))
            out.append(x)
    return out


def tithi_ok(days, x, tithi, paksa, loose=False):
    """The tithi is current at sunrise, or is a kṣaya tithi falling within the day. With `loose` it may also
    begin after sunrise (current later that day: the sunrise tithi is the one before) or have ended that
    morning (expired: the sunrise tithi is the one after)."""
    if not tithi:
        return True
    t = tithi + (15 if paksa == 'k' and tithi <= 15 else 0)
    if x['abs_tithi'] == t:
        return True
    prev = [d for d in days if d['jd'] == x['jd'] - 1]
    if x['abs_tithi'] == t + 1 and prev and prev[0]['abs_tithi'] == t - 1:  # kṣaya: tithi t within this day
        return True
    return loose and (x['abs_tithi'] in (t - 1, t + 1) or (t == 1 and x['abs_tithi'] == 30) or (t == 30 and x['abs_tithi'] == 1))


def nak_ok(x, nak):
    return nak is None or x['nak'] is None or x['nak'] == nak or (x['nak'] + 1) % 27 == nak


def iso(d):
    return f'{d[0]:04d}-{d[1]:02d}-{d[2]:02d}'


def verify(era, year, month='', paksa='', tithi='', weekday='', naksatra=''):
    era = era if era in OFFSET else norm_era(era or '')
    try:
        year = int(re.search(r'\d+', str(year)).group())
    except (AttributeError, TypeError):
        return {'status': 'no-year'}
    if not era:
        return {'status': 'no-era'}
    masa, adhika = norm_month(month) if isinstance(month, str) else (month, False)
    pk, ti = norm_paksa(paksa), norm_tithi(tithi)
    if ti and ti > 15:
        pk, ti = 'k', ti - 15
    if ti == 15 and re.search(r'am[aā]v|darsa|अमाव', fold(tithi or '')):
        pk = 'k'
    elif ti == 15 and pk is None and re.search(r'p[uū]r[nṇ]i?m|पूर्ण|पौर्ण', fold(tithi or '')):
        pk = 's'  # pūrṇimā
    wd, nk = norm_weekday(weekday), norm_naksatra(naksatra)
    given = {'era': era, 'year': year, 'masa': MASA_IAST[masa] if masa is not None else None, 'paksa': pk,
             'tithi': ti, 'weekday': wd, 'naksatra': NAK[nk] if nk is not None else None}
    if masa is None:
        return {'status': 'year-only', 'ce': ce_year(era, year, None), 'given': given}
    std_months = 'pūrṇimānta' if (era in PURNIMANTA and pk == 'k') else 'amānta'
    other_months = 'amānta' if std_months == 'pūrṇimānta' else 'pūrṇimānta'

    def month_of(system, saka):  # (Śaka year, amānta month) holding the stated month/pakṣa
        if system == 'pūrṇimānta' and pk == 'k':  # dark half of pūrṇimānta m = dark half of amānta m − 1
            return (saka - 1 if masa == 0 else saka), (masa - 1) % 12
        return saka, masa

    years = saka_years(era, year, masa)
    # (departures, Śaka, months, loose tithi, rule, strong): a weak departure fits a wrong date about as often as
    # a right one (tested on the NGMCP dates with shifted weekdays), so alone it does not verify
    readings = [(0, years[0][0], std_months, False, 'standard', True)]
    readings += [(1, sk, std_months, False, why, False) for sk, _, why in years[1:]]
    if pk == 'k':
        readings.append((1, years[0][0], other_months, False, f'{other_months} months', other_months == 'pūrṇimānta'))
    if ti:
        readings.append((1, years[0][0], std_months, True, 'tithi current later that day or expired', True))
    if years[0][0] < 1022:  # before c. 1100 intercalation followed the mean sun: a lunation may bear the
        for d in (1, -1):   # neighbouring month's name (Sewell & Dikshit); weak: verifies only with a nakṣatra
            readings.append((1, years[0][0] + (1 if masa + d > 11 else -1 if masa + d < 0 else 0), std_months, False,
                             f'month named {"one later" if d == 1 else "one earlier"} (mean-sun intercalation)', False, (masa + d) % 12))
    can_check = wd and (ti or nk is not None) and era not in UNVERIFIABLE
    std, found = None, []
    for rd in readings:
        dep, saka, system, loose, why, strong = rd[:6]
        if dep and not can_check:
            continue
        sk, m = month_of(system, saka) if len(rd) == 6 else (saka, rd[6])
        days = candidates(sk, m, pk, ti)
        month_days = [x for x in days if x['adhika'] == adhika or not any(d['adhika'] for d in days)]
        hits = [x for x in month_days if tithi_ok(days, x, ti, pk, loose)]
        if dep == 0:
            std = hits[0] if hits else (month_days[len(month_days) // 2] if month_days else None)
        if not can_check:
            continue
        full = [x for x in hits if x['weekday'] == wd and nak_ok(x, nk)]
        if full:
            found.append(('verified' if dep == 0 else 'verified-alt' if strong or nk is not None else 'possible',
                          why, full))
        elif dep == 0 and nk is not None and ti and [x for x in hits if x['weekday'] == wd]:
            found.append(('verified-weekday', why, [x for x in hits if x['weekday'] == wd]))
    order = {'verified': 0, 'verified-weekday': 1, 'verified-alt': 2}
    possible = sorted({w for st, w, _ in found if st == 'possible'})
    found = [f for f in found if f[0] != 'possible']
    if found:
        status, why, xs = min(found, key=lambda f: order[f[0]])
        x = xs[0]
        rule = why if why != 'standard' else 'standard'
        if std_months == 'pūrṇimānta':
            rule += ' (pūrṇimānta months)' if 'months' not in why else ''
        return {'status': status, 'rule': rule, 'date': iso(x['date']), 'ce': x['date'][0], 'given': given,
                'fits': sorted({w for st, w, _ in found if st != 'verified-weekday'}),
                'ambiguous': len({y['jd'] for y in xs}) > 1 or sum(1 for f in found if f[0] == status) > 1,
                'computed': {'weekday': x['weekday'], 'tithi': x['abs_tithi'],
                             'naksatra': NAK[x['nak']] if x['nak'] is not None else None, 'saka': x['saka']}}
    if std is None:
        return {'status': 'year-only', 'ce': ce_year(era, year, masa), 'given': given}
    exact = bool(ti) and std.get('abs_tithi') is not None
    out = {'possible': possible} if possible else {}
    return {**out, 'status': 'unverified' if can_check else 'computed',
            'rule': 'standard' + (', Lakṣmaṇasena era: not verifiable' if era in UNVERIFIABLE else ''), 'ce': std['date'][0],
            'date': iso(std['date']) if exact else f"{std['date'][0]:04d}-{std['date'][1]:02d}", 'given': given,
            'computed': {'weekday': std['weekday'], 'tithi': std['abs_tithi'],
                         'naksatra': NAK[std['nak']] if std['nak'] is not None else None, 'saka': std['saka']}}


if __name__ == '__main__':
    tests = [('NS', 128, 'Phālguna', 'śukla', '', 'Monday', 'Uttarabhādrapadā'),  # Bendall Add. 866
             ('VS', 2080, 'Kārttika', 'kṛṣṇa', 'amāvāsyā', 'Monday', ''),        # 13 Nov 2023 (VS: pūrṇimānta)
             ('ŚS', 1945, 'Āśvina', 'kṛṣṇa', '15', 'Monday', ''),               # same day, amānta
             ('AS', 31, 'Māgha', 'śukla', '13', 'Sunday', 'Puṣya'),             # Cāṅgu repoussé: 4 Feb 608
             ('AS', 301, 'Vaiśākha', 'śukla', '7', 'Sunday', 'Puṣya')]          # Suśrutasaṃhitā: 13 Apr 878
    for t in tests:
        print(t, '->', verify(*t))
