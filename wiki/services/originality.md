---
type: service
created: 2026-10-13
source: backend/plagiarism/, frontend/src/components/OriginalityPanel.tsx
---

# Originality (plagiarism) check

Runs on every text/PDF/DOCX submission, after processing (`content.tasks.queue_originality_check`
creates a pending `PlagiarismReport` and sends `plagiarism.tasks.check_submission` by name to
the `ml` queue, so the web process never imports torch). Cache hits are checked too: an identical
file must come out 0% original against its source.

Built the way Turnitin / Антиплагиат work: fingerprint index for candidates, exact alignment for
evidence, plus semantic and cross-language matching.

1. **Fingerprints**: 5-word shingles over normalized tokens (NFKC, lowercase, ё->е, invisible
   characters stripped, Latin/Cyrillic look-alikes folded to the word's majority script, so a
   homoglyph-obfuscated copy still matches). Winnowing (window 4) keeps about a quarter of the
   hashes; `TextFingerprint.fingerprints` is a bigint array with a GIN index, candidates come
   from `fingerprints && $1`.
2. **Exact**: top 15 candidates by fingerprint overlap are re-shingled in full and aligned into
   character spans of the student's text.
3. **Semantic**: sentences (>= 8 words) embedded with `intfloat/multilingual-e5-small` (384-d,
   `SentenceVector`, HNSW cosine). Nearest neighbour per sentence: >= 0.92 listed as reworded,
   counted in the score only at >= 0.95 (classmates write on the same topic; e5 puts unrelated
   sentences near 0.8). A different per-sentence language makes it `translation`.
4. **Web**: up to 8 distinctive sentences (long, many long words) quoted as queries through the
   provider chain `PLAGIARISM_SEARCH_PROVIDERS` (default searxng, brave, ddg) and Wikipedia's own
   full-text search; 8-word key phrases of the same sentences go to OpenAlex and arXiv
   (`plagiarism.academic`, see "Open scientific papers" below). Pages fetched with `safe_get`
   (3 MB HTML cap, 15 MB / 60 pages for PDFs read with `common.documents.extract_pdf`, words split
   by a line-break hyphen joined again), text extracted with trafilatura, aligned by shingles. Time
   caps so one check cannot hold the worker: 30 s per download (`FETCH_SECONDS`, on top of the 12 s
   socket timeout), 150 s for all web pages (`PAGES_SECONDS`), 90 s for paper full texts
   (`PAPER_SECONDS`); past a cap the rest is skipped and abstracts are still compared.
5. **Originality** = 100 x (1 - union of counted spans / text characters).

Same-author work never matches (resubmission is not plagiarism). Privacy in
`plagiarism.serializers.report_payload`: a source the viewer may see (own, class supervised,
staff) shows file, author, class and a link; anything else is "Another ProofLayer submission"
with only the student's own matching excerpt.

Search: Google's Custom Search JSON API is closed to new customers and ends 2027-01-01, so the
default is a self-hosted **SearXNG** (`deploy/compose.prod.yml` service `searxng`,
`deploy/searxng/settings.yml`: google, bing, duckduckgo, yandex, brave engines, JSON on, limiter
off, internal only). DuckDuckGo direct is rate-limited almost immediately (live test returned
202 Ratelimit on the first query), so it is the last fallback. Brave Search API by key is the
paid option.

UI: `OriginalityPanel` on the result page (percentage, sources with share, kind, excerpts);
originality column in the class list and CSV. Result page keeps polling while the report is
pending/running.

## Web search reality check (2026-10-17)

Demo seed showed a verbatim ru.wikipedia paste scoring 100% original. The prod SearXNG answered but every
engine was suspended for the server's IP: google "access denied", brave and google cse "too many requests",
duckduckgo timeout, yandex "parsing error"; bing gave nothing for quoted Russian sentences. So the web part
of the originality check found nothing for anyone. Fixes:
- `plagiarism.search.wikipedia()`: MediaWiki full-text search (`list=search`, quoted sentence) on ru/en/fr
  Wikipedia, called for every distinctive sentence in addition to the general search (setting
  `PLAGIARISM_WIKIPEDIA`, off in tests). Live: the paste is found, 835 of 1049 characters matched.
