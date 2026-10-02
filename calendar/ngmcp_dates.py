"""Recalculate the dates of the NGMCP manuscripts with the pañcāṅga -> data/ngmcp_dates.json

Input: data/manuscripts.json (build_persons.py), its `date_flat` (the flat conversion: NS + 880, VS − 57, ...;
a bare 'SAM' assigned to NS or VS by year and script), and the colophon readings.
  era, year   the catalogue's Date of Copying and the colophon reading's; where they differ both are tried.
              A bare 'SAM' (era inferred) is tried as NS and as VS, so a stated weekday can decide the era.
  elements    month, pakṣa, tithi, weekday, nakṣatra from the colophon reading; where it has none, from the
              catalogue's Date of Copying (db/normalize.norm_date).
Each candidate goes through calendar/verify.py; the best is kept: verified > verified-weekday > computed >
unverified > year-only, then the standard reading before alternatives, then the catalogue's era and year.
Usage: ngmcp_dates.py [--jobs 16] [--null K]
  --null K  control run: every stated weekday is moved K days (so it is wrong); the share of dates that still
            'verify' is the chance rate of each status. Writes nothing.
"""
import argparse, json, multiprocessing as mp, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'db'))
import verify as V
from build_persons import reading, D
import normalize as NZ

RANK = {'verified': 0, 'verified-weekday': 1, 'verified-alt': 2, 'computed': 3, 'unverified': 4, 'year-only': 5}
WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
NULL = int(os.environ.get('NGMCP_DATES_NULL', '0'))


def elements(m, o):
    d = dict((o or {}).get('date', {}))
    cat = NZ.norm_date(m['date_raw'] or '', m.get('script', ''))[0] if m['date_raw'] else {}
    tithi = d.get('tithi') or (str(cat.get('tithi')) if cat.get('tithi') else '')
    return {'month': d.get('month') or cat.get('month') or '', 'paksa': d.get('paksa') or cat.get('paksa') or '',
            'tithi': tithi, 'weekday': d.get('weekday') or cat.get('weekday') or '',
            'naksatra': d.get('nakshatra_yoga') or '', 'as_written': d.get('as_written') or ''}


def candidates(m, o):
    """(era, year, basis) to try, the pipeline's own choice first."""
    out = []
    f = m['date_flat']
    fy = re.search(r'\d+', str((f or {}).get('year') or ''))
    if f and f.get('era') and fy:
        y = int(fy.group())
        out.append((f['era'], y, 'catalogue' if m['date_src'] == 'catalogue' else 'colophon'))
        if f.get('inferred'):  # bare 'SAM': let the weekday decide between NS and VS
            for era in ('NS', 'VS'):
                if era != f['era'] and 500 <= y + {'NS': 880, 'VS': -57}[era] <= 2030:
                    out.append((era, y, "bare 'saṃvat' read as " + era))
    d = (o or {}).get('date', {})
    era = V.norm_era(d.get('era') or '')
    ym = re.search(r'\d+', str(d.get('year') or ''))
    if era and ym and (era, int(ym.group())) not in [c[:2] for c in out]:
        out.append((era, int(ym.group()), 'colophon reading'))
    return out


def one(m):
    try:
        return one_(m)
    except Exception as e:  # one unreadable record must not stop the run
        return m['reel'], {'status': 'error', 'error': repr(e)[:200], 'ce': None}


def one_(m):
    o = reading(m['reel'])
    el = elements(m, o)
    if NULL:
        wd = V.norm_weekday(el['weekday'])
        el['weekday'] = WEEK[(WEEK.index(wd) + NULL) % 7] if wd else ''
    tried = []
    for i, (era, year, basis) in enumerate(candidates(m, o)):
        r = V.verify(era, year, el['month'], el['paksa'], el['tithi'], el['weekday'], el['naksatra'])
        if r.get('ce') and 500 <= r['ce'] <= 2030:
            alt = 0 if r.get('rule', 'standard') == 'standard' else 1 + ('after sunrise' in r.get('rule', ''))
            tried.append(((RANK.get(r['status'], 9), alt, i), r, basis))
    if not tried:
        return m['reel'], None
    _, r, basis = min(tried, key=lambda x: x[0])
    r.update(basis=basis, flat_ce=m['date_flat']['ce'], flat_era=m['date_flat'].get('era'),
             flat_inferred=m['date_flat'].get('inferred'), as_written=el['as_written'][:300])
    if len(tried) > 1:
        r['alternatives'] = [f"{b}: {x['given']['era']} {x['given']['year']} -> {x['status']} {x['ce']}"
                             for _, x, b in tried if x is not r]
    return m['reel'], r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jobs', type=int, default=16)
    ap.add_argument('--null', type=int, default=0)
    a = ap.parse_args()
    if a.null:
        os.environ['NGMCP_DATES_NULL'] = str(a.null)
        global NULL
        NULL = a.null
    M = json.load(open(D('manuscripts.json')))
    todo = [m for m in M if m.get('source', 'NGMCP') == 'NGMCP' and m.get('date_flat')]
    with mp.Pool(a.jobs) as pool:
        res = dict(x for x in pool.imap_unordered(one, todo, chunksize=8) if x[1])
    errors = {k: r for k, r in res.items() if r['status'] == 'error'}
    res = {k: r for k, r in res.items() if r['status'] != 'error'}
    if errors:
        print(len(errors), 'errors, e.g.', list(errors.items())[:3])
    if not a.null:
        json.dump(res, open(D('ngmcp_dates.json'), 'w'), ensure_ascii=False, indent=0)
    return res


if __name__ == '__main__':
    import collections
    res = main()
    print(len(res), 'dates;', dict(collections.Counter(r['status'] for r in res.values())))
    print('rules of verified dates:', dict(collections.Counter(r.get('rule') for r in res.values()
                                                               if r['status'].startswith('verified'))))
    ch = collections.Counter((r['status'], (r['ce'] - r['flat_ce']) if abs(r['ce'] - r['flat_ce']) <= 2 else 'big')
                             for r in res.values())
    print('CE minus flat conversion:', sorted(ch.items(), key=lambda x: (x[0][0], str(x[0][1]))))
    era = collections.Counter((r['flat_era'], r['given']['era']) for r in res.values() if r['flat_inferred'])
    print("bare 'SAM' (flat era -> chosen era):", dict(era))
