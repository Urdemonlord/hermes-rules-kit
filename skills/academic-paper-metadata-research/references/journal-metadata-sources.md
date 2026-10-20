# Where to Verify Each Journal-Metadata Field

A filled paper table is only as good as the source behind each cell. Match the field to the
source that actually owns it; a search-result snippet is never sufficient.

## Field → source map

| Field | Authoritative source |
|---|---|
| PENULIS (authors) | Article page byline or the PDF first page. If absent, mark "cek laman artikel". |
| TAHUN (year) | Article page publication date (use the published date, not the received date). |
| PERMASALAHAN / TUJUAN (problem / objective) | Abstract + introduction of the paper. |
| DATA | Methods section — sample size, participants, dataset. Grep the PDF for `N =`. |
| SOFTWARE/APLIKASI | Methods/implementation section (e.g. Unity, Unreal Engine, Blender, SPSS). |
| METODE/ALGORITM | Methods section — design (R&D, experiment, survey), statistics used. |
| HASIL | Results section — exact statistic, score, or percentage. Read from the PDF. |
| AKREDITASI JURNAL | Indonesian: SINTA (sinta.kemdiktisaintek.go.id). International: Scimago/Scopus + WoS index. |
| LINK APC | The publisher's own article-processing-charge page. |
| BAHASA PAPER | Article page / PDF. |
| MASA AKTIF JURNAL | SINTA journal profile → accreditation SK validity period (ARJUNA). |
| NAMA JURNAL | Article page masthead. |
| LINK PAPER | DOI link (preferred) or the article URL. Verify it resolves. |
| JADWAL PUBLISH | Journal's issue frequency (e.g. 3 issues/year: Feb, Jun, Oct). |
| WAKTU TAHAPAN | Stage dates from the article page (received / revised / accepted / published). |

## Indonesian accreditation (Sinta / ARJUNA)

- **Sinta grade** (S1–S6) lives at `sinta.kemdiktisaintek.go.id/journals/profile/<id>`; the
  search page is `journals/search`. Confirm the journal's own profile, not a third-party list.
- **Active period / masa aktif** is the accreditation SK validity window (typically ~5 years).
  It is not on the article page — check ARJUNA. If you cannot confirm the SK, write "perlu cek
  SK ARJUNA terbaru" rather than asserting a period.
- A journal can be **Sinta-accredited and Scopus-indexed with different standing** — record both,
  separately.

## International indexing (Scopus / WoS / DOAJ)

- **Scopus quartile** varies by subject category; a journal may be Q1 in one category and Q2 in
  another. State the category when you state the quartile.
- **Web of Science** index matters: **ESCI** is not **SCIE**. A journal can be Scopus Q1 yet WoS
  ESCI-only.
- **DOAJ** is a good cross-check for open-access status and APCs.
- **Crossref** resolves DOIs and gives the canonical metadata record.

## APC volatility

Article-processing charges change without notice and differ by article type. Always:
- read the publisher's CURRENT fee page (Frontiers, MDPI, JMIR, Springer each have one);
- quote the currency the publisher uses (CHF for Frontiers/MDPI, USD for JMIR);
- date-stamp the figure and tell the user to re-check before submitting.

## Bulk candidate discovery (fill mode)

To fill a table of many rows, discover candidates with a batch of parallel searches rather than
one query at a time:

- **Topic + tier + year** — `<topic> Sinta 2 2024 artikel`, `<topic> Scopus Q1 2023 article`.
- **Journal-targeted** — `<journal name> <topic> 2024 article`; this is the fastest route when you
  already know which journals meet the tier (e.g. JTIIK, RESTI, TEKNIMEDIA, JUTIF, JOIV for Sinta
  1-2; MDPI / Frontiers / Springer / JMIR for Scopus).
- **Site-scoped** — `site:sinta.kemdiktisaintek.go.id <topic> Accred Sinta 2` surfaces SINTA-indexed
  articles with the grade already attached.

Fastest metadata source per publisher: MDPI, Frontiers, JMIR and Springer article pages expose
authors + dates + volume + DOI on one page; OJS Indonesian journals (`/article/view/<id>`) expose
"Penulis", "DOI", "Diterbitkan" and "Vol/No" on the abstract page. Prefer these over landing on the
PDF, and reserve PDF retrieval for the exact quantitative figures.

## Link probing

```bash
curl -s -o /dev/null -w '%{http_code} %{url_effective}\n' -L -A 'Mozilla/5.0' "$URL"
```

Some publishers block non-browser user agents — a 403 from a bare client is not proof the link
is dead; retry with a browser `User-Agent` before flagging it.
