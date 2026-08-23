---
name: books-manga-series
description: "Find, verify, download, catalog, and deliver legally free books, novels, manga/comics, and multi-volume series from official, public-domain, or Creative Commons sources. Use when the user asks to download books, manga, comics, novels, or a book series — including non-tech titles, not only programming books."
version: 1.0.0
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [books, manga, comics, novels, series, ebooks, PDF, EPUB, public-domain, Creative-Commons, legal]
    related_skills: [ocr-and-documents, arxiv]
---

# Books, manga, and series (legal only)

Use when the user wants **books of any kind**, **manga/comics**, or a **series** downloaded — not just tech.

Default: a **small curated set** of legally free files, catalogued locally, then **delivered in the same turn**.

## License gate (hard)

Download a file only when the rights holder (author, publisher, or public-domain status) offers that file for free keeping.

| Allowed | Forbidden |
|---|---|
| Project Gutenberg, Standard Ebooks, Internet Archive **public-domain** items | LibGen, Z-Library, Anna's Archive, Sci-Hub, dokumen.pub, PDFDrive, Scribd scrapes |
| Author/publisher “free EPUB/PDF” or CC / open textbook | MangaDex, MangaKakalot, MangaNato, Weebcentral, Hitomi, scanlation sites, nyaa |
| Official GitHub/release PDFs, GoalKicker, Green Tea Press, Baen Free Library | Kindle/Amazon/Kobo paid titles, “just rip the EPUB” |
| Public-domain / CC comics (Comic Book Plus, Digital Comic Museum, author CC) | Commercial manga (One Piece, Naruto, JJK, etc.) as files |
| Author-posted sample chapters only, when marked free | Full commercial books found elsewhere on this machine |

If the user names a **commercial** title: say it is not free to download, point at the official store / library / official reader app, and offer a **legal substitute** (same genre or a PD/CC work). Do **not** “just find a PDF.”

Do **not** re-send or copy commercial PDFs found in other trees (app data, BookOrbit, etc.).

**HTML-free ≠ file-free.** Manga Plus, Viz, Webtoon, and many author sites are free to *read in-browser*. Do not scrape or zip their pages unless the publisher posts a downloadable EPUB/PDF/CBZ.

## Library layout (discover, don’t hardcode)

Resolve the library root in this order:

1. `$BOOKS_DIR` if set
2. `~/books/README.md` exists → `~/books`
3. `~/Books` exists → `~/Books`
4. else create `~/books`

```
$LIB/
  README.md                 # catalog of record
  singles/                  # one-off books
  series/<Series_Name>/     # numbered volumes
  manga/<Title>/            # chapters or volumes
```

Treat other `books/` folders (apps, backups) as **separate inventory**. Never assume those files are licensed for redistribution.

Filenames: `Title_Author.ext` or `NN_Title.ext` inside a series/manga folder. ASCII, underscores, no spaces.

## Workflow

1. **Discover the library.** Read `$LIB/README.md` and list existing files. Skip duplicates.
2. **Clarify only if it changes the fetch.** “A few good novels” → pick 4–6 well-known **public-domain** titles. “This manga / this series” → check license first. Genre + “series” → one series, first few volumes.
3. **Find official download URLs.** Search the web for the title + `gutenberg`, `standard ebooks`, `creative commons`, `free epub`, or the author’s site. Confirm the host is on the allow list in `references/legal-sources.md`. HEAD-check: `content-type` must be the file (pdf / epub / octet-stream / zip), not HTML.
4. **Download via the helper** (verifies magic bytes):

```bash
python3 SKILL_DIR/scripts/fetch_legal.py URL --out "$LIB/singles/Title_Author.epub"
python3 SKILL_DIR/scripts/fetch_legal.py URL --out "$LIB/series/Oz/01_The_Wonderful_Wizard_of_Oz.epub"
```

   Fallback if the script is missing: `curl -fL --retry 3 -o FILE URL`, then check magic bytes (`%PDF`, EPUB/CBZ = ZIP `PK`).
5. **Catalog.** Append a row to `$LIB/README.md`: title, author, kind (novel / series / manga), source URL, license note.
6. **Deliver immediately** on Telegram/file-capable chats: one `MEDIA:/abs/path` per file in the same response as the summary. Do not wait for “send me those books.”
7. **Say what you refused** and why (commercial title, scanlation site, HTML-only official reader).

## Picking titles

### Novels / general books
Prefer complete, well-proofed public-domain editions:

- [Standard Ebooks](https://standardebooks.org/ebooks/) — best EPUB typography
- [Project Gutenberg](https://www.gutenberg.org/) — huge catalog; EPUB/Kindle, sometimes PDF
- Author sites and CC publishers (see `references/legal-sources.md`)

A default “few good books” mix if the user is vague: one adventure, one mystery, one SF, one literary classic — all PD (e.g. *Wizard of Oz*, *Sherlock Holmes*, *Frankenstein*, *Pride and Prejudice*).

### Series
- Create `series/<Name>/` and number volumes `01_`, `02_`, …
- Default: **first 3 volumes** unless they asked for the whole series
- Whole series: only if every volume is legally free; cap at **8** unless they explicitly want more
- Verify **each** volume independently (don’t assume vol 1’s license covers later books still in copyright)

### Manga / comics
Legally downloadable Japanese manga is **rare**. Do not pretend otherwise.

Allowed:
- Public-domain US comics (Comic Book Plus, Digital Comic Museum, Internet Archive PD)
- CC / author-posted downloadable comics
- A publisher file that is explicitly “free download”

Not allowed:
- Scanlations of in-copyright manga
- “Read online” official apps scraped to CBZ

If they asked for a current shonen/seinen title: refuse the file, name the official app/store, and offer a PD/CC comic instead.

## Pitfalls

- **Pirate search results dominate.** A Google hit for “Title PDF” is usually illegal. Ignore libgen/zlib/dokumen/pdfdrive even when they rank first.
- **SourceForge `/download`** often 403s or returns HTML. Do not fall back to a pirate mirror. Only another **same-license official** copy.
- **Internet Archive lending ≠ keep.** Controlled Digital Lending and borrowable items are not a download-to-keep license. Only items the page marks for public-domain / CC download.
- **HEAD can lie.** Always verify magic bytes after GET. HTML error pages saved as `.pdf` are a failure.
- **Webtoon / Manga Plus / Viz.** Free to read, not free to archive. Don’t scrape.
- **Series still in copyright.** Early Sherlock Holmes is PD; later Doyle and almost all modern series are not. Check per volume.
- **Delivery.** Saving to disk without `MEDIA:` on Telegram is incomplete for this user.

## Aftercare

Offer a next slice (another genre, next volumes, PD comics, or tech books) rather than dumping 20 titles. Keep `$LIB/README.md` as the inventory of record.