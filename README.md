# Nepalese scribes and patrons (NGMCP prosopography)

A register of the people named in Nepalese manuscripts (scribes, commissioners, owners, donors,
reigning kings, teachers, and the kin named to identify them), built from the NGMCP catalogue
entries in `/mnt2/kengo/E-texts/reference/ngmcp` (17,041 HTML files, 11,866 reels), completed from the
wiki mirror (6,217 further pages, 6,178 reels or bundle items that have no local card): 18,561
manuscripts and inscriptions in all.

All 5,106 colophons in the worklist have a first reading; 991 have an Opus reading (second reading, or
first where Gemini was unavailable). Register: 18,561 manuscripts and inscriptions, 5,190 dated, 3,706 persons.

Chart: https://kengoharimoto.github.io/nepalese-scribes/ (built from `out/nepalese_scribes.html` by
`.github/workflows/pages.yml` on every push that changes it; a private copy is also kept as a
claude.ai artifact).

Source data: the NGMCP descriptive catalogue (Nepalese-German Manuscript Cataloguing Project,
University of Hamburg). `data/records.jsonl` and the extraction outputs contain catalogue fields
and the colophon excerpts quoted by the cataloguers. The Hamburg wiki was taken offline in July 2025;
a mirror of its files is published under CC0 at https://github.com/INDOLOGY/NGMCP-Descriptive-Catalogue.

## Pipeline

