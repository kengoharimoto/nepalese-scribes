"""Recalculate the dates of Bendall's Cambridge manuscripts from their colophons -> data/bendall_dates.json

Bendall (1883) converted the dates himself; the Nepalese calendar was not yet well understood. Here each
colophon's own elements (era, year, month, pakṣa, tithi, weekday, nakṣatra; from the colophon reading,
extract/out_review or out_gflash, or from the quoted date where the reading left a field empty) go through
calendar/verify.py. The year: Bendall's era and year (not his A.D.) and the colophon reading's; where they
differ (an OCR digit slip, or another date in the text) both are tried, and the one whose weekday agrees
wins; with no check either way, Bendall's, since he saw the manuscript. Manuscripts whose colophon names no era (or a regnal year) keep no
recalculated date; build_persons.py then uses Bendall's date and marks it as his.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'extract'))
sys.path.insert(0, os.path.join(ROOT, 'db'))
import verify as V
import make_bendall_worklist as W


# Bendall's eras now read otherwise (his era -> (era, reason))
REATTRIBUTE = {
    'HS': ('AS', "Bendall's Harṣa era read as the Aṃśuvarman ('Mānadeva') saṃvat, i.e. the Kārttikādi Śaka with 500 dropped (Malla 2005)"),
}

# readings of a damaged or misread date element, applied before verification (field -> (value, reason))
EMEND = {
    'Cambridge Add. 1632': {'paksa': ('kṛṣṇa', "'ऽश्विनपक्षे' (OCR) read as असितपक्षे, the dark fortnight; with it the date verifies")},
}


def reading(label):
    fid = label.replace(' ', '_').replace('/', '-') + '.json'
    for d in ('out_review', 'out_gflash'):
        p = os.path.join(ROOT, 'extract', d, fid)
        if os.path.exists(p):
            return json.load(open(p)), d
    return None, None


def main():
    out = {}
    for e, p, title, text in W.units():
        label = W.label(e['add_no'], p and p['part'])
        d = p or e
        o, src = reading(label)
        cd = dict((o or {}).get('date', {}))
        aw = cd.get('as_written') or ''
        # elements the reading left empty but the quoted date has ('मिति चैत्र शुद्धि ३०', 'ज्येष्ठवदि ५')
        if aw and not cd.get('month') and V.norm_month(aw)[0] is not None:
            cd['month'] = aw
            m = re.search(V.MASA_PAT[V.norm_month(aw)[0]], V.fold(aw))
            tail = aw[m.end():] if m else aw
            cd['paksa'] = cd.get('paksa') or tail
            tm = re.search(r'(?:शु|सु|व|ब|दि|ि)\S*\s*(\d{1,2})\b', tail)
            cd['tithi'] = cd.get('tithi') or (tm.group(1) if tm else '')
        if aw and not cd.get('weekday'):
            cd['weekday'] = V.norm_weekday(aw) or ''
        emended = {}
        for k, (v, why) in EMEND.get(label, {}).items():
            cd[k] = v
            emended[k] = why
        era = V.norm_era(cd.get('era') or '')
        years = []
        if era and re.search(r'\d', str(cd.get('year') or '')):
            years.append((era, int(re.search(r'\d+', str(cd['year'])).group()), 'colophon'))
        era_note = ''
        if d.get('era') in REATTRIBUTE and d.get('era_year'):
            era2, era_note = REATTRIBUTE[d['era']]
            years = [y for y in years if y[1] != d['era_year']]  # the colophon itself names no era here
            years.insert(0, (era2, d['era_year'], "Bendall's year, era reattributed"))
        elif d.get('era') in V.OFFSET and d.get('era_year') and (d['era'], d['era_year']) not in [y[:2] for y in years]:
            years.insert(0, (d['era'], d['era_year'], "Bendall's era and year"))  # he saw the manuscript
        if not years:
            continue
        rank = {'verified': 0, 'verified-weekday': 1, 'verified-alt': 2, 'computed': 3, 'unverified': 4, 'year-only': 5}
        tried = []
        for era, year, basis in years:
            r = V.verify(era, year, cd.get('month', ''), cd.get('paksa', ''), cd.get('tithi', ''), cd.get('weekday', ''),
                         cd.get('nakshatra_yoga', ''))
            if r.get('ce'):
                tried.append((rank.get(r['status'], 9), len(tried), r, basis))
        if not tried:
            continue
        _, _, r, basis = min(tried, key=lambda x: x[:2])
        r.update(basis=basis, reading=src, bendall_ce=d.get('year_ce'), bendall_date=d.get('date_text'), as_written=aw[:300])
        if len(years) > 1:
            r['year_conflict'] = {b: f'{e} {y}' for e, y, b in years}
        if emended:
            r['emended'] = emended
        if era_note:
            r['era_note'] = era_note
        out[label] = r
    json.dump(out, open(os.path.join(ROOT, 'data', 'bendall_dates.json'), 'w'), ensure_ascii=False, indent=1)
    return out


if __name__ == '__main__':
    import collections
    res = main()
    print(len(res), 'dates;', dict(collections.Counter(r['status'] for r in res.values())))
    diff = [(k, r['bendall_ce'], r['ce'], r['status'], r.get('rule', '')) for k, r in res.items()
            if r.get('bendall_ce') and r['bendall_ce'] != r['ce']]
    print(len(diff), "differ from Bendall's A.D.:")
    for x in sorted(diff, key=lambda x: x[1]):
        print('  ', *x)
