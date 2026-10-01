"""Build a prosopographical dataset from parsed NGMCP records.

Input:  data/records.jsonl (parse_ngmcp.py)
Output: data/manuscripts.json  one row per microfilm reel (deduplicated)
        data/persons.json      one row per person (scribe / donor / king), with links to MSS
"""
import json, re, os, unicodedata, collections

HERE = os.path.dirname(os.path.abspath(__file__))
D = lambda *p: os.path.join(HERE, 'data', *p)

# ---------------------------------------------------------------- reels
def reel_key(r):
    """'A 1/1 = A 3/1' -> 'A 1/1'; falls back to the filename's reel number."""
    s = (r.get('Reel No.') or '').split('=')[0]
    m = re.search(r'([A-Z]{1,2})\s*(\d+)\s*[/-]\s*(\d+)\s*([a-z]?)', s)
    if not m:
        m = re.search(r'([A-Z]{1,2})\s*(\d+)\s*-\s*(\d+)\s*([a-z]?)', r['file'])
    if not m:
        return r['file']
    return f'{m.group(1)} {int(m.group(2))}/{int(m.group(3))}{m.group(4)}'


# ---------------------------------------------------------------- dates
ERA_OFFSET = {'NS': 880, 'VS': -57, 'ŚS': 78, 'LS': 1119}
ERA_PATTERNS = [  # order matters only for ties; the earliest match in the string wins
    ('NS', r'\bN\s?[SŚ]\b|Nepāla\s*[Ss]aṃvat'),
    ('VS', r'\bV\s?S|Vikra?ma'),
    ('ŚS', r'ŚS|ŚŚ|\bSS\b|Śaka|[Śś]āke|[Śś]ake'),
    ('LS', r'\bL\.?\s?S\.?'),
    ('SAM', r'SAM|[Ss]a[mṃ]vat|[Ss]aṃ\.?|[Ss]a[mṃ]\b|Sambat|Sṃ|\bS\b'),
]
YEAR = r'[\s.?:]*(?:(NS|VS|ŚS|ŚŚ|LS)[\s?]*)?(\d{2,4})\b'


def parse_date(s, script=''):
    """Return dict(era, year, ce, inferred) or None."""
    if not s:
        return None
    s = re.sub(r'[\[\]\(\)]', ' ', s)
    s = re.sub(r'\b([NVLŚ])\s+([SŚ])\b', r'\1\2', s)
    best = None
    for era, pat in ERA_PATTERNS:
        m = re.search(r'(?:' + pat + r')' + YEAR, s)
        if m and (best is None or m.start() < best[2]):
            best = (era, m, m.start())
    if not best:
        m = re.match(r'\s*(\d{3,4})\b', s)  # bare number
        if not m:
            return None
        best = ('SAM', m, 0)
        year = int(m.group(1))
    else:
        era, m, _ = best
        year = int(m.group(2))
        if m.group(1):  # "SAM (NS) 856"
            best = ({'ŚŚ': 'ŚS'}.get(m.group(1), m.group(1)), m, 0)
    era = best[0]
    inferred = False
    if era == 'SAM':
        inferred = True
        newari = 'newar' in script.lower()
        if year <= 1150 and (newari or year < 1000):
            era = 'NS'
        elif year >= 1500 or not newari:
            era = 'VS'
        else:
            era = 'NS'
    ce = year + ERA_OFFSET[era]
    if not 500 <= ce <= 2030:
        return None
    return {'era': era, 'year': year, 'ce': ce, 'inferred': inferred}


# ---------------------------------------------------------------- names
JUNK = re.compile(r'^(?:n/?a|none|unknown|not mentioned|-+|\?+|\\)$', re.I)
HONORIFIC = re.compile(r'^(?:śrī\s*|śri\s*|sri\s*|bābu\s+|paṇḍita\s+|pt\.\s*)+', re.I)


def split_names(s):
    if not s or len(s) > 90 or JUNK.match(s.strip()):
        return []
    # the cataloguer's lacuna marks ('...ryānanda', '(‥)bhayānanda', '+++candra', '///hīndramalla') make a
    # name a fragment: mark them before brackets and dots are stripped, and skip the marked names
    s = re.sub(r'\.{2,}|‥|…|\+{2,}|/{2,}', '§', s)
    s = re.sub(r'\[[^§]*?\]|\([^§]*?\)', '', s)
    s = re.sub(r'(?i)ṭīkākāraḥ?\s*:.*', '', s)
    out = []
    for p in re.split(r',|;|\band\b|&|/', s):
        p = p.strip(' ?.:*')
        if len(p) < 3 or '§' in p or JUNK.match(p) or re.search(r'\d|exp\.|fol\.', p):
            continue
        out.append(p)
    return out