- SearXNG: mojeek, qwant and startpage engines added; image pulled fresh (yandex parsing errors come
  from stale engine code).
- Reliable whole-web search still needs a key: `BRAVE_SEARCH_API_KEY` (free tier) is already supported
  in the provider chain.

## Honest percentages and visible sources (2026-10-24, Tribunal 1.10.0)

The demo audit found honest work at 68-94% "original" (shared plans, stock phrases, DOIs) and copy
percentages that did not add up. Fixes in `plagiarism.service` and `plagiarism.shingles`:
- Copied runs need 8+ words; URL, `www` and DOI tokens are removed before shingling.
- Wording shared by at least max(3, 30%) of classmates in runs of 30 words or fewer is masked, and so is
  the shadow-set prompt (`COMMON_AUTHORS`, `COMMON_SHARE`, `COMMON_MAX_WORDS`).
- Bibliography after a heading at 40%+ of the text is excluded from matching.
- The share counts letters of whole words; sources under 60 letters (`MIN_SOURCE_CHARS`) or 0.6% are
  dropped, so a match list never sits next to 100% and a share is clamped to 100 - originality.
- Reworded or translated sentences (`PARAPHRASE_SIMILAR` 0.95, `TRANSLATION_SIMILAR` 0.92) fold into the
  exact match of the same source; `kinds` lists both.
- Every excerpt carries `source_excerpts` (the source passage, first and last shingle placed separately);
  hidden sources give `hidden`, `hidden_reason` (`student_view` / `other_class`), no author or id.
- `web_status` (`ok` / `failed` / `short` / `off`, migration 0003) with answered-query count and engines;
  the UI names the scope from it ("web search did not answer this time").

Seed-order simulation of all 80 demo works with the real e5 model: every honest work 100%; left are
Vera from Arina (75.6%), Olga from Ivan (exact plus reworded) and the two hidden-text DOCX (7%).


## Open scientific papers: OpenAlex and arXiv (2026-10-26)

University and school essays copy from papers more than from Wikipedia, and the prod SearXNG engines are all
blocked, so two free catalogues joined the web part (owner rule: free only, no paid APIs, no signups, no
key-only services, no browser scraping). Module `plagiarism.academic`, wired in `plagiarism.web.web_matches`.

- **Queries**: each distinctive sentence gives an 8-word key phrase (`key_phrase`: the window with the most
  words of 7+ letters, punctuation dropped, AND/OR/NOT lowercased so they are not operators). Phrases are
  quoted and OR-combined (`or_groups`) under a URL budget: English texts fit one OpenAlex request, Russian ones
  (percent-encoded Cyrillic) take two. Phrases stay in the text's own language, so Russian essays find Russian
  journals and CyberLeninka; arXiv only gets Latin-script phrases.
- **OpenAlex** (`/works?search=`, searches title, abstract and full text; `select` keeps the payload small,
  `mailto=OPENALEX_MAILTO`). Abstract rebuilt from `abstract_inverted_index`. Full text links: best open
  location PDF, its landing page, `open_access.oa_url`, and any location on CyberLeninka (free to read, but
  OpenAlex marks it closed). Budget reality: without a key every IP shares $0.10 a day and a search costs
  $0.001, so about 100 searches a day, 1-2 per check; a 429 or fewer than 10 credits left pauses OpenAlex until
  `Retry-After` / `X-RateLimit-Reset`. `OPENALEX_API_KEY` (free, 10x budget) is optional, sent as a bearer
  token, and a refused key falls back to keyless. OpenAlex's paid content API is not used.
- **arXiv** (`export.arxiv.org/api/query`, Atom, `all:"phrase" OR ...`). Pacing: one request every 3 s across
  all workers through Redis slots (`wait_turn`: `cache.add` on `plag:arxiv:turn:<slot>`, sleep to the slot
  start, give up after 30 s). arXiv PDFs come from arxiv.org, whose robots.txt says `Crawl-delay: 15`, so they
  get their own slots 15 s apart (`plag:arxiv_pdf:turn:<slot>`, wait capped by the time left for full texts).
  429/503 pause arXiv and its PDFs for 10 minutes
  (or `Retry-After`). The PDF is read only when the title or abstract shares a 5-word shingle with the work.
  Live 2026-10-26 the API also answered 429 "Rate exceeded" after 46 s once, then worked in under a second.
