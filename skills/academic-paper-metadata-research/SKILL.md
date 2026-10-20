---
name: academic-paper-metadata-research
category: research
description: Use when filling or verifying a journal paper table.
tags: [research, academic, journals, papers, verification, spreadsheet, sinta, scopus]
triggers:
  - "carikan jurnal / paper tentang X"
  - "letakkan di template"
  - "cek validitas penulis / tahun / hasil / akreditasi"
  - "fill a literature review spreadsheet"
  - "verify journal metadata"
---

# Academic Paper & Journal Metadata Research

Research REAL papers on a topic and populate — or verify — a structured spreadsheet of
metadata. The deliverable is not a prose summary; it is a table where **every cell is a
real, checkable fact**, and the user can trust it enough to submit or hand in.

Two modes, same workflow:
- **Fill**: topic in, template out (one real paper per row).
- **Verify**: user's draft table in, corrected table + a per-column verdict out.

## When to Use

- User sends a spreadsheet template (journal assignment, literature review, "TUGAS JURNAL")
  and asks to fill it with papers on a topic.
- User sends an already-filled table and asks to "cek validitas" of the columns.
- User wants real journal metadata (accreditation, APC, language, active period) for a list
  of papers.

## Procedure

### 1. Read the template before doing anything else

Do NOT assume the header is row 1 or that the sheet is the active one. Load the workbook and
find the header row by scanning for a row whose cells match expected labels, then read the
rows below it:

```python
import openpyxl
wb = openpyxl.load_workbook(path, data_only=True)
ws = wb["Sheet1"]                      # confirm sheet name, don't guess
# header may be at row 8, not row 1 — detect it
HDR = [ws.cell(8, c).value for c in range(2, 20)]   # print and eyeball first
rows = {r: [ws.cell(r, c).value for c in range(2, 20)]
        for r in range(9, ws.max_row + 1) if ws.cell(r, 2).value}
```

Print the header row and the first data rows. Build a `header -> column index` dict from what
the sheet ACTUALLY contains and use that dict for every write — never hard-code column letters
or rely on positional order. Off-by-one here silently writes values into the wrong columns.

### 2. One real paper = one row

Every row must be a genuine, findable paper with real authors and a resolvable link. When the
user wants two index systems (e.g. Indonesian **Sinta** and international **Scopus**), keep them
on **separate rows** — do not merge a paper's Sinta and Scopus metadata into one cell.

### 3. Find candidate papers (Fill mode)

Discover candidates **journal-by-journal**, not topic-only — you need papers whose *journal*
also satisfies the tier the user asked for:

```python
for q in ['<topic> Sinta 2 2024 artikel',
          '<journal name> <topic> 2023 article',
          'MDPI Applied Sciences virtual reality 2024 education']:
    web_search(q, limit=6)
```

Then open the **article page** (never the search snippet) with `web_extract`: one page yields
authors, year, volume, DOI and the received/accepted/published dates together. Prioritise pages
that render full metadata — MDPI, Frontiers, JMIR, Springer, and OJS-based Indonesian journals
(`/article/view/<id>` shows "Penulis", "DOI", "Diterbitkan", "Vol/No" directly).

- Confirm the paper's year is inside the requested range. If you deliberately include an
  out-of-range classic as a reference, call it out in the reply instead of letting it pass as
  in-range.
- The article page gives neither the tier nor the APC: get the tier from the journal profile
  (SINTA / Scimago) and the APC from the publisher's fee page.

### 4. Verify each field against the RIGHT source

Metadata comes from different places; a search snippet is not enough. See
`references/journal-metadata-sources.md` for the field → source map (article page, PDF, SINTA,
Scimago, publisher APC page, DOAJ, Crossref). Rules that always apply:

- **Authors, year, data, method, results** — read the **article page or the PDF itself**.
- **Accreditation (Sinta grade) and active period** — check SINTA / ARJUNA, not a secondary blog.
- **Scopus quartile** — check Scimago/Scopus; a journal's quartile **varies by category**, and
  note the WoS index (ESCI vs SCIE) separately.
- **APC** — read the publisher's CURRENT fee page. APC changes over time; state the figure as
  of today and flag that it may change.

