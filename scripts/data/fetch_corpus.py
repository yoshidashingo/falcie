#!/usr/bin/env python3
"""Fetch a small held-out, public-domain corpus for the tokenizer vocab bakeoff.

Loop L-003. Dependency-free (standard library only). This script implements the
`data-policy.md` rule that **raw datasets are not committed** — instead the repo
keeps this retrieval script, a provenance manifest, and content hashes. Running it
downloads public-domain / permissively-licensed text, cleans it, and writes a
held-out training corpus to a local (gitignored) path. The trained-tokenizer
*report* (not the corpus) is the committed artifact.

Sources (all reachable and verified 2026-06-20):
  * Japanese: Aozora Bunko works whose copyright has expired (public domain). The
    ruby-zip link is discovered from each work's card page, the Shift-JIS text is
    extracted, and Aozora markup (ruby 《...》, base marker ｜, annotations ［＃...］,
    the 凡例 header block, and the 底本 footer) is stripped.
  * English: Project Gutenberg plain-text public-domain works; the Gutenberg
    START/END wrapper is stripped, leaving the public-domain body.
  * Code: a CPython standard-library file (PSF license, permissive).

Usage:
    python3 scripts/data/fetch_corpus.py                 # -> data/bakeoff/corpus.jsonl
    python3 scripts/data/fetch_corpus.py --max-bytes-per-lang 200000
    python3 scripts/data/fetch_corpus.py --manifest-only  # write manifest, no fetch

Output JSONL records: {"id", "language", "domain", "source", "text"} — one record
per paragraph, matching the probe schema so the scorer can consume it.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "data" / "bakeoff" / "corpus.jsonl"
MANIFEST = ROOT / "configs" / "data" / "bakeoff-corpus.manifest.json"
SNAPSHOT = "2026-06-20"
USER_AGENT = "falcie-tokenizer-bakeoff/1.0 (research; dependency-free)"

# Public-domain Japanese works (Aozora Bunko). card -> the work's card page; the
# ruby-zip is discovered from the page so we never hardcode a fragile filename.
AOZORA = [
    ("akutagawa_rashomon", "羅生門 / 芥川龍之介", "https://www.aozora.gr.jp/cards/000879/card127.html"),
    ("akutagawa_kumo", "蜘蛛の糸 / 芥川龍之介", "https://www.aozora.gr.jp/cards/000879/card92.html"),
    ("natsume_kokoro", "こころ / 夏目漱石", "https://www.aozora.gr.jp/cards/000148/card773.html"),
    ("natsume_botchan", "坊っちゃん / 夏目漱石", "https://www.aozora.gr.jp/cards/000148/card752.html"),
    ("dazai_hashire", "走れメロス / 太宰治", "https://www.aozora.gr.jp/cards/000035/card1567.html"),
    ("miyazawa_chumon", "注文の多い料理店 / 宮沢賢治", "https://www.aozora.gr.jp/cards/000081/card43754.html"),
]

# Public-domain English works (Project Gutenberg).
GUTENBERG = [
    ("gutenberg_alice", "Alice's Adventures in Wonderland / Lewis Carroll",
     "https://www.gutenberg.org/files/11/11-0.txt"),
    ("gutenberg_pride", "Pride and Prejudice / Jane Austen",
     "https://www.gutenberg.org/cache/epub/1342/pg1342.txt"),
]

# Permissively-licensed code (CPython stdlib, PSF license).
CODE = [
    ("cpython_argparse", "CPython Lib/argparse.py (PSF)",
     "https://raw.githubusercontent.com/python/cpython/main/Lib/argparse.py"),
]


def _get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


# -- cleaning ---------------------------------------------------------------

_RUBY = re.compile(r"《[^》]*》")
_ANNOT = re.compile(r"［＃[^］]*］")
_SEP = re.compile(r"^[\-―ー=_]{8,}\s*$")


def clean_aozora(raw: bytes) -> str:
    """Decode Shift-JIS and strip Aozora ruby/annotation markup, header, footer."""
    text = raw.decode("shift_jis", errors="replace").replace("\r\n", "\n")
    lines = text.split("\n")

    # Drop the 凡例 block bracketed by the first two separator lines, if present.
    sep_idx = [i for i, ln in enumerate(lines) if _SEP.match(ln)]
    if len(sep_idx) >= 2:
        lines = lines[sep_idx[1] + 1:]

    # Drop the 底本 footer onward.
    for i, ln in enumerate(lines):
        if ln.startswith("底本：") or ln.startswith("底本:"):
            lines = lines[:i]
            break

    body = "\n".join(lines)
    body = _RUBY.sub("", body)
    body = _ANNOT.sub("", body)
    body = body.replace("｜", "").replace("|", "")
    return body.strip()


_GUT_START = re.compile(r"\*\*\*\s*START OF TH[EI]S?[^\n]*PROJECT GUTENBERG[^\n]*\*\*\*", re.I)
_GUT_END = re.compile(r"\*\*\*\s*END OF TH[EI]S?[^\n]*PROJECT GUTENBERG[^\n]*\*\*\*", re.I)


def clean_gutenberg(raw: bytes) -> str:
    """Decode UTF-8 and strip the Project Gutenberg START/END wrapper."""
    text = raw.decode("utf-8-sig", errors="replace").replace("\r\n", "\n")
    m_start = _GUT_START.search(text)
    if m_start:
        text = text[m_start.end():]
    m_end = _GUT_END.search(text)
    if m_end:
        text = text[:m_end.start()]
    return text.strip()


def clean_code(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace").replace("\r\n", "\n").strip()


def discover_aozora_zip(card_url: str) -> str:
    """Find the ruby-zip download URL from an Aozora card page."""
    html = _get(card_url).decode("shift_jis", errors="replace")
    base = card_url.rsplit("/", 1)[0]
    m = re.search(r'href="(?:\./)?files/(\d+_ruby_\d+\.zip)"', html)
    if not m:
        m = re.search(r'href="(?:\./)?files/([^"]+\.zip)"', html)
    if not m:
        raise RuntimeError(f"no zip link found on {card_url}")
    return f"{base}/files/{m.group(1)}"


def fetch_aozora_text(card_url: str) -> str:
    zip_url = discover_aozora_zip(card_url)
    data = _get(zip_url)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        txt_names = [n for n in zf.namelist() if n.lower().endswith(".txt")]
        if not txt_names:
            raise RuntimeError(f"no .txt in {zip_url}")
        return clean_aozora(zf.read(txt_names[0]))


# -- paragraphs / output ----------------------------------------------------

def paragraphs(text: str, fine: bool = False) -> list[str]:
    """Split into non-trivial paragraphs.

    Blank-line runs always separate paragraphs. With ``fine=True`` (used for
    Aozora, whose bodies use single-newline line breaks and rarely blank lines)
    any newline separates too — otherwise a whole work collapses into one giant
    paragraph and the held-out split becomes document-granular instead of
    paragraph-granular.
    """
    splitter = r"\n+" if fine else r"\n\s*\n"
    out: list[str] = []
    for chunk in re.split(splitter, text):
        p = " ".join(chunk.split())
        if len(p) >= 8:
            out.append(p)
    return out


def gather(language: str, domain: str, items, cleaner, max_bytes: int) -> tuple[list[dict], list[dict]]:
    """Return (records, provenance) for one language slice, capped at max_bytes."""
    records: list[dict] = []
    provenance: list[dict] = []
    used = 0
    for key, title, url in items:
        try:
            if domain == "literature" and language == "ja":
                text = fetch_aozora_text(url)
            else:
                text = cleaner(_get(url))
        except Exception as exc:  # noqa: BLE001 — report and continue, do not abort the run
            print(f"  WARN  {key}: {exc!r}", file=sys.stderr)
            provenance.append({"id": key, "title": title, "source": url, "status": "failed", "error": repr(exc)})
            continue
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        src_bytes = 0
        n_before = len(records)
        all_paras = paragraphs(text, fine=(language == "ja"))
        for idx, para in enumerate(all_paras):
            pb = len(para.encode("utf-8"))
            if used + pb > max_bytes:
                break
            records.append({"id": f"{key}-{idx:04d}", "language": language, "domain": domain, "source": key, "text": para})
            used += pb
            src_bytes += pb
        used_paras = len(records) - n_before
        # cap_reached = this source actually lost paragraphs to the per-language byte
        # cap (not merely "the cap was full on entry"). Be explicit when a source was
        # fetched fine but contributed nothing, so "ok" with 0 paragraphs can't mislead.
        truncated = used_paras < len(all_paras)
        status = "ok" if used_paras > 0 else "ok_truncated_by_cap"
        provenance.append({
            "id": key, "title": title, "source": url, "snapshot": SNAPSHOT,
            "license": "public-domain" if domain == "literature" else "permissive (PSF)",
            "language": language, "domain": domain, "status": status,
            "cap_reached": truncated, "sha256_full_clean": sha,
            "paragraphs_used": used_paras, "bytes_used": src_bytes,
        })
        print(f"  ok    {key}: +{len(records) - n_before} paras, {src_bytes}B (cap {max_bytes}B, used {used}B)")
        if used >= max_bytes:
            break
    return records, provenance


def write_manifest(provenance: list[dict], totals: dict) -> None:
    manifest = {
        "name": "tokenizer-bakeoff-corpus",
        "version": SNAPSHOT,
        "use": "tokenizer-training (evaluation; not model pretraining)",
        "note": "Held-out corpus for the L-003 vocab bakeoff. Per data-policy.md the "
                "raw corpus is NOT committed; regenerate with scripts/data/fetch_corpus.py.",
        "retrieval_script": "scripts/data/fetch_corpus.py",
        "filters": ["aozora_markup_strip", "gutenberg_wrapper_strip", "paragraph_split", "per_language_byte_cap"],
        "totals": totals,
        "sources": provenance,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {MANIFEST.relative_to(ROOT)}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--max-bytes-per-lang", type=int, default=300_000,
                    help="Cap per language slice to bound pure-Python BPE training time.")
    ap.add_argument("--manifest-only", action="store_true",
                    help="Do not fetch; only (re)write the manifest skeleton.")
    args = ap.parse_args(argv[1:])

    if args.manifest_only:
        write_manifest([], {})
        return 0

    print("fetching Japanese (Aozora, public domain)…")
    ja, ja_prov = gather("ja", "literature", AOZORA, None, args.max_bytes_per_lang)
    print("fetching English (Gutenberg, public domain)…")
    en, en_prov = gather("en", "literature", GUTENBERG, clean_gutenberg, args.max_bytes_per_lang)
    print("fetching code (CPython, PSF)…")
    code, code_prov = gather("code", "code", CODE, clean_code, args.max_bytes_per_lang)

    records = ja + en + code
    if not records:
        print("ERROR: no records fetched (network?). Nothing written.", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def lang_bytes(recs):
        return sum(len(r["text"].encode("utf-8")) for r in recs)

    totals = {
        "records": len(records),
        "bytes": lang_bytes(records),
        "by_language": {"ja": lang_bytes(ja), "en": lang_bytes(en), "code": lang_bytes(code)},
        "corpus_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
    }
    write_manifest(ja_prov + en_prov + code_prov, totals)
    print(f"wrote {args.output.relative_to(ROOT)} — {totals['records']} paras, {totals['bytes']}B "
          f"(ja={totals['by_language']['ja']} en={totals['by_language']['en']} code={totals['by_language']['code']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
