"""Build db/ngmcp.sqlite: the NGMCP catalogue HTML entries and the NGMCP title list in one database.

  python3 db/build_db.py            (about a minute)

Sources
  /mnt2/kengo/E-texts/NGMCP/*.html        descriptive catalogue entries (parse_html.py, normalize.py)
  data/ngmcpdb_production.sql.bz2         title list database (load_sql.py), tables kept as tl_*
  data/persons.json, data/relations.json  the person register built by build_persons.py
  data/bendall1883_ocr.md                 Bendall's Cambridge catalogue (1883), OCR (bendall.py)

See db/README.md for the tables.
"""
import collections, difflib, json, os, re, sqlite3, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bendall, load_sql, parse_html as P, normalize as N  # noqa: E402

OUT = os.path.join(HERE, 'ngmcp.sqlite')
DATA = os.path.join(HERE, '..', 'data')
TL_TABLES = ['calendars', 'catalogs', 'catalog_title_relations', 'hh_scans', 'ktm_scans', 'languages',
             'language_title_relations', 'manuscripts', 'manuscript_title_relations', 'materials', 'scripts',
             'script_title_relations', 'subjects', 'subject_title_relations', 'tbt_authors', 'tbt_titles', 'titles']

SCHEMA = """
CREATE TABLE script   (code TEXT PRIMARY KEY, name TEXT, in_title_list INTEGER);
CREATE TABLE language (code TEXT PRIMARY KEY, name TEXT);
CREATE TABLE material (code TEXT PRIMARY KEY, name TEXT);
CREATE TABLE subject  (id INTEGER PRIMARY KEY, abbreviation TEXT, name TEXT);
CREATE TABLE calendar (abbreviation TEXT PRIMARY KEY, name TEXT, diff_to_ce INTEGER);

CREATE TABLE manuscript (          -- one microfilmed manuscript: series, reel, position on the reel
  id INTEGER PRIMARY KEY, series TEXT, reel INTEGER, entry INTEGER, label TEXT,
  UNIQUE (series, reel, entry));

CREATE TABLE catalogue_entry (     -- one catalogue HTML file
  id INTEGER PRIMARY KEY, file TEXT UNIQUE, manuscript_id INTEGER REFERENCES manuscript(id),
  series TEXT, reel INTEGER, entry INTEGER, marker TEXT, label TEXT, reel_source TEXT,
  preferred INTEGER, duplicate_of INTEGER,
  title TEXT, alt_title TEXT, author TEXT, commentator TEXT,
  subject_raw TEXT, language_raw TEXT, language_codes TEXT,
  script_raw TEXT, script_codes TEXT, script_style TEXT,
  material_raw TEXT, material_code TEXT REFERENCES material(code), paper_origin TEXT, format TEXT,
  state_raw TEXT, complete INTEGER, damaged INTEGER,
  size_raw TEXT, width_cm REAL, height_cm REAL,
  binding_hole_raw TEXT, binding_holes INTEGER,
  folios_raw TEXT, folio_count INTEGER, counted_in_pages INTEGER,
  lines_raw TEXT, lines_min INTEGER, lines_max INTEGER,
  foliation TEXT, marginal_title TEXT, illustrations TEXT,
  scribe TEXT, date_of_copying_raw TEXT, era TEXT, era_year INTEGER, year_ce INTEGER, era_inferred INTEGER,
  date_uncertain INTEGER, month TEXT, paksa TEXT, tithi INTEGER, weekday TEXT,
  place_of_copying TEXT, king TEXT, donor TEXT, owner_deliverer TEXT, owner_of_ms TEXT,
  place_of_deposit_raw TEXT, place_of_deposit TEXT, accession_no_raw TEXT, acc1 INTEGER, acc2 INTEGER,
  inventory_no_raw TEXT, inventory_no INTEGER, inventory_new INTEGER, mtm_inventory_no TEXT, mtm_title TEXT,
  remarks TEXT, text_features TEXT, reference TEXT, acknowledgement TEXT,
  edited_ms_raw TEXT, edited INTEGER, used_for_edition TEXT, manuscript_features TEXT, stamp TEXT,
  mf_reel_no TEXT, mf_remarks TEXT, date_of_filming_raw TEXT, date_of_filming TEXT,
  exposures_raw TEXT, exposures INTEGER, slides TEXT, used_copy_raw TEXT, used_copy TEXT,
  type_of_film_raw TEXT, type_of_film TEXT,
  catalogued_by TEXT, catalogue_date_raw TEXT, catalogue_date TEXT, catalogue_note TEXT, bibliography TEXT,
  colophon TEXT);
CREATE TABLE catalogue_reel     (entry_id INTEGER, series TEXT, reel INTEGER, entry INTEGER, marker TEXT,
                                 relation TEXT, source TEXT);
CREATE TABLE catalogue_script   (entry_id INTEGER, code TEXT, PRIMARY KEY (entry_id, code));
CREATE TABLE catalogue_language (entry_id INTEGER, code TEXT, PRIMARY KEY (entry_id, code));
CREATE TABLE catalogue_subject  (entry_id INTEGER, subject_id INTEGER, PRIMARY KEY (entry_id, subject_id));
CREATE TABLE excerpt (id INTEGER PRIMARY KEY, entry_id INTEGER, seq INTEGER, kind TEXT, label TEXT,
                      text TEXT, locus TEXT);
CREATE TABLE issue (entry_id INTEGER, field TEXT, problem TEXT, raw_value TEXT);

CREATE TABLE title (               -- one text in the title list (tl_titles), decoded
  id INTEGER PRIMARY KEY, manuscript_id INTEGER REFERENCES manuscript(id), title TEXT,
  material_code TEXT, material_uncertain INTEGER, complete INTEGER, damaged INTEGER,
  script_codes TEXT, language_codes TEXT, folio_count INTEGER, width_cm REAL, height_cm REAL,
  era TEXT, era_year INTEGER, year_ce INTEGER, date_uncertain INTEGER, acc1 INTEGER, acc2 INTEGER,
  mtm INTEGER, identical_with INTEGER, catalogued INTEGER, remarks TEXT);
CREATE TABLE title_subject (title_id INTEGER, subject_id INTEGER, PRIMARY KEY (title_id, subject_id));

CREATE TABLE entry_title (         -- which title-list text a catalogue entry describes
  entry_id INTEGER, title_id INTEGER, method TEXT, score REAL, PRIMARY KEY (entry_id, title_id));

CREATE TABLE discrepancy (entry_id INTEGER, title_id INTEGER, field TEXT, catalogue_value TEXT,
                          titlelist_value TEXT);

CREATE TABLE same_manuscript (     -- two microfilm positions that show the same manuscript (a < b)
  manuscript_a INTEGER, manuscript_b INTEGER, label_a TEXT, label_b TEXT, source TEXT, uncertain INTEGER,
  evidence TEXT);
CREATE TABLE filming_group (       -- all positions of one manuscript filmed more than once
  group_id INTEGER, manuscript_id INTEGER, label TEXT, date_of_filming TEXT, seq INTEGER, order_basis TEXT,
  suspect INTEGER,   -- the group puts two positions of one reel together: some link is probably wrong
  PRIMARY KEY (group_id, manuscript_id));

CREATE TABLE bendall_entry (       -- Bendall 1883, Cambridge University Library Add. MSS
  add_no TEXT PRIMARY KEY, add_num INTEGER, pdf_page INTEGER, title TEXT, description TEXT,
  material TEXT, leaves INTEGER, lines_min INTEGER, lines_max INTEGER, width_in REAL, height_in REAL,
  width_cm REAL, height_cm REAL, hand TEXT, date_text TEXT, era TEXT, era_year INTEGER, year_ce INTEGER,
  century INTEGER, n_parts INTEGER, pages_out_of_order INTEGER, text TEXT);
CREATE TABLE bendall_part (        -- the numbered works of a composite entry (Add. 1680 I-XXX ...)
  add_no TEXT, part INTEGER, part_to INTEGER, title TEXT, description TEXT, material TEXT, leaves INTEGER,
  lines_min INTEGER, lines_max INTEGER, width_in REAL, height_in REAL, hand TEXT, date_text TEXT, era TEXT,
  era_year INTEGER, year_ce INTEGER, century INTEGER, text TEXT, PRIMARY KEY (add_no, part));
CREATE TABLE bendall_excerpt (add_no TEXT, part INTEGER, seq INTEGER, kind TEXT, label TEXT, text TEXT);
CREATE TABLE bendall_date (        -- dates recalculated from the colophons (calendar/bendall_dates.py)
  label TEXT PRIMARY KEY, add_no TEXT, part INTEGER, status TEXT, rule TEXT, date TEXT, year_ce INTEGER,
  era TEXT, era_year INTEGER, month TEXT, paksa TEXT, tithi INTEGER, weekday TEXT, naksatra TEXT,
  computed_weekday TEXT, computed_tithi INTEGER, computed_naksatra TEXT, saka INTEGER, ambiguous INTEGER,
  bendall_ce INTEGER, bendall_date TEXT, basis TEXT, year_conflict TEXT, emended TEXT,  -- emendations, era reattributions
  as_written TEXT);
CREATE TABLE ngmcp_date (          -- NGMCP dates recalculated with the pañcāṅga (calendar/ngmcp_dates.py)
  label TEXT PRIMARY KEY, manuscript_id INTEGER, status TEXT, rule TEXT, date TEXT, year_ce INTEGER,
  era TEXT, era_year INTEGER, month TEXT, paksa TEXT, tithi INTEGER, weekday TEXT, naksatra TEXT,
  computed_weekday TEXT, computed_tithi INTEGER, computed_naksatra TEXT, saka INTEGER, ambiguous INTEGER,
  flat_ce INTEGER, flat_era TEXT, basis TEXT, possible TEXT, alternatives TEXT, as_written TEXT);
CREATE TABLE licchavi_inscription (  -- E-texts/1_sanskr/7_inscriptions/licchavi, one row per inscription
  no INTEGER PRIMARY KEY, label TEXT, file TEXT, header TEXT, samvat TEXT, gnoli TEXT, dv TEXT, hj TEXT, regmi TEXT,
  era TEXT, era_year INTEGER, date TEXT, year_ce INTEGER, status TEXT, rule TEXT, month TEXT, paksa TEXT, tithi INTEGER,
  weekday TEXT, naksatra TEXT, computed_weekday TEXT, computed_naksatra TEXT, as_written TEXT, text TEXT);
CREATE TABLE bendall_ngmcp_title ( -- NGMCP texts with the same title (the same work, not the same MS)
  add_no TEXT, part INTEGER, bendall_title TEXT, title_id INTEGER, ngmcp_title TEXT);

CREATE TABLE person (id INTEGER PRIMARY KEY, kind TEXT, key TEXT, name TEXT, role TEXT, variants TEXT,
                     titles TEXT, residence TEXT, first_ce INTEGER, last_ce INTEGER);
CREATE TABLE attestation (person_id INTEGER, manuscript_id INTEGER, label TEXT, name TEXT, roles TEXT,
                          titles TEXT, residence TEXT, affiliation TEXT, evidence TEXT, confidence TEXT,
                          source TEXT);
CREATE TABLE person_relation (from_person INTEGER, type TEXT, to_person INTEGER, label TEXT, evidence TEXT);
"""

