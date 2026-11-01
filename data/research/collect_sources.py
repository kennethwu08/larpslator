"""Refresh the fixed source list and check term spellings; no recursive crawl.

Uses the standard library. Optional pypdf enables text checks for PDF sources.
No full articles or PDFs are saved. Definitions are curated in terms.en-ko.jsonl,
not auto-generated or replaced by this script.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
import time
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
AGENT = "LinguaClipResearch/0.1"
LIMIT = 8 * 1024 * 1024


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def fetch(url):
    with urlopen(Request(url, headers={"User-Agent": AGENT}), timeout=20) as resp:
        data = resp.read(LIMIT + 1)
        if len(data) > LIMIT:
            raise ValueError("Source exceeds 8 MiB collection limit.")
        return data, resp.geturl(), resp.headers.get_content_charset() or "utf-8"


def allowed(url):
    origin = urlsplit(url)
    robots_url = f"{origin.scheme}://{origin.netloc}/robots.txt"
    try:
        data, _, encoding = fetch(robots_url)
        robot = RobotFileParser()
        robot.parse(data.decode(encoding, errors="replace").splitlines())
        return robot.can_fetch(AGENT, url), "checked"
    except Exception:
        # Fail closed for the repeatable collector; manual web review can remain.
        return False, "unavailable; skipped"


def normalized(s):
    return re.sub(r"\s+", "", s).casefold()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    sources = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))
    terms = [json.loads(s) for s in (HERE / "terms.en-ko.jsonl").read_text(encoding="utf-8").splitlines()]
    report = []
    checks = []
    for source in sources:
        row = {"source_id": source["id"], "url": source["url"],
               "checked_at_utc": datetime.now(timezone.utc).isoformat()}
        try:
            can_fetch, robots = allowed(source["url"])
            row["robots"] = robots
            if not can_fetch:
                row["status"] = "skipped_robots"
                report.append(row)
                print(source["id"], row["status"], flush=True)
                continue
            data, final_url, encoding = fetch(source["url"])
            row.update(final_url=final_url, bytes=len(data),
                       sha256=hashlib.sha256(data).hexdigest())
            if source["kind"] == "pdf":
                try:
                    from pypdf import PdfReader
                except ImportError:
                    row["status"] = "fetched_pdf_extractor_unavailable"
                    report.append(row)
                    continue
                reader = PdfReader(io.BytesIO(data))
                text = "\n".join(p.extract_text() or "" for p in reader.pages)
                row["pages"] = len(reader.pages)
            else:
                extractor = Text()
                extractor.feed(data.decode(encoding, errors="replace"))
                text = " ".join(extractor.parts)
            row["hangul_characters"] = len(re.findall(r"[가-힣]", text))
            row["status"] = "extracted_in_memory" if row["hangul_characters"] else "no_korean_text_extracted"
            norm = normalized(text)
            for term in terms:
                if source["id"] in term["source_ids"]:
                    checks.append({"term_id": term["id"], "source_id": source["id"],
                                   "preferred_spelling_found": normalized(term["preferred_ko"]) in norm,
                                   "meaning_verified": False})
        except Exception as exc:
            row["status"] = "fetch_failed"
            row["error"] = f"{type(exc).__name__}: {exc}"
        report.append(row)
        print(source["id"], row["status"], flush=True)
        time.sleep(0.5)
    (HERE / "collection_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    (HERE / "spelling_checks.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False)+"\n" for r in checks), encoding="utf-8")


if __name__ == "__main__":
    main()
