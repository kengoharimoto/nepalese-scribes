# Nepalese scribes and patrons (NGMCP prosopography)

A register of the people named in Nepalese manuscripts (scribes, commissioners, owners, donors,
reigning kings, teachers, and the kin named to identify them), built from the NGMCP catalogue
entries in `/mnt2/kengo/E-texts/NGMCP` (13,382 HTML files, 11,861 microfilm reels).

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
| select colophons that may name people or dates | `extract/make_worklist.py` | `extract/worklist.jsonl` (3,258 reels) |
| first reading of every colophon (Gemini Flash, key as in `indology-genealogy/pipeline/llm.py`) | `extract/extract_gemini.py` | `extract/out_gflash/` |
| pick uncertain readings: low confidence, doubt in notes, catalogue Scribe/King not found, date off by > 2 years | `extract/select_review.py` | `extract/review_list.jsonl` |
| second reading by Opus (`claude -p`), given the colophon and the first reading | `extract/review.py` | `extract/out_review/` |
| Bendall's Cambridge manuscripts (1883): one record per Add. number or part of a composite number | `extract/make_bendall_worklist.py` | `extract/worklist_bendall.jsonl` (319) |
| their first reading (Bendall's English notes and Devanāgarī excerpts together) and Opus second reading | `extract_gemini.py` / `select_review.py` / `review.py` with `--preamble bendall_preamble.txt` | `extract/out_gflash/Cambridge_*`, `extract/out_review/Cambridge_*` (30) |
| merge readings and catalogue fields, group persons, convert dates | `build_persons.py` | `data/manuscripts.json`, `data/persons.json`, `data/relations.json` |
| chart | `export_chart.py` + `chart_template.html` | `out/nepalese_scribes.html` |
| Bendall's Cambridge catalogue (1883): Chandra OCR of the 1992 reprint scan | `chandra-ocr.sh` (in `/mnt2/kengo`) | `data/bendall1883_ocr.md` |
| recalculate dates from the colophons with the pañcāṅga (Yano & Fushimi, `pancanga313_ns_test.pl`, not in the repository: Michio Yano and Makoto Fushimi's *Pancanga* 3.13 Perl program, placed in the project root; rules and their test in `calendar/verify.py`) | `calendar/ngmcp_dates.py`, `calendar/bendall_dates.py` (run after a first `build_persons.py`, then rebuild) | `data/ngmcp_dates.json`, `data/bendall_dates.json` |
| catalogue + title-list database (merges the HTML entries with `data/ngmcpdb_production.sql.bz2`; see `db/README.md`) | `db/build_db.py` | `db/ngmcp.sqlite` |

`extract/extract.py` is the `claude -p` version of the first reading. It was used for the
model comparison on 30 colophons (`extract/pilot.jsonl`; outputs in `extract/out` (Opus),
`out_sonnet`, `out_fable`, `out_gpro`). Both `claude -p` runners pause on a usage limit until the
reset time and skip reels already done, so they can simply be restarted.

## Decisions

- Paper manuscripts dated before 1300 are treated as undated (`date_doubtful`); the Aṃśuvarman ("Mānadeva")
  saṃvat is the Kārttikādi Śaka − 500 (K. P. Malla 2005; `calendar/verify.py`); B 11/4 and C 80/7, AS-dated
  and only in the title list, are added from `data/extra_manuscripts.json`.
- Dates: recalculated from the colophons with the pañcāṅga and checked against the stated weekday
  (`calendar/verify.py`); the flat conversion below is kept as `date_flat` and used for year-only dates.
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