def fold(s):
    s = unicodedata.normalize('NFD', s.lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = s.replace('ṃ', 'm')
    return s


UNUSABLE = re.compile(r'…|‥|\.\.|unnamed|illegible|lacuna|unknown|anonymous|\b(?:son|daughter|wife) of\b', re.I)


# name forms identified by hand as one person (key -> key)
SAME_PERSON = {
    'ratnakaralala': 'lalaratnakara',      # catalogue reverses the parts; Kāśī 1820-1837
    'yadolalaratnakara': 'lalaratnakara',  # B 38/11, Kāśī ŚS 1747: yadolālalaratnākarākhyaḥ
}

TITLE_ONLY = {'varma', 'varman', 'sarma', 'sarman', 'misra', 'upadhyaya', 'vajracarya', 'karmacarya',
              'josi', 'daivajna', 'thakura', 'bhata', 'bhatta'}  # a title with the name lost


def usable_name(n):
    """False for placeholders ('[unnamed]', '[lacuna]') and fragments ('…deva', '[...]sena'), which would
    otherwise fold to a bare suffix and merge with unrelated people."""
    return bool(n.strip(' .…[]/()')) and not UNUSABLE.search(n)


def name_key(n, role=''):
    k = fold(HONORIFIC.sub('', n.strip()))
    if role == 'king':  # regnal epithets: śrīśrīsumatijayajitāmitramalladeva = Jitāmitra Malla
        k = re.sub(r'^(?:sri|\s)+', '', k)
        k2 = re.sub(r'^(?:sumati\s*)?jaya[\s-]*', '', k)
        k = k2 if len(re.sub(r'[^a-z]', '', k2)) >= 6 else k  # but not Jayasiṃha -> siṃha
        k = re.sub(r'(?<=malla)\s*deva$', '', k)
        k = re.sub(r'r(?=mala$)', '', k)
        k = k.replace('bikram', 'vikram').replace('pratap ', 'pratapa').replace('bhaskara', 'bhaskara')
    # Śāha / Shah dynasty names: only an explicit separate word or 'shah' (not every name in -sa: Kālidāsa)
    k = re.sub(r'\s+(?:sah|saha|shah|sha|shaha)\s*$', 'saha', k)
    k = re.sub(r'shaha?$', 'saha', k)
    k = re.sub(r'[^a-z]', '', k)
    k = k.replace('ee', 'i').replace('oo', 'u')
    # common orthographic variation in colophon names
    k = re.sub(r'(rr)', 'r', k)
    k = re.sub(r'([kgcjtdpb])\1', r'\1', k)  # gemination after r
    k = re.sub(r'm(?=[kgcjtdpb])', 'n', k)    # anusvāra for nasal
    if role != 'king':  # caste / office suffixes are titles, not part of the name
        k2 = re.sub(r'(?:sarm(?:a|an|ma|mana)?|misra|upadhyay[a]?|vajracary[a]?|karmacary[a]?|josi|joshi|'
                    r'daivajna|thakura?|varma|varman)$', '', k)
        k = k2 if len(k2) >= 4 else k
    k = re.sub(r'malla?$', 'mala', k)
    return k


# ---------------------------------------------------------------- places
PLACE_MAP = [
    ('Bhaktapur', r'bhakta|khvapa|khopa|bhatgaon'),
    ('Patan (Lalitpur)', r'lalit|yala|patan|hnolavih|cukramah'),
    ('Kathmandu', r'kathmandu|kant[i]pur|kast[h]amand|yen\b|kathamand'),
    ('Vārāṇasī', r'kasi|varan|banaras|benares'),
    ('Gorkhā', r'gork'),
]


def norm_place(p):
    if not p:
        return ''
    f = fold(p)
    for name, pat in PLACE_MAP:
        if re.search(pat, f):
            return name
    return p.strip(' ,.')


# ---------------------------------------------------------------- colophon readings
EXTRACT = os.path.join(HERE, 'extract')
ROLE_GROUP = {'scribe': 'scribe', 'commissioner': 'patron', 'donor': 'patron', 'owner': 'patron',
              'beneficiary': 'patron', 'king': 'king', 'queen': 'king', 'relative_only': 'kin'}
GROUP_ORDER = ['scribe', 'patron', 'king', 'other', 'kin']


def reading(reel):
    """The Opus second reading if there is one, else the Gemini Flash reading, else None."""
    fid = reel.replace(' ', '_').replace('/', '-') + '.json'
    for d, src in (('out_review', 'opus'), ('out_gflash', 'flash')):
        p = os.path.join(EXTRACT, d, fid)
        if os.path.exists(p):
            o = json.load(open(p))
            o['_src'] = src
            return o
    return None


def ce_of(o):
    m = re.match(r'\s*(\d{3,4})', (o or {}).get('date', {}).get('ce_approx') or '')
    return int(m.group(1)) if m and 500 <= int(m.group(1)) <= 2030 else None


# ---------------------------------------------------------------- build
def main():
    recs = [json.loads(l) for l in open(D('records.jsonl'))]
    byreel = collections.OrderedDict()
    for r in recs:
        k = reel_key(r)
        if k in byreel:  # merge duplicate catalogue files of one reel: keep non-empty fields
            old = byreel[k]
            for f, v in r.items():
                if v and (not old.get(f) or (isinstance(v, str) and len(v) > len(old[f]) and f == 'colophon')):
                    old[f] = v
            old.setdefault('files', []).append(r['file'])
        else:
            r['files'] = [r['file']]
            byreel[k] = r

    mss = []
    att = collections.defaultdict(list)  # (kind, key) -> attestations
    local = {}                           # (ms id, local pid) -> attestation id
    rels = []                            # (ms id, from pid, type, to pid, evidence)
    for k, r in byreel.items():
        script = r.get('Script', '')
        cat_date = parse_date(r.get('Date of Copying', ''), script)
        o = reading(k)
        date, date_src = cat_date, 'catalogue'
        if (not cat_date or cat_date['inferred']) and ce_of(o):
            era = o['date']['era']
            date = {'era': era if era in ERA_OFFSET else '', 'year': o['date']['year'], 'ce': ce_of(o),
                    'inferred': era not in ERA_OFFSET}
            date_src = 'colophon'
        elif cat_date and cat_date['inferred'] and (o or {}).get('date', {}).get('era') in ERA_OFFSET \
                and o['date']['era'] != cat_date['era']:  # guessed era contradicted by the colophon: undated
            date, date_src = None, ''
        place = r.get('Place of Copying', '') or (o or {}).get('place', {}).get('normalized', '') \
            or (o or {}).get('place', {}).get('as_written', '')
        ms = {
            'id': len(mss), 'reel': k, 'title': r.get('Title', ''), 'subject': r.get('Subject', ''),
            'script': script, 'material': r.get('Material', ''),
            'date_raw': r.get('Date of Copying', '') or (o or {}).get('date', {}).get('as_written', ''),
            'date': date, 'date_src': date_src,
            'place_raw': place, 'place': norm_place(place),
            'colophon': (r.get('colophon') or '')[:1500], 'files': r['files'],
            'reading': (o or {}).get('_src', ''), 'purpose': (o or {}).get('purpose', ''),
            'notes': (o or {}).get('notes', ''),
            'review': (o or {}).get('review', {}).get('changes', []),
        }
        mss.append(ms)

        found = []  # name keys from the colophon reading, to skip duplicate catalogue-field persons
        for p in (o or {}).get('persons', []):
            roles = [x for x in p['roles'] if x not in ('author', 'commentator')]
            if not roles or not usable_name(p['name']):
                continue
            kind = 'king' if set(roles) & {'king', 'queen'} else 'person'
            key = name_key(p['name'], 'king' if kind == 'king' else '')
            if any(fold(t) == 'lala' for t in p['titles']) and not key.startswith('lala'):
                key = 'lala' + key  # Opus puts lāla in titles: (lāla) Ratnākara = Lālaratnākara
            key = SAME_PERSON.get(key, key)
            if len(key) < 3 or key in TITLE_ONLY:
                continue
            a = {'ms': ms['id'], 'name': p['name'], 'roles': roles, 'titles': p['titles'],
                 'residence': p['residence'], 'affiliation': p['affiliation'], 'evidence': p['evidence'],
                 'conf': p['confidence'], 'src': o['_src'], 'aid': len(local)}
            att[(kind, key)].append(a)
            local[(ms['id'], p['pid'])] = a['aid']
            found.append((kind, key))
        for x in (o or {}).get('relations', []):
            rels.append((ms['id'], x['from'], x['type'], x['to'], x['evidence']))

        for role, field in (('scribe', 'Scribe'), ('donor', 'Donor'), ('king', 'King')):
            for n in split_names(r.get(field, '')):
                kind = 'king' if role == 'king' else 'person'
                key = SAME_PERSON.get(name_key(n, role), name_key(n, role))
                if not usable_name(n) or len(key) < 3 or key in TITLE_ONLY or any(fk == kind and (fk2[:6] == key[:6] or key in fk2 or fk2 in key)
                                       for fk, fk2 in found):
                    continue
                att[(kind, key)].append({'ms': ms['id'], 'name': n, 'roles': [role], 'titles': [],
                                         'residence': '', 'affiliation': '', 'evidence': '', 'conf': '',
                                         'src': 'catalogue'})

    # a name recurring across centuries is several people: split a name cluster wherever
    # consecutive dated MSS are > GAP years apart or the span would exceed SPAN years
    # (undated MSS stay in the biggest sub-cluster).
    GAP, SPAN = 40, 60
    # kings attested as commissioners/owners belong with the same king's regnal attestations
    for (kind, key) in [k for k in att if k[0] == 'person']:
        keep = []
        for a in att[(kind, key)]:
            kk = name_key(a['name'], 'king')
            if ('king', kk) in att and re.search(r'(malla|deva|[sś]āha|sāha)$', a['name'].lower().replace(' ', '')):
                att[('king', kk)].append(a)
            else:
                keep.append(a)
        att[(kind, key)] = keep
    for k in [k for k, v in att.items() if not v]:
        del att[k]
    out, where = [], {}  # where: attestation id -> person id
    for (kind, key), items in att.items():
        idx = list(range(len(items)))
        dated = sorted((mss[items[j]['ms']]['date']['ce'], j) for j in idx if mss[items[j]['ms']]['date'])
        undated = [j for j in idx if not mss[items[j]['ms']]['date']]
        groups, cur = [], []
        for ce, j in dated:  # a new person after a gap, or when one career would exceed SPAN years
            if cur and (ce - cur[-1][0] > GAP or ce - cur[0][0] > SPAN):
                groups.append(cur); cur = []
            cur.append((ce, j))
        if cur:
            groups.append(cur)
        if not groups:
            groups = [[]]
        big = max(range(len(groups)), key=lambda g: len(groups[g]))
        for gi, g in enumerate(groups):
            js = [j for _, j in g] + (undated if gi == big else [])
            a = [items[j] for j in js]
            names = collections.Counter(x['name'] for x in a)
            rc = collections.Counter(ROLE_GROUP.get(ro, 'other') for x in a for ro in set(x['roles']))
            ces = [ce for ce, _ in g]
            pid = len(out)
            for x in a:
                if 'aid' in x:
                    where[x['aid']] = pid
            out.append({
                'id': pid, 'kind': kind, 'key': key, 'name': names.most_common(1)[0][0],
                'variants': sorted(names), 'ms': sorted({x['ms'] for x in a}),
                'roles': dict(rc), 'role': min(rc, key=lambda g: (-rc[g], GROUP_ORDER.index(g))),
                'titles': sorted({t for x in a for t in x['titles']}),
                'residence': sorted({x['residence'] for x in a if x['residence']}),
                'att': a, 'from': min(ces) if ces else None, 'to': max(ces) if ces else None,
                'homonym_split': len(groups) > 1,
                'places': sorted({mss[x['ms']]['place'] for x in a if mss[x['ms']]['place']}),
                'sources': sorted({x['src'] for x in a}),
            })

    relations = []
    for msid, f, typ, t, ev in rels:
        a, b = local.get((msid, f)), local.get((msid, t))
        if a and b and a in where and b in where and where[a] != where[b]:
            relations.append({'from': where[a], 'type': typ, 'to': where[b], 'ms': msid, 'evidence': ev})
    for ms in mss:
        ms['persons'] = []
    for p in out:
        for i in p['ms']:
            mss[i]['persons'].append(p['id'])

    json.dump(mss, open(D('manuscripts.json'), 'w'), ensure_ascii=False)
    json.dump(out, open(D('persons.json'), 'w'), ensure_ascii=False)
    json.dump(relations, open(D('relations.json'), 'w'), ensure_ascii=False)
    c = collections.Counter(p['role'] for p in out)
    print(f'{len(recs)} files -> {len(mss)} reels; dated {sum(1 for m in mss if m["date"])}; '
          f'persons {dict(c)}; relations {len(relations)}; '
          f'readings {dict(collections.Counter(m["reading"] for m in mss if m["reading"]))}')


if __name__ == '__main__':
    main()
