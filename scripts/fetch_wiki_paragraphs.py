#!/usr/bin/env python3
import argparse
import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

USER_AGENT = "ProofLayerDatasetBuilder/1.0 (text detector research; https://prooflayer.cloud)"
CUTOFF = "2021-12-31T23:59:59Z"
PARAGRAPH = re.compile(r"<p>(.*?)</p>", re.S)
TAG = re.compile(r"<[^>]+>")
REF = re.compile(r"\[(?:\d+|[a-z]|note \d+|citation needed|нет АИ|источник не указан \d+ дней|réf\. nécessaire)\]")
SPACES = re.compile(r"\s+")


def bucket(key: str) -> float:
    return int(hashlib.sha1(key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def split_for(key: str) -> str:
    value = bucket(f"{key}:wiki")
    if value < 0.15:
        return "test"
    if value < 0.32:
        return "calib"
    return "train"


def api(lang: str, params: dict) -> dict:
    query = urllib.parse.urlencode({**params, "format": "json", "formatversion": 2})
    request = urllib.request.Request(f"https://{lang}.wikipedia.org/w/api.php?{query}", headers={"User-Agent": USER_AGENT})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            retry_after = exc.headers.get("Retry-After", "") if exc.headers else ""
            time.sleep(int(retry_after) if retry_after.isdigit() else 5 * 2 ** attempt)
        except OSError:
            time.sleep(2 ** attempt)
    return {}


def random_titles(lang: str, count: int) -> list[str]:
    data = api(lang, {"action": "query", "list": "random", "rnnamespace": 0, "rnlimit": count})
    return [page["title"] for page in data.get("query", {}).get("random", [])]


def old_revision(lang: str, title: str) -> tuple[int, str] | None:
    data = api(
        lang,
        {"action": "query", "prop": "revisions", "titles": title, "rvlimit": 1, "rvstart": CUTOFF, "rvdir": "older", "rvprop": "ids|timestamp"},
    )
    pages = data.get("query", {}).get("pages", [])
    revisions = pages[0].get("revisions") if pages else None
    if not revisions:
        return None
    return revisions[0]["revid"], revisions[0]["timestamp"]


def paragraphs(lang: str, oldid: int) -> list[str]:
    data = api(lang, {"action": "parse", "oldid": oldid, "prop": "text", "disablelimitreport": 1, "disableeditsection": 1})
    body = data.get("parse", {}).get("text", "")
    out = []
    for raw in PARAGRAPH.findall(body):
        text = SPACES.sub(" ", REF.sub("", html.unescape(TAG.sub("", raw)))).strip()
        if len(text.split()) >= 40 and text.endswith((".", "!", "?", "»", '"', ")")):
            out.append(text)
    return out


def passage(parts: list[str], min_words: int, max_words: int) -> str | None:
    for start in range(len(parts)):
        chunk = []
        for part in parts[start:]:
            chunk.append(part)
            words = sum(len(p.split()) for p in chunk)
            if words >= min_words:
                return "\n\n".join(chunk) if words <= max_words else None
    return None


def fetch_one(lang: str, title: str, excluded: set[str]) -> dict | None:
    if title.lower() in excluded:
        return None
    revision = old_revision(lang, title)
    if revision is None:
        return None
    oldid, timestamp = revision
    text = passage(paragraphs(lang, oldid), 110, 320)
    if text is None:
        return None
    rid = f"wiki-{lang}-{oldid}"
    return {"id": rid, "lang": lang, "title": title, "oldid": oldid, "timestamp": timestamp, "split": split_for(rid), "text": text}


def excluded_titles(path: Path) -> set[str]:
    if not path.exists():
        return set()
    titles = set()
    for row in map(json.loads, open(path)):
        match = re.search(r"'(.+?)'", row.get("attribution", ""))
        if match:
            titles.add(match.group(1).lower())
    return titles


def main():
    parser = argparse.ArgumentParser(description="Fetch human Wikipedia passages as of 2021-12-31 for the text classifier")
    parser.add_argument("--langs", nargs="*", default=["en", "ru", "fr"])
    parser.add_argument("--per-lang", type=int, default=1200)
    parser.add_argument("--raw", default="dataset/text_raw")
    parser.add_argument("--seeds", default="dataset/text_gen/wiki_seeds.jsonl")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    raw = Path(args.raw)
    excluded = excluded_titles(raw / "textsight_human_wiki.jsonl")
    seeds = []
    for lang in args.langs:
        path = raw / f"wiki_{lang}.jsonl"
        rows = [json.loads(line) for line in open(path)] if path.exists() else []
        seen = {r["title"] for r in rows}
        failures = 0
        with open(path, "a") as fh, ThreadPoolExecutor(args.workers) as pool:
            while len(rows) < args.per_lang:
                fresh = random_titles(lang, 50)
                failures = 0 if fresh else failures + 1
                if failures >= 5:
                    raise SystemExit(f"{lang}: Wikipedia API unreachable, check network and SSL_CERT_FILE")
                if not fresh:
                    time.sleep(60)
                    continue
                titles = [t for t in fresh if t not in seen]
                seen.update(titles)
                for row in pool.map(lambda t: fetch_one(lang, t, excluded), titles):
                    if row is None or len(rows) >= args.per_lang:
                        continue
                    rows.append(row)
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                fh.flush()
                print(f"{lang} {len(rows)}/{args.per_lang}", flush=True)
        for r in rows:
            seeds.append(
                {
                    "id": f"wiki-seed-{r['id']}",
                    "lang": lang,
                    "split": r["split"],
                    "hint": r["title"],
                    "genre": "wiki",
                    "words": max(110, min(300, len(r["text"].split()))),
                    "human_id": r["id"],
                }
            )
    Path(args.seeds).parent.mkdir(parents=True, exist_ok=True)
    with open(args.seeds, "w") as fh:
        for seed in seeds:
            fh.write(json.dumps(seed, ensure_ascii=False) + "\n")
    print(f"{len(seeds)} seeds -> {args.seeds}")


if __name__ == "__main__":
    main()