- **Caching**: search answers 7 days (`PLAGIARISM_ACADEMIC_CACHE`), paper full texts 7 days (failed fetches
  1 hour), keyed by query or URL, so a class copying one paper downloads it once. Full texts are stored
  zlib-compressed: the prod Redis is also the Celery broker and has no `maxmemory`.
- **Matching**: up to `PLAGIARISM_PAPER_TEXTS` (4) full texts per check; source text = title + abstract +
  full text, aligned by shingles like web pages (the e5 sentence matching is internal only). The reference
  list is still cut by `body_end` / the skip mask, so its titles are neither searched nor matched. A work
  that quotes a paper with a proper citation still shows the paper as a source; the teacher judges context.
  `body_end` knows the same headings as the citation check (`Источники`, `Использованные источники`,
  `Sources`, `Literature`, `Literature cited`, `Sources et références` were missing). The paper's own title is
  masked in the work for that paper (`title_skip`), so naming a paper by its title, in the text or in a
  reference list whose heading is not recognized, is not copying from it.
  Same paper twice: identity is the title, the arXiv id (abs/pdf links and DOI `10.48550/arXiv.*`) and the
  DOI (`paper_keys`); the arXiv record wins (canonical link, free PDF). OpenAlex keeps records of arXiv
  papers under the arXiv DOI with a wrong title (live: LoRA listed as "LoRA Fine-Tuning of a 3B Code LLM").
- **Match rows**: `source: "web"` plus `engine` (`web`, `wikipedia`, `openalex`, `arxiv`), and for papers
  `authors` (first 5), `authors_total`, `year`, `venue` (arXiv: `journal_ref` or "arXiv"). The UI shows
  "Scientific paper · authors · year · venue"; the PDF report adds "(authors et al., year, venue)".
- **web_status / engines**: an engine is named only if it answered; one whose pages all failed to open is
  dropped; no engine left means `failed`. The scope sentence is built from the engines: "Compared with
  students' work in ProofLayer, Wikipedia, open scientific papers and a web search", minus what did not
  answer. The PDF report names the catalogues that answered ("open scientific papers (arXiv)").
  Privacy, Data Processing (both languages) and the school web search setting name Wikipedia,
  OpenAlex and arXiv.
- **Live smoke** (2026-10-26, not a test): an essay with three sentences of the "Attention Is All You Need"
  abstract found the arXiv paper (2017, PDF 39.6k chars, before the arXiv-first rule an odd 2025 OpenAlex
  duplicate record took its place) and three OpenAlex papers that reuse the abstract, 9 s in all; a Russian
  essay with three sentences from the body of a CyberLeninka paper (not its abstract) was found through
  OpenAlex full-text search, the full text came from CyberLeninka after the journal's own link failed on an
  expired certificate, 512 characters matched.
- **Review smoke** (2026-10-26, same pipeline as `run_check` minus classmates, Wikipedia on, SearXNG off):
  English essay with three sentences of the LoRA abstract (arXiv 2106.09685) plus its reference: the arXiv
  paper (PDF read), 440 chars, 28% original, plus two OpenAlex papers that reuse LoRA sentences (120 and 85
  chars); the broken OpenAlex record of LoRA is no longer listed. Russian essay with three body sentences of
  a Tver State University PDF (eprints.tversu.ru): found through OpenAlex full-text search, 481 chars after
  joining hyphenated line breaks (401 before), 24.6% original. Russian essay with three abstract sentences
  of a 2025 Management of Education paper: 497 chars, 23.7%. An honest English essay, an English essay
  that names the LoRA paper and an honest Russian essay that names a paper's 8-word title in its text (and
  lists it under "Источники:"): 100% each; the last one would read 80.5% without the title mask (OpenAlex
  returns that paper for the title phrase). 3 to 39 s per check.