### 5. Pull the numbers from the PDF, not the abstract

For quantitative claims (sample size, test statistic, SUS score, percentage improvement),
download the actual PDF and grep it for the figure:

```python
from hermes_tools import terminal, read_file
terminal("cd /tmp && curl -s -L -A 'Mozilla/5.0' -o p.pdf '<pdf-url>'")
c = read_file("/tmp/p.pdf")["content"]
import re
for kw in ["4.416", "87.72", "N =", "p = 0.001"]:
    ...  # confirm the number literally appears
```

If the exact figure is not in the source you read, say so — do not round or invent it.

### 6. Confirm every link resolves

Dead links are the most common defect in a filled table. Probe each URL (and resolve each DOI):

```bash
curl -s -o /dev/null -w '%{http_code} %{url_effective}\n' -L -A 'Mozilla/5.0' "$URL"
```

### 7. Deliver in the user's shape

- Preserve the original template's structure and sheet name; write values into the existing
  cells rather than rebuilding the layout.
- Add a separate notes sheet (e.g. **"CATATAN VERIFIKASI"**) with one row per field per paper and
  a colour-coded verdict: green = valid, amber = corrected, orange = needs the user's attention.
  A ready template is at `templates/verification_notes_sheet.py`.
- Export **both** `.xlsx` and `.csv` and send both.
- Write everything in **Indonesian**; the user's register is technical-but-plain.
- When asked to "paste hasilnya kesini", put the full table content in the chat reply, not only
  the file.

## Pitfalls

- **Header row is not always row 1.** Templates commonly carry a title block above the header.
  Detect the header row and the first data row by scanning, then build a header→index map.
  Positional writes against a wrong assumption put values in the wrong columns.
- **Always `wb.save(path)` and then reload to verify.** Editing cells in memory and forgetting
  the save — or saving and not re-reading — means corrections silently vanish. Re-open the saved
  file and print the cells you changed before declaring success.
- **Never fabricate authors or fields.** When a page does not list the full author set, write
  "nama penulis: cek laman artikel" (check the article page) instead of guessing. A plausible
  invented name is worse than an explicit gap.
- **Don't trust the abstract or a secondary summary for numbers.** Read the source body/PDF;
  a paraphrase can carry a wrong figure that then propagates into the table.
- **Sinta ≠ Scopus ≠ WoS.** Keep them labelled and separate. A Sinta 1 journal can be Scopus Q3;
  a Scopus Q1 claim may be Q2 in another category; ESCI is not SCIE. Never print a bare "Q1".
- **APC and accreditation are volatile.** Fees change (an APC can jump within a year) and Sinta
  grades expire on a SK period. State figures "as of today" and tell the user to re-check ARJUNA
  and the publisher's fee page before submitting.
- **Estimates are not facts.** "Jadwal publish" and "waktu tahapan" from a general publishing
  workflow are ESTIMATES — label them as such; only stage dates read from the article page are
  facts.
- **Keep rows inside the requested year range; flag exceptions.** A table titled "2021-2026"
  that silently contains a 2020 paper is a defect. Either drop it or label it as an out-of-range
  reference in the reply.
- **Preserve the template's cell styling when writing new rows.** Copy the style from an existing
  filled row — `cell._style = copy(ws.cell(src_row, col)._style)` — so fonts, borders and wrap
  match. Without it the added rows render half-formatted next to the originals.
- **Do not present unverified rows as verified.** If a field could not be confirmed, its verdict
  is "needs check", not "valid".

## Verification Checklist

- [ ] Header row and data start located by scanning, not assumed
- [ ] Header→index map built and used for every write
- [ ] Every row is one real paper with resolvable authors and link
- [ ] Every row's year is inside the requested range (or explicitly flagged as an exception)
- [ ] New rows carry the template's cell styling
- [ ] Sinta / Scopus / WoS kept on separate rows and labelled
- [ ] Quantitative figures grepped from the source PDF
- [ ] Every URL/DOI probed and returns 200
- [ ] Unverifiable fields marked, not fabricated
- [ ] File saved, re-opened, and the changed cells printed
- [ ] xlsx + csv delivered; notes sheet added; reply in Indonesian
