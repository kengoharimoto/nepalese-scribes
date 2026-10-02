# NGMCP database (`db/ngmcp.sqlite`)

One SQLite database combining the NGMCP descriptive catalogue (13,382 HTML entries in
`/mnt2/kengo/E-texts/NGMCP`) and the NGMCP title list (MySQL dump `data/ngmcpdb_production.sql.bz2`).

    python3 db/build_db.py      # about 15 seconds; writes db/ngmcp.sqlite (not in git, ~90 MB)

| script | does |
|---|---|
| `parse_html.py` | splits an entry into its template sections and reads ~45 labels (with their misspellings, labels broken over lines, missing colons, headings run into the previous field) and the excerpt subsections («Beginning», «End», «Colophon», «Sub-colophon», ...) |
| `normalize.py` | turns each raw field into typed columns and controlled codes; whatever it cannot read goes to the `issue` table |
| `load_sql.py` | loads the MySQL dump into SQLite (no MySQL needed); account tables (users, roles, permissions) are skipped |
| `build_db.py` | builds the database: catalogue tables, decoded title list, links between the two, discrepancies, the person register |

## Tables

**Catalogue (HTML)**

- `catalogue_entry`: one row per HTML file. Every normalised column keeps its source next to it
  (`script_raw` → `script_codes`, `size_raw` → `width_cm`, `height_cm`, `date_of_copying_raw` → `era`,
  `era_year`, `year_ce`, `month`, `paksa`, `tithi`, `weekday`, ...). Several files describe the same reel
  position: `preferred = 1` marks the fullest one, the others have `duplicate_of`.
- `catalogue_reel`: every reel number named in an entry, with `relation` primary / identical
  (`A 1/1 = A 3/1`) / continued (`B 105/17 - B 106/1`) / microfilm (from the Microfilm Details block).
- `catalogue_script`, `catalogue_language`, `catalogue_subject`: the coded values as rows.
- `excerpt`: the excerpt subsections in order (`kind` = beginning, end, colophon, sub-colophon,
  transcript, other; `locus` = the folio reference at the end, e.g. `fol. 36v3–5`).
- `issue`: fields that could not be read or hold something else (a note in «Scribe», the state in
  «Material», an impossible filming date ...), with the raw value.

**Title list (SQL dump)**

- `tl_*`: the original tables unchanged (`tl_titles`, `tl_manuscripts`, `tl_catalogs`, `tl_ktm_scans`,
  `tl_tbt_titles`, ...).
- `title`: `tl_titles` decoded into the same columns as the catalogue (material, completeness, script and
  language codes, size, era/year/CE, accession number).

**Combined**

- `manuscript`: one row per microfilm position (`series`, `reel`, `entry`; label `A 19/8`). Parts of a
  multiple-text manuscript (`A 981/19a`, `.../19b`) share one manuscript and differ by `catalogue_entry.marker`.
- `entry_title`: which title-list text a catalogue entry describes, with `method`:
  `title match` (one-to-one by title similarity within the manuscript, `score` ≥ 0.6),
  `title list catalog link` (the title list's own file link), `only title at this reel position`,
  `part of a multiple-text manuscript` (no matching text; linked to the closest title of the bundle).
- `merged` (view): one row per text. Catalogue values are used where present, title-list values
  otherwise; `source` says both / catalogue / title list, `date_source` where the date comes from.
- `discrepancy`: catalogue and title list disagree (folio count, size > 1 cm, date > 1 year, material,
  script, accession number, very different titles).
- `same_manuscript`: two microfilm positions that show the same manuscript, one row per source of the
  claim: the title list's `identical_with`, `=` in the catalogue's Reel No. (`A 1/1 = A 3/1`), or a remark
  in either source ("identical with A 1336/7", "= A 38/15", "refilmed as ..."). `uncertain = 1` when the
  remark has "?" or "prob."; `evidence` quotes it.
- `filming_group`: the positions joined by those links (2,899 manuscripts filmed more than once, 3,033
  retakes). `seq` orders the filmings by filming date when every member has one, otherwise by reel
  number within one series (`order_basis`); mixed-series groups without dates stay unordered.
  `suspect = 1` when a group holds two positions on the same reel, which usually means a wrong link
  in the sources (A 1/2 is said to be "= A 3/1" as well as "= A 3/2").
- `person`, `attestation`, `person_relation`: the scribe and patron register from `build_persons.py`,
  attached to manuscripts.

**Vocabularies**: `script`, `language`, `material`, `subject`, `calendar`. Codes follow the title list
(script D Devanagari, W Newari, M Maithili ...; material P palm-leaf, T Thyāsaphu ...). Additions:
material `paper` (the title list leaves paper blank) and `cloth`; scripts Ku Kuṭilā, Nn Nandināgarī,
Gi Gilgit/Bamiyan.

## Decisions

- Dates of copying use the same rules as the person register (`build_persons.parse_date`): era from
  the catalogue, a bare "SAM" read as NS or VS by year and script (`era_inferred = 1`).
- Filming and cataloguing dates become ISO dates; two-digit years are 19xx, `BS 2043-1-28` is converted
  to its CE year only.
- Sizes accept `22. 5 x 7.0`, `26 0 x 11 5` (space for the point) and `1,057 x 24` (rolls).
- `edited` is NULL when the template's `no/yes` was left unchanged.
- The title-list tables `catalogsCopy` and `*_copy` are backup copies in the dump and are not loaded.

## Examples

```sql
-- dated Newari-script palm-leaf manuscripts before 1400 CE
SELECT reel, title, era, era_year, year_ce, scribe FROM merged
WHERE material_code = 'P' AND script_codes LIKE '%W%' AND year_ce < 1400 ORDER BY year_ce;

-- colophons naming a place, with the catalogue's place of copying
SELECT c.label, c.place_of_copying, x.text FROM catalogue_entry c JOIN excerpt x ON x.entry_id = c.id
WHERE x.kind = 'colophon' AND c.place_of_copying IS NOT NULL;

-- where the two sources disagree on the date
SELECT c.label, c.title, d.catalogue_value, d.titlelist_value FROM discrepancy d
JOIN catalogue_entry c ON c.id = d.entry_id WHERE d.field = 'date';

-- retakes: every filming after the first of a manuscript
SELECT g.label, first.label AS first_filmed FROM filming_group g
JOIN filming_group first ON first.group_id = g.group_id AND first.seq = 1 WHERE g.seq > 1;

-- everything one scribe copied
SELECT a.label, c.title, c.year_ce, a.roles FROM person p JOIN attestation a ON a.person_id = p.id
LEFT JOIN catalogue_entry c ON c.label = a.label AND c.preferred = 1 WHERE p.name = 'Jaugīndrapati';
```