| step | script | output |
|---|---|---|
| parse catalogue HTML (fields + «Colophon» excerpt) | `parse_ngmcp.py` | `data/records.jsonl` |
| parse the wiki mirror (clone into `E-texts/reference/ngmcp-mirror-src/repo`), keeping the pages whose reel has no local card (same reel, or same inventory number and a similar title); the page title gives the reel where the Reel No. field disagrees (79 pages, mostly typos: 'A 29/19' for B 29-19); wiki footnotes are removed; every Colophon block is kept, bundle items ('E 1774-3(30)') stay separate | `parse_mirror.py` | `data/records_mirror.jsonl` |
| select colophons that may name people or dates | `extract/make_worklist.py` | `extract/worklist.jsonl` (5,106 reels) |
| first reading of every colophon (Gemini Flash, key as in `indology-genealogy/pipeline/llm.py`) | `extract/extract_gemini.py` | `extract/out_gflash/` |
| pick uncertain readings: low confidence, doubt in notes, catalogue Scribe/King not found, date off by > 2 years | `extract/select_review.py` | `extract/review_list.jsonl` |
| second reading by Opus (`claude -p`), given the colophon and the first reading | `extract/review.py` | `extract/out_review/` |
| first reading by Opus where Gemini was unavailable (so far C 80/7 and four reels whose colophon grew in a later card; their Flash readings are in `extract/out_superseded/`) | `extract/extract.py` | `extract/out_opus/` |
| Bendall's Cambridge manuscripts (1883): one record per Add. number or part of a composite number | `extract/make_bendall_worklist.py` | `extract/worklist_bendall.jsonl` (319) |
| their first reading (Bendall's English notes and Devanāgarī excerpts together) and Opus second reading | `extract_gemini.py` / `select_review.py` / `review.py` with `--preamble bendall_preamble.txt` | `extract/out_gflash/Cambridge_*`, `extract/out_review/Cambridge_*` (30) |
| merge readings and catalogue fields, group persons, convert dates | `build_persons.py` | `data/manuscripts.json`, `data/persons.json`, `data/relations.json` |
| chart | `export_chart.py` + `chart_template.html` | `out/nepalese_scribes.html` |
| Bendall's Cambridge catalogue (1883): Chandra OCR of the 1992 reprint scan | `chandra-ocr.sh` (in `/mnt2/kengo`) | `data/bendall1883_ocr.md` |
| recalculate dates from the colophons with the pañcāṅga (Yano & Fushimi, `pancanga313_ns_test.pl`, not in the repository: Michio Yano and Makoto Fushimi's *Pancanga* 3.13 Perl program, placed in the project root; rules and their test in `calendar/verify.py`) | `calendar/ngmcp_dates.py`, `calendar/bendall_dates.py` (run after a first `build_persons.py`, then rebuild) | `data/ngmcp_dates.json`, `data/bendall_dates.json` |
| Licchavi inscriptions (E-texts `1_sanskr/7_inscriptions/licchavi`, 198; e-text edition prepared by D. N. Lielukhine): worklist, reading (Gemini Flash; Opus for 20), dates afresh | `extract/make_licchavi_worklist.py`; `extract_gemini.py` / `review.py` with `--preamble preamble_licchavi.txt --schema schema_licchavi.json`; `calendar/licchavi_dates.py` | `extract/out_gflash/Licchavi_*`, `extract/out_review/Licchavi_*`, `data/licchavi_dates.json` |
| catalogue + title-list database (merges the HTML entries with `data/ngmcpdb_production.sql.bz2`; see `db/README.md`) | `db/build_db.py` | `db/ngmcp.sqlite` |

`extract/extract.py` is the `claude -p` version of the first reading. It was used for the
model comparison on 30 colophons (`extract/pilot.jsonl`; outputs in `extract/out` (Opus),
`out_sonnet`, `out_fable`, `out_gpro`). Both `claude -p` runners pause on a usage limit until the
reset time and skip reels already done, so they can simply be restarted.

## Decisions

- Licchavi inscriptions: persons named only as ancestors in genealogies are left out, and Licchavi persons
  are grouped separately from the persons of manuscripts (keys `lic:`); -varman stays part of a name there.
  Both Licchavi series (saṃvat 386–535, and Aṃśuvarman's from 29) are read as the Kārttikādi current Śaka
  (Malla 2005), the second with 500 dropped (`calendar/verify.py`, eras LIC and AS). A year is LIC only
  within 386–535, otherwise AS. Entry 55 of the edition is not an inscription but the colophon of the
  Suśrutasaṃhitā, Kaiser Library 699 (C 80/7), and is left out (`NOT_INSCRIPTIONS` in
  `extract/make_licchavi_worklist.py`); the manuscript is registered from its catalogue entry (by KH, in the
  mirror). There Vasuvarman (vaidya, of Gaṇadevadevakula) is the owner, the book having been given to him;
  Harṣacandra, subject of *prākhilat* (for *prālikhat*), is read as the scribe, but he may have had the copy
  made (Acharya in Klebanov: causative; Suvedī & Tivārī read an ablative and a lost scribe's name): open.
  Also open, between KH's reading (catalogue entry; the same text in Harimoto, RSO 84, 2011: 88) and Klebanov's
  edition (draft of 2015): the place compound (*°dūnīścalakanivāsino* in KH, *°dūnīgvalaka°* in Klebanov and *gvalaka* in the earlier editions;
  *gvala* = temple, Acharya); whether Gaṇadevadevakula is the place of copying (entry) or only Vasuvarman's
  residence (Klebanov); the last sentence (KH *tadādhiśruyābhyāṃ na kaścid*, Klebanov *tad ādhikrayābhyāṃ
  tadgotrajena kenacin na kañcid*, K *tadgotrajena cin na kaścid*); and the bundle (two manuscripts in the
  entry, "at least two" in Harimoto, JIBS 62.3, 2014: 23, at least four codicological units in Klebanov; the
  2011 article's Fig. 1 names the dated one "KL 699-4"). The entry's Owner field has "Vaidyavasvarman" for
  Vasuvarman.
- B 29/19 (Suśrutasaṃhitā, NAK 5/333, from Hemarāja Śarman's collection; scribe the vaidya Amarasiṃhaka, son
  of Kamaladatta) is left undated (`DATE_OPEN` in `build_persons.py`): its year (*anala-aṅga/agni/aṅka-rasa*)
  is corrected in the manuscript, and the readings give c. 1510/1512, 1543, 1573, Harimoto's 1540 (2014: 23) and
  the catalogue's 1465. B 30/15 (NAK 5/334) is a modern printout of photographs of 5/333, and A 1267/11 is a
  second filming of A 45/5 (Harimoto 2014, n. 1–2); neither has a catalogue entry here.
- Paper manuscripts dated before 1300 are treated as undated (`date_doubtful`); the Aṃśuvarman ("Mānadeva")
  saṃvat is the Kārttikādi Śaka − 500 (K. P. Malla 2005; `calendar/verify.py`), recognised in the catalogue as
  'Mānadeva Saṃvat'; B 11/4, AS-dated and only in the title list, is added from `data/extra_manuscripts.json`
  (Caitra śukla 12 of 234 = Monday 10 March 811, unverifiable; Harimoto 2011: 90).
- Month names: the poetic Mādhava is Vaiśākha, and the vṛddhi spelling jyaiṣṭha is Jyeṣṭha.
- Places: Deopatan (Devapattana, by Paśupati) is kept apart from Patan (Lalitpur).
- Dates: recalculated from the colophons with the pañcāṅga and checked against the stated weekday
  (`calendar/verify.py`); the flat conversion below is kept as `date_flat` and used for year-only dates.
  The program's Julian-day-to-Gregorian conversion makes the last day of February a "February 30" in
  213 of the years 1583–2030 and computes it as the day after; `calendar/panc_batch.pl` replaces it (ten
  dates corrected, three of them now verified). Julian-calendar dates (before 1582) were not affected.
- Flat conversion (before the pañcāṅga): the catalogue date where it names the era; otherwise the colophon reading.
  NS + 880, VS − 57, ŚS + 78, LS + 1119. A bare "SAM" in the catalogue is read as NS for years up
  to 1150 in Newari script or below 1000, otherwise VS, and is marked as inferred.
- Names are grouped by a folded key without śrī and without titles (śarman, miśra, upādhyāya,
  vajrācārya, karmācārya, jośī, daivajña, ṭhakkura, varman). Regnal epithets are removed from kings
  (śrīśrīsumatijayajitāmitramalladeva = Jitāmitra Malla). A person attested as patron whose name
  matches a king is merged into that king.
- Homonyms are separated by date only: a new person starts after a 40-year gap in attestations or
  when one career would exceed 60 years. Undated attestations go to the largest group.
- Authors and commentators named in colophons are extracted but left out of the register.
