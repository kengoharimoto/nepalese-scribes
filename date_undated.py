"""Estimate dates of undated manuscripts from the dated attestations of the people and places they name.

Evidence, strongest first:
  king      the reigning king's attested span (dated MSS naming him), ± 5 years
  pair      two persons of this MS who are also named together in a dated MS: that MS's date ± 25
  person    a person's dated span ± 20 (a scribe's or patron's career); only for names that were not split
            into homonyms. Graded by what besides the name links the attestations: a shared title or
            residence ('person+'), or the name alone ('person').
  place     a specific locality (vihāra, ṭola, village; not a city) whose dated MSS fall within 150 years:
            their 10th–90th percentile range
The estimate is the intersection of the intervals of the strongest evidence available; if they do not
overlap, the king/pair evidence wins and the conflict is reported.
Output: data/estimates.json  {ms id: {from, to, conf, basis: [...], conflict}}
"""
import json, os, re, collections, statistics
from build_persons import D, fold

M = json.load(open(D('manuscripts.json')))
P = json.load(open(D('persons.json')))
CITY = re.compile(r'^(?:bhaktapur|patan|kathmandu|varanasi|nepal|kasi|lalitpur|gorkha)', re.I)
clusters_per_key = collections.Counter((p['kind'], p['key']) for p in P)


def localities(m):
    """Specific place strings attached to a manuscript: its place of copying and the residence/affiliation of its persons."""
    out = set()
    raw = [m['place_raw']] + [a.get('residence', '') for i in m['persons'] for a in P[i]['att'] if a['ms'] == m['id']] \
        + [a.get('affiliation', '') for i in m['persons'] for a in P[i]['att'] if a['ms'] == m['id']]
    for s in raw:
        for part in re.split(r'[,;/()]| in | of ', s or ''):
            k = re.sub(r'[^a-z]', '', fold(part))
            k = re.sub(r'(?:sya|sthane|nivasi|vastavya|ya|e|am)$', '', k)
            if len(k) >= 6 and not CITY.match(k):
                out.add(k)
    return out


# dated MSS per locality and per pair of persons
loc_dates, pair_dates = collections.defaultdict(list), collections.defaultdict(list)
for m in M:
    if not m['date']:
        continue
    for l in localities(m):
        loc_dates[l].append(m['date']['ce'])
    ps = sorted(set(m['persons']))
    for i in range(len(ps)):
        for j in range(i + 1, len(ps)):
            pair_dates[(ps[i], ps[j])].append(m['date']['ce'])


def att_of(p, msid):
    return next((a for a in P[p]['att'] if a['ms'] == msid), {})


def estimate(m):
    ev = []
    ps = sorted(set(m['persons']))
    for i in range(len(ps)):
        for j in range(i + 1, len(ps)):
            ds = pair_dates.get((ps[i], ps[j]))
            if ds:
                ev.append(('pair', min(ds) - 25, max(ds) + 25,
                           f"{P[ps[i]]['name']} and {P[ps[j]]['name']} are named together in a dated MS ({min(ds)}{'–' + str(max(ds)) if max(ds) > min(ds) else ''})"))
    for pid in ps:
        p = P[pid]
        if not p['from']:
            continue
        a = att_of(pid, m['id'])
        n_dated = len({x['ms'] for x in p['att'] if M[x['ms']]['date']})
        if p['kind'] == 'king' and n_dated >= 2:
            # one dated attestation is not enough: kings are also named as patrons of the text itself
            ev.append(('king', p['from'] - 5, p['to'] + 5,
                       f"king {p['name']} is attested {p['from']}–{p['to']} ({n_dated} dated MSS)"))
            continue
        if clusters_per_key[(p['kind'], p['key'])] > 1:
            continue  # a homonym: the name alone cannot say which person this is
        dated = [x for x in p['att'] if M[x['ms']]['date']]
        shared = set(a.get('titles') or []) & {t for x in dated for t in x['titles']} if isinstance(a.get('titles'), list) else set()
        res = a.get('residence') and any(x['residence'] and fold(x['residence'])[:6] == fold(a['residence'])[:6] for x in dated)
        kind = 'person+' if shared or res else 'person'
        if kind == 'person' and len(p['key']) < 7:
            continue  # short common names (Rāma, Hari, Gopāla) say too little on their own
        why = ' and '.join(filter(None, [', '.join(sorted(shared)) and 'the title ' + ', '.join(sorted(shared)),
                                        res and 'the residence']))
        ev.append((kind, p['from'] - 20, p['to'] + 20,
                   f"{p['name']} is attested {p['from']}{'–' + str(p['to']) if p['to'] > p['from'] else ''}"
                   + (f' with {why}' if why else ' (same name only)')))
    for l in localities(m):
        ds = sorted(loc_dates.get(l, []))
        if len(ds) >= 2:
            lo, hi = ds[int(.1 * (len(ds) - 1))], ds[int(.9 * (len(ds) - 1) + .999)]
            if hi - lo <= 150:
                ev.append(('place', lo - 10, hi + 10, f"{len(ds)} dated MSS of the locality '{l}' fall {lo}–{hi}"))
    if not ev:
        return None
    for tier in (('king', 'pair'), ('king', 'pair', 'person+'), ('king', 'pair', 'person+', 'person'),
                 ('king', 'pair', 'person+', 'person', 'place')):
        use = [e for e in ev if e[0] in tier]
        if use:
            break
    lo, hi = max(e[1] for e in use), min(e[2] for e in use)
    conflict = lo > hi
    if conflict:  # fall back on the strongest single kind present
        best = [e for e in use if e[0] == use[0][0]] if use[0][0] in ('king', 'pair') else use
        strong = [e for e in use if e[0] in ('king', 'pair')] or best
        lo, hi = min(e[1] for e in strong), max(e[2] for e in strong)
    kinds = {e[0] for e in use}
    conf = ('high' if kinds & {'king', 'pair'} and not conflict else
            'medium' if kinds & {'king', 'pair', 'person+'} or len(use) >= 2 else 'low')
    return {'from': lo, 'to': hi, 'conf': conf, 'conflict': conflict,
            'basis': [e[3] for e in sorted(ev, key=lambda e: ['king', 'pair', 'person+', 'person', 'place'].index(e[0]))][:8]}


est = {}
for m in M:
    if not m['date'] and m['persons']:
        e = estimate(m)
        if e:
            est[m['id']] = e
json.dump(est, open(D('estimates.json'), 'w'), ensure_ascii=False)
c = collections.Counter(e['conf'] for e in est.values())
und = sum(1 for m in M if not m['date'] and m['persons'])
print(f'{len(est)} of {und} undated MSS with persons estimated: {dict(c)}; conflicts {sum(e["conflict"] for e in est.values())}; '
      f'median width {statistics.median(e["to"] - e["from"] for e in est.values())} years')
