# Legal download sources

Confirm the specific file is offered for free keeping. Hosts change; HEAD-check every URL.

## General books (any genre)

| Source | What you get | Notes |
|---|---|---|
| [Standard Ebooks](https://standardebooks.org/ebooks/) | EPUB (and Kindle) of public-domain literature | Best typesetting. Open each book page and use the official EPUB link. |
| [Project Gutenberg](https://www.gutenberg.org/) | EPUB, Kindle; PDF sometimes | Search → book page → “EPUB3 (with images)”. IDs look like `/ebooks/84`. Direct: `https://www.gutenberg.org/ebooks/<id>.epub.images` |
| [Internet Archive](https://archive.org/) | PDF/EPUB of **public-domain** or CC items | Only when the item page shows a downloadable PD/CC file. Skip “Borrow”. |
| Author / publisher site | Whatever they post | Green Tea Press, personal sites, university pages. Must be their file. |
| [Baen Free Library](https://www.baen.com/allbooks/category/index/id/2012) | Official free SF/F ebooks | Publisher-authorized. |
| [EbookFoundation/free-programming-books](https://github.com/EbookFoundation/free-programming-books) | Index of legal tech books | Index only — still fetch from the listed official URL. |

### Gutenberg quick pattern

```bash
# Book page: https://www.gutenberg.org/ebooks/11
curl -fL -o Alice_Lewis_Carroll.epub \
  "https://www.gutenberg.org/ebooks/11.epub.images"
```

If `.epub.images` 404s, try `.epub.noimages`.

### Standard Ebooks pattern

Open the book page (e.g. `https://standardebooks.org/ebooks/mary-shelley/frankenstein`) and download the `…/downloads/…epub` link from that page. Do not guess CDN paths.

## Tech / CS (subset)

| Book | Official URL |
|---|---|
| Think Python 2e — Downey | https://greenteapress.com/thinkpython2/thinkpython2.pdf |
| Think OS — Downey | https://greenteapress.com/thinkos/thinkos.pdf |
| Think Data Structures — Downey | https://greenteapress.com/thinkdast/thinkdast.pdf |
| Eloquent JavaScript — Haverbeke | https://eloquentjavascript.net/Eloquent_JavaScript_small.pdf |
| Pro Git 2e | GitHub `progit/progit2` latest release `progit.pdf` |
| The Linux Command Line — Shotts | https://linuxcommand.org/tlcl.php (SourceForge often 403 to curl) |
| GoalKicker Notes | https://goalkicker.com/ — `PythonBook`, `JavaScriptBook`, `AlgorithmsBook` PDFs |
| SICP 2e (CC typeset) | https://media.githubusercontent.com/media/sarabander/sicp-pdf/master/sicp.pdf |
| Competitive Programmer's Handbook | https://cses.fi/book/book.pdf |
| Algorithms — Jeff Erickson | https://jeffe.cs.illinois.edu/teaching/algorithms/book/Algorithms-JeffE.pdf |
| Open Data Structures (Java, screen) | https://opendatastructures.org/ods-java-screen.pdf |

HTML-free, PDF often paid: Crafting Interpreters, The Rust Book, OSTEP full book, AOSA.

Commercial tech — do not download: CTCI; Beyond CTCI (full); DDIA; EPI; Grokking *; Alex Xu / ByteByteGo; CLRS print.

## Manga / comics

| Source | What you get | Notes |
|---|---|---|
| [Comic Book Plus](https://comicbookplus.com/) | Public-domain US comics | Golden/Silver Age. Legal PD scans. |
| [Digital Comic Museum](https://digitalcomicmuseum.com/) | Public-domain US comics | Account may be required; still PD. |
| Internet Archive PD comics | CBZ/PDF | Item must be PD/CC, not borrowed. |
| Author CC / “free download” page | EPUB/PDF/CBZ | Only if the author posted the file. |

**Not sources:** MangaDex, MangaKakalot, MangaNato, Weebcentral, Comick, Hitomi, nhentai, nyaa, any scanlation aggregator.

Official readers (Manga Plus, Viz Shonen Jump, Webtoon, Tapas): free to read in-app, **not** a download-to-keep license.

## Series (public domain examples)

Verify each volume. These sets are commonly PD in the US:

- Oz — L. Frank Baum (early volumes; later Baum/Thompson may differ)
- Sherlock Holmes — Arthur Conan Doyle (early novels/stories; check later tales)
- Alice books — Lewis Carroll
- Anne of Green Gables — L. M. Montgomery (early volumes)
- Tarzan — early Burroughs novels (check per title)
- Barsoom / John Carter — early Burroughs
- Tom Swift, Rover Boys, and similar pre-1929 series

Modern series (Harry Potter, LOTR print, Hunger Games, One Piece, etc.) are **not** free files.

## Blocked hosts (never fetch)

`libgen`, `library genesis`, `zlib`, `z-library`, `annas-archive`, `anna’s archive`, `sci-hub`, `dokumen.pub`, `pdfdrive`, `scribd.com/document` scrapes, `mangadex`, `mangakakalot`, `manganato`, `weebcentral`, `comick`, `hitomi.la`.