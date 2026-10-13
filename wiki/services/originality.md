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
   provider chain `PLAGIARISM_SEARCH_PROVIDERS` (default searxng, brave, ddg); pages fetched with
   `safe_get` (3 MB cap), text extracted with trafilatura, aligned by shingles.
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
