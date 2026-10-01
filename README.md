# Nepalese scribes and patrons (NGMCP prosopography)

A register of the people named in Nepalese manuscripts (scribes, commissioners, owners, donors,
reigning kings, teachers, and the kin named to identify them), built from the NGMCP catalogue
entries in `/mnt2/kengo/E-texts/NGMCP` (13,382 HTML files, 11,861 microfilm reels).

Chart: `out/nepalese_scribes.html` (published as https://claude.ai/artifact/VyE9X9o4i9sHdkHYbec1ZT).

## Pipeline

| step | script | output |
|---|---|---|
| parse catalogue HTML (fields + «Colophon» excerpt) | `parse_ngmcp.py` | `data/records.jsonl` |
| select colophons that may name people or dates | `extract/make_worklist.py` | `extract/worklist.jsonl` (3,258 reels) |
| first reading of every colophon (Gemini Flash, key as in `indology-genealogy/pipeline/llm.py`) | `extract/extract_gemini.py` | `extract/out_gflash/` |
| pick uncertain readings: low confidence, doubt in notes, catalogue Scribe/King not found, date off by > 2 years | `extract/select_review.py` | `extract/review_list.jsonl` |
| second reading by Opus (`claude -p`), given the colophon and the first reading | `extract/review.py` | `extract/out_review/` |
| merge readings and catalogue fields, group persons, convert dates | `build_persons.py` | `data/manuscripts.json`, `data/persons.json`, `data/relations.json` |
| chart | `export_chart.py` + `chart_template.html` | `out/nepalese_scribes.html` |

`extract/extract.py` is the `claude -p` version of the first reading. It was used for the
model comparison on 30 colophons (`extract/pilot.jsonl`; outputs in `extract/out` (Opus),
`out_sonnet`, `out_fable`, `out_gpro`). Both `claude -p` runners pause on a usage limit until the
reset time and skip reels already done, so they can simply be restarted.

## Decisions

- Dates: the catalogue date is used where it names the era; otherwise the colophon reading.
  NS + 880, VS − 57, ŚS + 78, LS + 1119. A bare "SAM" in the catalogue is read as NS for years up
  to 1150 in Newari script or below 1000, otherwise VS, and is marked as inferred.
- Names are grouped by a folded key without śrī and without titles (śarman, miśra, upādhyāya,
  vajrācārya, karmācārya, jośī, daivajña, ṭhakkura, varman). Regnal epithets are removed from kings
  (śrīśrīsumatijayajitāmitramalladeva = Jitāmitra Malla). A person attested as patron whose name
  matches a king is merged into that king.
- Homonyms are separated by date only: a new person starts after a 40-year gap in attestations or
  when one career would exceed 60 years. Undated attestations go to the largest group.
- Authors and commentators named in colophons are extracted but left out of the register.
