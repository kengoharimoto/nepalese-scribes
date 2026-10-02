"""Calculate the dates of the Licchavi inscriptions afresh -> data/licchavi_dates.json

The year is the editor's (the 'Saṃvat N' of the entry header), or the reading's where the header has none;
the other elements (month, pakṣa, tithi, nakṣatra, weekday) come from the reading of the inscription
(extract/out_review or out_gflash). The editors' CE equivalents are not used.
Era by year: saṃvat 300 and above is the earlier Licchavi series (LIC, saṃvat 386–535), below 300 the
Aṃśuvarman ('Mānadeva') saṃvat (AS); both are the Kārttikādi current Śaka (K. P. Malla, CNAS Journal 32.1,
2005), the second with 500 dropped: see calendar/verify.py.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'extract'))
import verify as V
import make_licchavi_worklist as W


def reading(label):
    fid = label.replace(' ', '_').replace('/', '-') + '.json'
    for d in ('out_review', 'out_gflash'):
        p = os.path.join(ROOT, 'extract', d, fid)
        if os.path.exists(p):
            return json.load(open(p)), d
    return None, None


def year_of(s):
    """'386', '300 80 6' (hundreds, tens and units written separately), '[3]98' -> int."""
    s = re.sub(r'[\[\]()]', '', str(s or ''))
    nums = [int(x) for x in re.findall(r'\d+', s)]
    if not nums:
        return None
    if len(nums) > 1 and nums[0] % 100 == 0 and all(n < nums[0] for n in nums[1:]):
        return sum(nums[:3])
    return nums[0]


def main():
    out = {}
    for e in W.entries():
        label = W.label(e['no'])
        o, src = reading(label)
        d = (o or {}).get('date', {})
        year, basis = year_of(e['samvat']), 'editor'
        ry = year_of(d.get('year'))
        if not year or (len(e['samvat']) < 3 and ry and ry > year):  # header '[3]98' or a lost hundred
            year, basis = ry, 'reading'
        if not year:
            continue
        era = 'LIC' if year >= 300 else 'AS'
        r = V.verify(era, year, d.get('month', ''), d.get('paksa', ''), d.get('tithi', ''), d.get('weekday', ''),
                     d.get('nakshatra_yoga', ''))
        if not r.get('ce'):
            continue
        r.update(basis=basis, reading=src, header=e['head'], as_written=(d.get('as_written') or '')[:300],
                 concordance=e['conc'])
        if ry and ry != year:
            r['year_conflict'] = {'editor': e['samvat'], 'reading': d.get('year')}
        out[label] = r
    json.dump(out, open(os.path.join(ROOT, 'data', 'licchavi_dates.json'), 'w'), ensure_ascii=False, indent=1)
    return out


if __name__ == '__main__':
    import collections
    res = main()
    print(len(res), 'dated inscriptions;', dict(collections.Counter(r['status'] for r in res.values())),
          dict(collections.Counter(r['given']['era'] for r in res.values())))
    for k, r in list(res.items())[:6] + [(k, r) for k, r in res.items() if r.get('year_conflict')][:8]:
        print(f"  {k:20s} {r['given']['era']} {r['given']['year']} {r.get('date', ''):10s} {r['status']:9s} {r.get('year_conflict', '')}")