TITLE_STATE = {'C': ('complete', 1), 'I': ('complete', 0), 'D': ('damaged', 1), 'U': ('damaged', 0)}


def iso(r, k):
    return r.get(k) or ''


def locus(text):
    m = re.search(r'\(((?:fols?|exps?|f)\.?\s*[^()]{1,40})\)\s*$', text)
    return m.group(1) if m else None


def build():
    if os.path.exists(OUT):
        os.remove(OUT)
    con = load_sql.load(OUT)
    for t in [r[0] for r in con.execute("select name from sqlite_master where type='table'")]:
        if t in TL_TABLES:
            con.execute(f'ALTER TABLE "{t}" RENAME TO "tl_{t}"')
        else:
            con.execute(f'DROP TABLE "{t}"')  # backup copies in the dump (catalogsCopy, *_copy)
    con.executescript(SCHEMA)

    # ------------------------------------------------------------ vocabularies
    tl_scripts = {a for (a,) in con.execute('select abbreviation from tl_scripts') if a}
    con.executemany('INSERT INTO script VALUES (?,?,?)',
                    [(c, n, int(c in tl_scripts)) for c, (n, _) in N.SCRIPTS.items()] +
                    [(a, n, 1) for a, n in con.execute('select abbreviation, name from tl_scripts')
                     if a and a not in N.SCRIPTS])
    con.executemany('INSERT INTO language VALUES (?,?)',
                    [(a, n) for a, n in con.execute('select abbreviation, name from tl_languages') if a])
    con.executemany('INSERT INTO material VALUES (?,?)', list(N.MATERIALS.items()) +
                    [(a, d) for a, d in con.execute('select abbreviation, description from tl_materials')
                     if a not in N.MATERIALS])
    con.execute('INSERT INTO subject SELECT id, abbreviation, subject FROM tl_subjects')
    con.execute("INSERT INTO calendar SELECT abbreviation, description, diff_to_ce FROM tl_calendars")
    subjects = N.Subjects(con.execute('select id, abbreviation, name from subject').fetchall())

    manuscripts = {}

    def ms_id(series, reel, entry):
        if series is None or reel is None or entry is None:
            return None
        k = (series, reel, entry)
        if k not in manuscripts:
            manuscripts[k] = len(manuscripts) + 1
        return manuscripts[k]

    # ------------------------------------------------------------ catalogue entries
    files = sorted(f for f in os.listdir(P.SRC) if f.endswith('.html'))
    entries, issues = [], []
    for eid, f in enumerate(files, 1):
        r = P.parse(f)
        e = {'id': eid, 'file': f}
        iss = []
        refs = N.reels(r.get('reel_no', ''))
        fref = N.reel_from_file(f)
        src = 'reel_no'
        if not refs and fref:
            refs, src = [dict(fref, rel='primary')], 'file'
            iss.append(('reel_no', 'reel number not readable; taken from the file name'))
        elif refs and fref and (refs[0]['series'], refs[0]['reel'], refs[0]['entry']) != \
                (fref['series'], fref['reel'], fref['entry']) and \
                not any((x['series'], x['reel'], x['entry']) == (fref['series'], fref['reel'], fref['entry']) for x in refs):
            iss.append(('reel_no', f'file name has {N.reel_label(**fref)}'))
        p = refs[0] if refs else {}
        e.update(series=p.get('series'), reel=p.get('reel'), entry=p.get('entry'), marker=p.get('marker') or '',
                 reel_source=src if refs else None)
        e['label'] = N.reel_label(e['series'], e['reel'], e['entry'], e['marker']) if refs else None
        e['manuscript_id'] = ms_id(e['series'], e['reel'], e['entry'])
        e['_reels'] = [(x['series'], x['reel'], x['entry'], x['marker'], x['rel'], 'reel_no' if src == 'reel_no' else 'file')
                       for x in refs]
        e['_reels'] += [(x['series'], x['reel'], x['entry'], x['marker'], 'microfilm', 'mf_reel_no')
                        for x in N.reels(r.get('mf_reel_no', ''))
                        if (x['series'], x['reel'], x['entry']) not in {(y[0], y[1], y[2]) for y in e['_reels']}]

        for k in ('title', 'alt_title', 'author', 'commentator', 'foliation', 'marginal_title', 'illustrations',
                  'scribe', 'place_of_copying', 'king', 'donor', 'owner_deliverer', 'owner_of_ms',
                  'mtm_inventory_no', 'mtm_title', 'remarks', 'text_features', 'reference', 'acknowledgement',
                  'used_for_edition', 'manuscript_features', 'stamp', 'mf_reel_no', 'mf_remarks', 'slides',
                  'catalogued_by', 'catalogue_note', 'bibliography'):
            e[k] = r.get(k) or None
        raw = {'subject_raw': 'subject', 'language_raw': 'language', 'script_raw': 'script',
               'material_raw': 'material', 'state_raw': 'state', 'size_raw': 'size', 'binding_hole_raw': 'binding_hole',
               'folios_raw': 'folios', 'lines_raw': 'lines_per_folio', 'date_of_copying_raw': 'date_of_copying',
               'place_of_deposit_raw': 'place_of_deposit', 'accession_no_raw': 'accession_no',
               'inventory_no_raw': 'inventory_no', 'edited_ms_raw': 'edited_ms', 'date_of_filming_raw': 'date_of_filming',
               'exposures_raw': 'exposures', 'used_copy_raw': 'used_copy', 'type_of_film_raw': 'type_of_film',
               'catalogue_date_raw': 'catalogue_date'}
        for k, src_k in raw.items():
            e[k] = r.get(src_k) or None
        for fn, k in ((N.norm_script, 'script'), (N.norm_language, 'language'), (N.norm_material, 'material'),
                      (N.norm_state, 'state'), (N.norm_size, 'size'), (N.norm_folios, 'folios'),
                      (N.norm_lines, 'lines_per_folio'), (N.norm_binding, 'binding_hole'),
                      (N.norm_inventory, 'inventory_no')):
            o, i = fn(r.get(k, ''))
            e.update(o)
            iss += i
        o, i = N.norm_date(r.get('date_of_copying', ''), r.get('script', ''))
        e.update(o)
        iss += i
        e.update(N.norm_accession(r.get('accession_no', '')))
        e['place_of_deposit'] = N.norm_deposit(r.get('place_of_deposit', ''))
        e['edited'] = N.norm_yesno(r.get('edited_ms', ''))
        for k in ('date_of_filming', 'catalogue_date'):
            e[k], i = N.norm_day(r.get(k, ''), k)
            iss += i
        e['exposures'] = N.first_int(r.get('exposures', ''))
        e['used_copy'] = N.norm_used_copy(r.get('used_copy', ''))
        e['type_of_film'] = N.norm_film(r.get('type_of_film', ''))
        e['_subjects'], i = subjects(r.get('subject', ''))
        iss += i
        if e['scribe'] and len(e['scribe']) > 80:
            iss.append(('scribe', 'long text in the Scribe field (probably a note)'))
        e['_excerpts'] = r['excerpts']
        cols = [x for x in r['excerpts'] if x['kind'] == 'colophon']
        e['colophon'] = ' ‖ '.join(x['text'] for x in cols) or None
        issues += [(eid, fld, prob, (r.get(fld) or '')[:300]) for fld, prob in iss]
        entries.append(e)

    # duplicates: several files for one reel position; prefer the fullest, then the latest catalogued
    groups = collections.defaultdict(list)
    for e in entries:
        groups[(e['series'], e['reel'], e['entry'], e['marker']) if e['label'] else e['file']].append(e)
    for g in groups.values():
        def fullness(e):
            return (sum(1 for k, v in e.items() if v not in (None, '', 0) and not k.startswith('_')),
                    len(e['_excerpts']), e['catalogue_date'] or '', -e['id'])
        g.sort(key=fullness, reverse=True)
        for i, e in enumerate(g):
            e['preferred'] = int(i == 0)
            e['duplicate_of'] = g[0]['id'] if i else None

    cols = [c[1] for c in con.execute('PRAGMA table_info(catalogue_entry)')]
    con.executemany(f'INSERT INTO catalogue_entry VALUES ({",".join("?" * len(cols))})',
                    [[e.get(c) for c in cols] for e in entries])
    con.executemany('INSERT INTO catalogue_reel VALUES (?,?,?,?,?,?,?)',
                    [(e['id'],) + x for e in entries for x in e['_reels']])
    con.executemany('INSERT INTO catalogue_script VALUES (?,?)',
                    [(e['id'], c) for e in entries for c in (e['script_codes'] or '').split()])
    con.executemany('INSERT INTO catalogue_language VALUES (?,?)',
                    [(e['id'], c) for e in entries for c in (e['language_codes'] or '').split()])
    con.executemany('INSERT INTO catalogue_subject VALUES (?,?)',
                    [(e['id'], s) for e in entries for s in e['_subjects']])
    con.executemany('INSERT INTO excerpt (entry_id, seq, kind, label, text, locus) VALUES (?,?,?,?,?,?)',
                    [(e['id'], i, x['kind'], x['label'], x['text'], locus(x['text']))
                     for e in entries for i, x in enumerate(e['_excerpts'], 1)])
    con.executemany('INSERT INTO issue VALUES (?,?,?,?)', issues)

    # ------------------------------------------------------------ title list, decoded
    cal = {a.upper(): d for a, d in con.execute('select abbreviation, diff_to_ce from tl_calendars')}
    titles = []
    for row in con.execute('''select id, title, material, state, script, language, microfilm_series, microfilm_reel,
            microfilm_entry, folio_count, size_x, size_y, _calendar, year, common_era, date_uncertain, acc1, acc2,
            mtm, identical_with, catalogued, remarks, material_uncertain, era_conjectured, calendar_id from tl_titles'''):
        (tid, title, mat, state, script, lang, se, re_, en, fc, sx, sy, calname, year, ce, du, a1, a2, mtm, ident,
         catd, rem, mu, conj, cal_id) = row
        t = {'id': tid, 'title': title, 'manuscript_id': ms_id(se, re_, en) if se and se not in '0?' else None}
        m = (mat or '').strip()
        t['material_code'] = 'paper' if not m else m.rstrip('?') if m.rstrip('?') in N.MATERIALS or m.rstrip('?') in 'LXCS' else m
        t['material_uncertain'] = int(m.endswith('?') or bool(mu))
        st = (state or '').upper()
        t['complete'] = 1 if 'C' in st else 0 if 'I' in st else None
        t['damaged'] = 1 if 'D' in st else 0 if 'U' in st else None
        t['script_codes'] = ' '.join(c for c in (script or '') if c.isalpha() and c.isupper()) or None
        t['language_codes'] = ' '.join(c for c in (lang or '') if c.isalpha() and c.isupper()) or None
        t['folio_count'] = fc if fc and fc > 0 else None
        t['width_cm'], t['height_cm'] = (sx if sx and sx > 0 else None), (sy if sy and sy > 0 else None)
        era = (calname or '').upper().rstrip('XY').replace('ŚS', 'ŚS')
        era = 'ŚS' if era in ('ŚS', 'SS') else era
        t['era'] = era or None
        t['era_year'] = year
        t['year_ce'] = ce or (year + cal[era] if year and cal.get(era) is not None else None)
        t['date_uncertain'] = int(bool(du) or bool(conj) or (calname or '').upper().endswith(('X', 'Y')))
        if cal_id == 7 or era == 'MS':  # 'Mānadeva saṃvat' = Aṃśuvarman's Kārttikādi Śaka − 500 (calendar/verify.py)
            t['era'] = 'AS'
            t['year_ce'] = year + 577 if year and year <= 320 else None  # NS 1 = AS 304; D 41/7 'MS 901' is not AS
            t['date_uncertain'] = 1
        t.update(acc1=a1, acc2=a2, mtm=mtm or None, identical_with=ident, catalogued=catd, remarks=rem)
        titles.append(t)
    tcols = [c[1] for c in con.execute('PRAGMA table_info(title)')]
    con.executemany(f'INSERT INTO title VALUES ({",".join("?" * len(tcols))})', [[t.get(c) for c in tcols] for t in titles])
    con.execute('INSERT OR IGNORE INTO title_subject SELECT title_id, subject_id FROM tl_subject_title_relations '
                'WHERE subject_id IS NOT NULL')
    con.executemany('INSERT INTO manuscript VALUES (?,?,?,?,?)',
                    [(i, s, r, n, f'{s} {r}/{n}') for (s, r, n), i in manuscripts.items()])

    # ------------------------------------------------------------ catalogue entry <-> title list
    by_ms = collections.defaultdict(list)
    for t in titles:
        if t['manuscript_id']:
            by_ms[t['manuscript_id']].append(t)
    canon = {}
    for cid, se, re_, num, mk, fn in con.execute('select id, series, reel, number, marker, file_name from tl_catalogs'):
        canon[(se, re_, num, mk or '')] = cid
    cat_titles = collections.defaultdict(list)
    for cid, tid in con.execute('select catalog_id, title_id from tl_catalog_title_relations'):
        cat_titles[cid].append(tid)
    tit = {t['id']: t for t in titles}

    def sim(a, b):
        fa, fb = re.sub(r'[^a-z]', '', N.fold(a)), re.sub(r'[^a-z]', '', N.fold(b))
        return difflib.SequenceMatcher(None, fa, fb).ratio() if fa and fb else 0.0

    # Within one manuscript, pair catalogue entries and title-list texts one to one by title similarity.
    # The title list's own catalog links tie every part of a multiple-text manuscript (A 981/19ag) to all its
    # texts, so they only widen the candidates; an entry left unpaired is linked to its single candidate, or
    # marked as part of a multiple-text manuscript (folio counts there describe the whole bundle).
    links = []
    ents_by_ms = collections.defaultdict(list)
    for e in entries:
        if e['manuscript_id'] and e['preferred']:
            ents_by_ms[e['manuscript_id']].append(e)
    for msid, ents in ents_by_ms.items():
        cand = {t['id']: t for t in by_ms.get(msid, [])}
        for e in ents:
            cid = canon.get((e['series'], e['reel'], e['entry'], e['marker']))
            cand.update({tid: tit[tid] for tid in cat_titles.get(cid, []) if tid in tit})
        pairs = sorted(((sim(e['title'] or '', t['title'] or ''), e['id'], t['id']) for e in ents for t in cand.values()),
                       reverse=True)
        done_e, done_t = set(), set()
        for sc, eid, tid in pairs:
            if sc < 0.6:
                break
            if eid in done_e or tid in done_t:
                continue
            links.append((eid, tid, 'title match', round(sc, 3)))
            done_e.add(eid)
            done_t.add(tid)
        for e in ents:
            if e['id'] in done_e:
                continue
            cid = canon.get((e['series'], e['reel'], e['entry'], e['marker']))
            own = [tid for tid in cat_titles.get(cid, []) if tid in tit]
            if len(own) == 1 and own[0] not in done_t:
                tid, how = own[0], 'title list catalog link'
            elif len(ents) == 1 and len(cand) == 1:
                tid, how = next(iter(cand)), 'only title at this reel position'
            elif cand:
                tid = max(cand, key=lambda t: sim(e['title'] or '', cand[t]['title'] or ''))
                how = 'part of a multiple-text manuscript'
            else:
                continue
            links.append((e['id'], tid, how, round(sim(e['title'] or '', tit[tid]['title'] or ''), 3)))
    # duplicate catalogue files follow their preferred file
    first = {}
    for eid, tid, how, sc in links:
        first.setdefault(eid, (tid, how, sc))
    for e in entries:
        if e['duplicate_of'] and e['duplicate_of'] in first:
            tid, how, sc = first[e['duplicate_of']]
            links.append((e['id'], tid, how, sc))
    con.executemany('INSERT OR IGNORE INTO entry_title VALUES (?,?,?,?)', links)

    # ------------------------------------------------------------ discrepancies between the two sources
    eby = {e['id']: e for e in entries}
    disc = []
    for eid, tid, method, sc in links:
        e, t = eby[eid], tit[tid]
        if e['duplicate_of']:
            continue
        if method == 'part of a multiple-text manuscript':
            continue
        if e['folio_count'] and t['folio_count'] and e['folio_count'] != t['folio_count']:
            disc.append((eid, tid, 'folio_count', e['folio_count'], t['folio_count']))
        if e['width_cm'] and t['width_cm'] and (abs(e['width_cm'] - t['width_cm']) > 1.0 or
                                                abs((e['height_cm'] or 0) - (t['height_cm'] or 0)) > 1.0):
            disc.append((eid, tid, 'size', f"{e['width_cm']} x {e['height_cm']}", f"{t['width_cm']} x {t['height_cm']}"))
        if e['year_ce'] and t['year_ce'] and abs(e['year_ce'] - t['year_ce']) > 1:
            disc.append((eid, tid, 'date', f"{e['era']} {e['era_year']} = {e['year_ce']}",
                         f"{t['era']} {t['era_year']} = {t['year_ce']}"))
        if e['material_code'] and t['material_code'] and e['material_code'] != t['material_code']:
            disc.append((eid, tid, 'material', e['material_code'], t['material_code']))
        es, ts = set((e['script_codes'] or '').split()), set((t['script_codes'] or '').split()) - {'U'}
        if es and ts and not es & ts:
            disc.append((eid, tid, 'script', e['script_codes'], t['script_codes']))
        if e['acc1'] and t['acc1'] and (e['acc1'], e['acc2']) != (t['acc1'], t['acc2']):
            disc.append((eid, tid, 'accession_no', f"{e['acc1']}/{e['acc2']}", f"{t['acc1']}/{t['acc2']}"))
        if sc < 0.5:
            disc.append((eid, tid, 'title', e['title'], t['title']))
    con.executemany('INSERT INTO discrepancy VALUES (?,?,?,?,?)', disc)

    # ------------------------------------------------------------ Bendall's Cambridge catalogue (1883)
    if os.path.exists(bendall.SRC):
        bes = bendall.parse()
        cm = lambda v: round(v * 2.54, 1) if v else None
        con.executemany('INSERT INTO bendall_entry VALUES (' + ','.join('?' * 22) + ')', [
            (e['add_no'], e['add_num'], e['pdf_page'], e['title'], e['description'], e['material'], e['leaves'],
             e['lines_min'], e['lines_max'], e['width_in'], e['height_in'], cm(e['width_in']), cm(e['height_in']),
             e['hand'], e['date_text'], e['era'], e['era_year'], e['year_ce'], e['century'], len(e['parts']),
             e['pages_out_of_order'], e['text']) for e in bes])
        con.executemany('INSERT INTO bendall_part VALUES (' + ','.join('?' * 18) + ')', [
            (e['add_no'], p['part'], p['part_to'], p['title'], p['description'], p['material'], p['leaves'],
             p['lines_min'], p['lines_max'], p['width_in'], p['height_in'], p['hand'], p['date_text'], p['era'],
             p['era_year'], p['year_ce'], p['century'], p['text']) for e in bes for p in e['parts']])
        con.executemany('INSERT INTO bendall_excerpt VALUES (?,?,?,?,?,?)', [
            (e['add_no'], x['part'], i, x['kind'], x['label'], x['text'])
            for e in bes for i, x in enumerate(e['excerpts'], 1)])
        # same work in the NGMCP title list, by a folded title key (Bendall writes ç, sh, ṛi for ś, ṣ, ṛ)
        def tkey(t):
            t = re.sub(r'^(?:fragments? of (?:the |an? )?|leaf of (?:the |an? )?|first .*? of the |part of (?:the |an? )?)',
                       '', (t or '').strip(), flags=re.I)
            t = re.split(r'\s+by\s+|,|\(|;|\bwith\b', t)[0]
            t = t.replace('Ç', 'Ś').replace('ç', 'ś').replace('SH', 'Ṣ').replace('sh', 'ṣ').replace('Sh', 'Ṣ')
            t = re.sub(r'ṚI|ṛi', 'ṛ', t)
            return re.sub(r'[^a-z]', '', N.fold(t))
        tl_by_key = collections.defaultdict(list)
        for t in titles:
            k = tkey(t['title'])
            if len(k) >= 5:
                tl_by_key[k].append(t)
        rows = []
        for e in bes:
            for part, ttl in ([(None, e['title'])] if not e['parts'] else [(p['part'], p['title']) for p in e['parts']]):
                for one in (ttl or '').split(' | '):
                    for t in tl_by_key.get(tkey(one), []):
                        rows.append((e['add_no'], part, one, t['id'], t['title']))
        con.executemany('INSERT INTO bendall_ngmcp_title VALUES (?,?,?,?,?)', rows)
        dpath = os.path.join(DATA, 'bendall_dates.json')
        roman = {v: i for i, v in enumerate(['', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII',
                                              'XIII', 'XIV', 'XV', 'XVI', 'XVII', 'XVIII', 'XIX', 'XX', 'XXI', 'XXII',
                                              'XXIII', 'XXIV', 'XXV', 'XXVI', 'XXVII', 'XXVIII', 'XXIX', 'XXX'])}
        drows = []
        for label, r in (json.load(open(dpath)).items() if os.path.exists(dpath) else []):
            m = re.match(r'Cambridge Add\. (\S+)(?: \((\w+)\))?', label)
            g, c = r.get('given', {}), r.get('computed', {})
            drows.append((label, m.group(1), roman.get(m.group(2)) if m.group(2) else None, r['status'], r.get('rule'),
                          r.get('date'), r['ce'], g.get('era'), g.get('year'), g.get('masa'), g.get('paksa'), g.get('tithi'),
                          g.get('weekday'), g.get('naksatra'), c.get('weekday'), c.get('tithi'), c.get('naksatra'),
                          c.get('saka'), int(bool(r.get('ambiguous'))), r.get('bendall_ce'), r.get('bendall_date'),
                          r.get('basis'), json.dumps(r['year_conflict'], ensure_ascii=False) if r.get('year_conflict') else None,
                          '; '.join(x for x in (json.dumps(r['emended'], ensure_ascii=False) if r.get('emended') else '',
                                                r.get('era_note', '')) if x) or None, r.get('as_written')))
        con.executemany('INSERT INTO bendall_date VALUES (' + ','.join('?' * 25) + ')', drows)

    # ------------------------------------------------------------ NGMCP dates recalculated with the pañcāṅga
    npath = os.path.join(DATA, 'ngmcp_dates.json')
    nrows = []
    for label, r in (json.load(open(npath)).items() if os.path.exists(npath) else []):
        rr = N.reels(label)
        g, c = r.get('given', {}), r.get('computed', {})
        nrows.append((label, ms_id(rr[0]['series'], rr[0]['reel'], rr[0]['entry']) if rr else None, r['status'],
                      r.get('rule'), r.get('date'), r['ce'], g.get('era'), g.get('year'), g.get('masa'), g.get('paksa'),
                      g.get('tithi'), g.get('weekday'), g.get('naksatra'), c.get('weekday'), c.get('tithi'),
                      c.get('naksatra'), c.get('saka'), int(bool(r.get('ambiguous'))), r.get('flat_ce'), r.get('flat_era'),
                      r.get('basis'), ', '.join(r.get('possible', [])) or None,
                      ' | '.join(r.get('alternatives', [])) or None, r.get('as_written')))
    con.executemany('INSERT INTO ngmcp_date VALUES (' + ','.join('?' * 24) + ')', nrows)

    # ------------------------------------------------------------ Licchavi inscriptions
    sys.path.insert(0, os.path.join(HERE, '..', 'extract'))
    try:
        import make_licchavi_worklist as LW
        lent = LW.entries()
    except Exception:
        lent = []
    lpath = os.path.join(DATA, 'licchavi_dates.json')
    ldates = json.load(open(lpath)) if os.path.exists(lpath) else {}
    lrows = []
    for e in lent:
        r = ldates.get(LW.label(e['no']), {})
        g, c = r.get('given', {}), r.get('computed', {})
        lrows.append((e['no'], LW.label(e['no']), e['file'], e['head'], e['samvat'], e['conc'].get('Gn'), e['conc'].get('DV'),
                      e['conc'].get('HJ'), e['conc'].get('R'), g.get('era'), g.get('year'), r.get('date'), r.get('ce'),
                      r.get('status'), r.get('rule'), g.get('masa'), g.get('paksa'), g.get('tithi'), g.get('weekday'),
                      g.get('naksatra'), c.get('weekday'), c.get('naksatra'), r.get('as_written'), e['text']))
    con.executemany('INSERT INTO licchavi_inscription VALUES (' + ','.join('?' * 24) + ')', lrows)

    # ------------------------------------------------------------ person register (build_persons.py)
    try:
        mss = json.load(open(os.path.join(DATA, 'manuscripts.json')))
        persons = json.load(open(os.path.join(DATA, 'persons.json')))
        rels = json.load(open(os.path.join(DATA, 'relations.json')))
    except FileNotFoundError:
        mss = persons = rels = []
    ms_label = {m['id']: m['reel'] for m in mss}

    def label_ms(label):
        rr = N.reels(label)
        return ms_id(rr[0]['series'], rr[0]['reel'], rr[0]['entry']) if rr else None

    prow, arow = [], []
    for p in persons:
        prow.append((p['id'], p.get('kind'), p.get('key'), p.get('name'), p.get('role'),
                     ' | '.join(p.get('variants', [])), ', '.join(p.get('titles', [])),
                     ', '.join(p.get('residence', [])), p.get('from'), p.get('to')))
        for a in p.get('att', []):
            lab = ms_label.get(a['ms'])
            arow.append((p['id'], label_ms(lab) if lab else None, lab, a.get('name'), ', '.join(a.get('roles', [])),
                         ', '.join(a.get('titles', [])), a.get('residence'), a.get('affiliation'), a.get('evidence'),
                         a.get('conf'), a.get('src')))
    con.executemany('INSERT INTO person VALUES (?,?,?,?,?,?,?,?,?,?)', prow)
    con.executemany('INSERT INTO attestation VALUES (?,?,?,?,?,?,?,?,?,?,?)', arow)
    con.executemany('INSERT INTO person_relation VALUES (?,?,?,?,?)',
                    [(r['from'], r['type'], r['to'], ms_label.get(r.get('ms')), r.get('evidence')) for r in rels])
    # ------------------------------------------------------------ manuscripts filmed more than once
    # Evidence: the title list's identical_with, «A 1/1 = A 3/1» in the catalogue's Reel No., and remarks
    # ('identical with A 1336/7', '= A 38/15', 'refilmed as ...'); a '?' or 'prob.' marks the link uncertain.
    pos = {}  # manuscript id -> (series, reel, entry)
    for k, i in manuscripts.items():
        pos[i] = k
    same = {}

    def same_as(a, b, source, uncertain, evidence):
        if not a or not b or a == b or a[0] in '0?' or b[0] in '0?':
            return
        a, b = sorted([a, b])
        ia, ib = ms_id(*a), ms_id(*b)
        key = (ia, ib, source)
        if key not in same or (same[key][5] and not uncertain):
            same[key] = (ia, ib, N.reel_label(*a), N.reel_label(*b), source, int(uncertain), evidence)

    for t in titles:
        if t['identical_with'] and t['identical_with'] in tit and t['manuscript_id'] and tit[t['identical_with']]['manuscript_id']:
            same_as(pos[t['manuscript_id']], pos[tit[t['identical_with']]['manuscript_id']], 'title list identical_with',
                    False, f"title {t['id']} = title {t['identical_with']}")
    for e in entries:
        for x in e['_reels']:
            if x[4] == 'identical' and e['manuscript_id']:
                same_as(pos[e['manuscript_id']], x[:3], 'catalogue reel no.', '?' in (r.get('reel_no') or ''), e['file'])
    ref = r'((?:[A-Z]\s*\d+\s*/\s*\d+[a-z]*[\s,;]*(?:and\s+)?)+)(\??)'
    rem_pat = re.compile(r'(?:identical (?:with|to)|^=|;\s*=|same (?:MS|manuscript)[^.;]{0,40}?(?:as|under|on)|'
                         r're-?(?:micro)?filmed (?:as|under|on)|also (?:micro)?filmed (?:as|under|on))\s*(?:reel\s*(?:no\.?)?\s*)?'
                         + ref, re.I)

    def from_remarks(here, text, source):
        for m in rem_pat.finditer(text or ''):
            unc = bool(m.group(2)) or bool(re.search(r'\bprob|\bperhaps|\bpossibly|\bmay be', text[max(0, m.start() - 30):m.start()], re.I))
            for x in N.reels(m.group(1)):
                same_as(here, (x['series'], x['reel'], x['entry']), source, unc, text[:300])

    for t in titles:
        if t['manuscript_id'] and t['remarks']:
            from_remarks(pos[t['manuscript_id']], t['remarks'], 'title list remarks')
    for e in entries:
        if e['preferred'] and e['manuscript_id']:
            for k in ('remarks', 'mf_remarks', 'manuscript_features'):
                from_remarks(pos[e['manuscript_id']], e[k], 'catalogue remarks')
    con.executemany('INSERT INTO same_manuscript VALUES (?,?,?,?,?,?,?)', sorted(same.values()))
    pos = {i: k for k, i in manuscripts.items()}  # positions named only in remarks are new

    parent = {}

    def root(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for ia, ib, *_ in same.values():
        parent[root(ia)] = root(ib)
    groups = collections.defaultdict(list)
    for x in list(parent):
        groups[root(x)].append(x)
    filmed = {}
    for e in entries:
        if e['manuscript_id'] and e['date_of_filming'] and len(e['date_of_filming']) == 10:
            filmed[e['manuscript_id']] = min(filmed.get(e['manuscript_id'], '9999'), e['date_of_filming'])
    rows = []
    for gid, members in enumerate(sorted(groups.values(), key=lambda g: sorted(pos[i] for i in g)), 1):
        if all(i in filmed for i in members):
            basis, key = 'filming date', lambda i: (filmed[i], pos[i])
        elif len({pos[i][0] for i in members}) == 1:
            basis, key = 'reel number', lambda i: pos[i]
        else:
            basis, key = None, lambda i: pos[i]
        reels_ = [pos[i][:2] for i in members]
        suspect = int(len(set(reels_)) < len(reels_))
        for n, i in enumerate(sorted(members, key=key), 1):
            rows.append((gid, i, N.reel_label(*pos[i]), filmed.get(i), n if basis else None, basis, suspect))
    con.executemany('INSERT INTO filming_group VALUES (?,?,?,?,?,?,?)', rows)

    # manuscripts named only in the person register or in remarks
    con.executemany('INSERT OR IGNORE INTO manuscript VALUES (?,?,?,?,?)',
                    [(i, s, r, n, f'{s} {r}/{n}') for (s, r, n), i in manuscripts.items()])
    con.execute('UPDATE attestation SET manuscript_id = (SELECT id FROM manuscript m WHERE m.label = attestation.label) '
                'WHERE manuscript_id IS NULL')

    con.executescript(VIEWS)
    for ix in ('catalogue_entry(manuscript_id)', 'catalogue_entry(label)', 'catalogue_reel(entry_id)',
               'catalogue_reel(series, reel, entry)', 'excerpt(entry_id)', 'issue(entry_id)', 'title(manuscript_id)',
               'entry_title(title_id)', 'discrepancy(entry_id)', 'attestation(person_id)',
               'attestation(manuscript_id)', 'same_manuscript(manuscript_a)', 'same_manuscript(manuscript_b)', 'filming_group(manuscript_id)', 'bendall_excerpt(add_no)', 'ngmcp_date(manuscript_id)', 'bendall_ngmcp_title(add_no)', 'bendall_ngmcp_title(title_id)', 'title_subject(subject_id)', 'catalogue_subject(subject_id)'):
        con.execute(f'CREATE INDEX "ix_{re.sub(r"[^a-z]+", "_", ix)}" ON {ix}')
    con.commit()
    con.execute('VACUUM')
    return con


VIEWS = """
-- one row per text: each title-list title with its catalogue entry, plus catalogue entries the title list lacks;
-- catalogue values first, the title list where the catalogue has none
CREATE VIEW merged AS
WITH best AS (
  SELECT et.title_id, min(et.entry_id) AS entry_id FROM entry_title et JOIN catalogue_entry c ON c.id = et.entry_id
  WHERE c.preferred = 1 AND et.method != 'part of a multiple-text manuscript' GROUP BY et.title_id)
SELECT m.label AS reel, c.marker, t.id AS title_id, c.id AS entry_id, c.file,
  COALESCE(c.title, t.title) AS title, t.title AS titlelist_title, c.author,
  COALESCE(c.material_code, t.material_code) AS material_code,
  COALESCE(c.script_codes, t.script_codes) AS script_codes,
  COALESCE(c.language_codes, t.language_codes) AS language_codes,
  COALESCE(c.folio_count, t.folio_count) AS folio_count,
  COALESCE(c.width_cm, t.width_cm) AS width_cm, COALESCE(c.height_cm, t.height_cm) AS height_cm,
  COALESCE(c.complete, t.complete) AS complete, COALESCE(c.damaged, t.damaged) AS damaged,
  CASE WHEN c.year_ce IS NOT NULL THEN c.era ELSE t.era END AS era,
  CASE WHEN c.year_ce IS NOT NULL THEN c.era_year ELSE t.era_year END AS era_year,
  COALESCE(c.year_ce, t.year_ce) AS year_ce,
  CASE WHEN c.year_ce IS NOT NULL THEN 'catalogue' WHEN t.year_ce IS NOT NULL THEN 'title list' END AS date_source,
  c.scribe, c.king, c.donor, c.place_of_copying, c.place_of_deposit,
  COALESCE(c.acc1, t.acc1) AS acc1, COALESCE(c.acc2, t.acc2) AS acc2, c.inventory_no,
  CASE WHEN c.id IS NOT NULL AND t.id IS NOT NULL THEN 'both' WHEN c.id IS NOT NULL THEN 'catalogue'
       ELSE 'title list' END AS source,
  COALESCE(c.manuscript_id, t.manuscript_id) AS manuscript_id
FROM title t LEFT JOIN best b ON b.title_id = t.id LEFT JOIN catalogue_entry c ON c.id = b.entry_id
LEFT JOIN manuscript m ON m.id = t.manuscript_id
UNION ALL
SELECT c.label, c.marker, NULL, c.id, c.file, c.title, NULL, c.author, c.material_code, c.script_codes,
  c.language_codes, c.folio_count, c.width_cm, c.height_cm, c.complete, c.damaged, c.era, c.era_year, c.year_ce,
  CASE WHEN c.year_ce IS NOT NULL THEN 'catalogue' END, c.scribe, c.king, c.donor, c.place_of_copying,
  c.place_of_deposit, c.acc1, c.acc2, c.inventory_no, 'catalogue', c.manuscript_id
FROM catalogue_entry c
WHERE c.preferred = 1 AND c.id NOT IN (SELECT entry_id FROM best);

CREATE VIEW catalogue_subjects AS
SELECT cs.entry_id, group_concat(s.name, '; ') AS subjects
FROM catalogue_subject cs JOIN subject s ON s.id = cs.subject_id GROUP BY cs.entry_id;
"""


if __name__ == '__main__':
    con = build()
    q = lambda s: con.execute(s).fetchone()[0]
    print('catalogue entries', q('select count(*) from catalogue_entry'),
          '| preferred', q('select count(*) from catalogue_entry where preferred=1'),
          '| excerpts', q('select count(*) from excerpt'), '| issues', q('select count(*) from issue'))
    print('titles', q('select count(*) from title'), '| manuscripts', q('select count(*) from manuscript'))
    for m, n in con.execute('select method, count(*) from entry_title group by 1'):
        print('  link:', m, n)
    print('preferred entries linked', q('select count(distinct entry_id) from entry_title et join catalogue_entry c '
                                        'on c.id=et.entry_id where preferred=1'))
    for f, n in con.execute('select field, count(*) from discrepancy group by 1 order by 2 desc'):
        print('  discrepancy:', f, n)
    print('merged rows', q('select count(*) from merged'))
    print('same-manuscript links', q('select count(*) from same_manuscript'), '| groups',
          q('select count(distinct group_id) from filming_group'), '| retakes',
          q('select count(*) - count(distinct group_id) from filming_group'))
    print('Bendall entries', q('select count(*) from bendall_entry'), '| parts', q('select count(*) from bendall_part'),
          '| excerpts', q('select count(*) from bendall_excerpt'), '| entries with an NGMCP title match',
          q('select count(distinct add_no) from bendall_ngmcp_title'))
