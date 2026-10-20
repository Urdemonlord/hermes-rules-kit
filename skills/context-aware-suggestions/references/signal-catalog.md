# Signal catalog: capability detectors & domain vocabularies

Reusable starting points for the relevance filter in a context-aware suggestion feature.
Two independent things are detected: **which capabilities the project already has** (used to
suppress suggestions) and **which domain the app belongs to** (used to order them).

All matching is against a lowercased haystack of paths + content + free-text context.
Apply the pitfalls in SKILL.md before extending either table: word boundaries, no ubiquitous
tokens, real storage APIs only.

## Capability detectors (presence → suppress the suggestion)

Each row is `id` → signals that mean *already present*. Extend with real API names, never
with generic English words.

| id | presence signals (abbreviated) |
|---|---|
| auth | `login|signin|signup|register|logout|jwt|bearer|session|password|bcrypt|auth`; path `auth|login|session|user` |
| persistence | `sqlite|postgres|mysql|mongodb|prisma|drizzle|sequelize|mongoose|firestore|sqlalchemy|room|realm|hive|sqflite|localstorage|sessionstorage|shared_preferences|asyncstorage|indexeddb|json.dump|pickle.|open(...,'w')|writeFile` |
| search | `\bsearch\b|\bpencarian\b|\bcari\b|\bquery\b|.filter(|where(|ilike`; path `search` |
| drag-drop | `\bdrag(gestart|over|enter|end|leave)?\b|draggable|ondrop|\bdrop\b|datatransfer|sortable|reorder|pointerdown` |
| charts | `recharts|chart.js|chartjs|\bd3\b|plotly|matplotlib|seaborn|victory|apexcharts|\bchart\b|\bgrafik\b|\bgraph\b` |
| export | `download|jszip|file-saver|tostream|\bblob\(|to_csv|writerow|\bcsv\b` |
| notifications | `\btoast\b|notification|\bsnackbar\b|\bnotif\b|alert\(|flash\(` |
| forms-validation | `\bzod\b|\byup\b|formik|react-hook-form|validate|validator|isvalid|\brequired\b|minlength|maxlength|pydantic` |
| filters | `\bfilter\b|sortby|orderby|order_by|order\s+by|\bsegment\b|\btab\b` |
| pagination | `pagination|\bpage\b|offset|\blimit\(|per_page|pagesize` |
| file-upload | `upload|multipart|formdata|type=["']file["']|multer|filereader` |
| tests | `\.test\.|\.spec\.|__tests__|pytest|\bjest\b|vitest|flutter_test|cargo\s+test|#\[test\]|go\s+test|unittest|junit` |
| routing | `react-router|createbrowserrouter|next/link|vue-router|go_router|navigationbar|navhost|gorilla/mux|gin.default|express.router|@app.route|fastapi|apirouter` |
| state-management | `zustand|redux|mobx|recoil|jotai|riverpod|\bbloc\b|\bviewmodel\b|usecontext|createcontext|usereducer` |
| loading-state | `loading|isloading|spinner|skeleton|shimmer` |
| error-handling | `try\s*\{|catch\s*\(|errorboundary|errorhandler|except\s+\w+|rescue` |
| empty-state | `\bempty\b|\bkosong\b|no data|belum ada|placeholder` |
| animations | `framer-motion|\banimate\b|animation|transition|@keyframes` |
| responsive | `@media|mediaquery|\bsm:|\bmd:|\blg:|\bxl:|flex-wrap|grid-cols|responsive` |
| dark-mode | `darkmode|dark-mode|dark mode|mode gelap|prefers-color-scheme|\bdark:|settheme|themetoggle` |
| i18n | `\bi18n\b|\blocale\b|translation|react-intl|\bintl\b|\bl10n\b` |
| accessibility | `aria-|\brole=["']|alt=["']|htmlfor|tabindex` |
| cli-args | `argparse|click\b|typer|sys\.argv|commander|yargs|cobra|getopt` |
| logging | `\blogging\b|logger|log\.info|winston|pino|structlog|loguru|\bprint\(` |
| config-env | `dotenv|process\.env|os\.environ|\.env\b|config\.yaml|configparser|\bsettings\b|getenv` |
| optimization | `vectoriz|\bnumba\b|\bcache\b|memoiz|chunksize|\bbatch\b|multiprocess|threadpool` |

## Domain vocabularies (classification → ordering)

Match these against **metadata first, content second** (weight metadata above content). Each
domain also needs its own **noun** for phrasing chips, and its own **relevance order**.

| domain | vocabulary | noun | relevant capabilities, most first |
|---|---|---|---|
| landing | `landing|hero|cta|marketing|saas|startup|pricing|testimoni` | konten | forms-validation, responsive, animations, accessibility, i18n, dark-mode |
| kanban | `kanban|board|wip|backlog|swimlane|drag.{0,20}card` | kartu | drag-drop, search, persistence, filters, auth, notifications |
| todo | `todo|to-do|task|tugas|checklist|done` | tugas | persistence, search, filters, notifications, empty-state, auth |
| notes | `note|notes|catatan|markdown|journal` | catatan | persistence, search, export, filters, auth |
| ecommerce | `product|produk|cart|keranjang|checkout|order|pesanan|toko|shop` | produk | auth, search, pagination, persistence, file-upload, filters |
| chat | `chat|message|pesan|conversation|percakapan` | pesan | persistence, notifications, search, pagination, auth |
| blog | `blog|post|posting|artikel|article|cms` | artikel | search, pagination, filters, auth, persistence |
| dashboard | `dashboard|statistik|statistic|metric|analytics|kpi` | data | charts, filters, export, pagination, search |
| finance | `expense|pengeluaran|budget|anggaran|finance|keuangan|saldo|balance|invoice|pemasukan` | pengeluaran | charts, persistence, export, filters, auth |
| calendar | `calendar|kalender|event|jadwal|schedule|agenda|deadline` | jadwal | persistence, notifications, filters, auth, search |
| social | `feed|follow|follower|like|comment|komentar` | postingan | auth, notifications, pagination, search, persistence |
| inventory | `inventory|stok|stock|gudang|warehouse|barang` | stok | search, pagination, export, charts, filters |
| datascript | `pandas|numpy|dataframe|jupyter|read_csv|read_excel|dataset|analisa|etl|scraper|script\s+(python|bash|node)|\.ipynb|\.sh` | data | data-validation, tests, logging, cli-args, optimization, export, config-env |
| generic | (no match) | data | persistence, auth, search, filters, export, notifications |

Domain-agnostic quality gaps to append **after** the domain's own list: `error-handling`,
`loading-state`, `tests`, `routing`, `state-management`.

## Scoring & tie-breaks

- Score a domain as `2 × matches(metadata) + matches(content)`, then sort score desc.
- Tie-break by the domain table's own order so the result is stable across calls.
- Take the first domain as primary (drives the noun and the relevance order); keep the rest
  as secondary candidates so a project matching two domains still gets the union.
- Dedupe candidate ids while preserving order, then take the first N that are absent.
