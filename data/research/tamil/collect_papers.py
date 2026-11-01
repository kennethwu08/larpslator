"""Collect bibliographic metadata and licensed full text for the Tamil research pack.

English sports sources remain English. Tamil summaries are separate authored
content and are never represented as published Tamil papers. No API key needed.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
LIMIT = 12 * 1024 * 1024
AGENT = "LinguaClipAcademicResearch/0.1"


def fetch(url):
    with urlopen(Request(url, headers={"User-Agent": AGENT}), timeout=20) as r:
        data = r.read(LIMIT + 1)
        if len(data) > LIMIT:
            raise ValueError("Response exceeds 12 MiB limit")
        return data, r.geturl()


def text(node):
    return " ".join("".join(node.itertext()).split()) if node is not None else ""


def main():
    records = [json.loads(s) for s in (HERE / "papers.jsonl").read_text(encoding="utf-8").splitlines()]
    report = []
    folder = HERE / "licensed_fulltext"
    folder.mkdir(exist_ok=True)
    for record in records:
        entry = {"id":record["id"],"checked_at_utc":datetime.now(timezone.utc).isoformat(),
                 "source_language":record["source_language"]}
        if record["source_language"] == "ta":
            # Do not redistribute a journal that reserves reproduction rights.
            entry.update(status="bibliographic_record_only",
                         evidence=record["evidence"],
                         reason="Publisher metadata reviewed through web research; direct fetch failed or timed out. No full Tamil paper saved.",
                         url=record["url"])
            report.append(entry)
            continue
        try:
            query = urlencode({"query":'DOI:"'+record["doi"]+'"',"format":"json","resultType":"core"})
            search_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?"+query
            data, _ = fetch(search_url)
            hits=json.loads(data)["resultList"]["result"]
            hit=next((h for h in hits if h.get("doi","").lower()==record["doi"].lower()),None)
            if hit is None:
                raise ValueError("DOI not found in Europe PMC")
            pmcid=hit.get("pmcid")
            entry["bibliographic_metadata"]={k:hit.get(k) for k in
                ("id","source","pmcid","doi","title","authorString","pubYear","isOpenAccess")}
            if not pmcid:
                entry["status"]="metadata_only_no_open_fulltext"
            else:
                xml_url=f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
                xml_data, final_url=fetch(xml_url)
                article=ET.fromstring(xml_data)
                license_nodes=article.findall(".//permissions/license")
                license_text=" ".join(text(n) for n in license_nodes)
                license_links=" ".join(str(v) for n in license_nodes for child in n.iter() for v in child.attrib.values())
                cc_by=("creativecommons.org/licenses/by/" in license_links
                       or "creativecommons.org/licenses/by/".replace("https://","") in license_text)
                entry.update(fulltext_url=final_url,license_notice=license_text,
                             license_links=license_links,license_verified_cc_by=cc_by)
                if not cc_by:
                    entry["status"]="metadata_only_license_not_verified"
                else:
                    (folder/f'{record["id"]}.xml').write_bytes(xml_data)
                    abstract=text(article.find("./front/article-meta/abstract"))
                    body=article.find("./body")
                    body_text="\n\n".join(text(n) for n in list(body)) if body is not None else ""
                    if len(body_text)<500:
                        raise ValueError("Full-text body is missing or too short")
                    authors=entry["bibliographic_metadata"].get("authorString","")
                    header=(f'{record["title"]}\nAuthors: {authors}\nDOI: {record["doi"]}\n'
                            f'Source: {record["url"]}\nXML source: {final_url}\n'
                            f'Original language: English (NOT Tamil)\n'
                            f'License: {license_text}\n'
                            'Modification: article abstract/body extracted to plain text; formatting removed.\n\n')
                    (folder/f'{record["id"]}.txt').write_text(header+abstract+"\n\n"+body_text+"\n",encoding="utf-8")
                    entry.update(status="licensed_english_fulltext_saved",
                                 sha256_xml=hashlib.sha256(xml_data).hexdigest(),
                                 body_characters=len(body_text),
                                 local_xml=f'licensed_fulltext/{record["id"]}.xml',
                                 local_text=f'licensed_fulltext/{record["id"]}.txt')
        except Exception as exc:
            entry.update(status="fetch_failed",error=f"{type(exc).__name__}: {exc}")
        report.append(entry)
        print(record["id"],entry["status"],flush=True)
        time.sleep(0.5)
    (HERE/"collection_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    # Reflect actual outcomes rather than claiming successful scraping from seeds.
    outcomes={r["id"]:r for r in report}
    for record in records:
        outcome=outcomes[record["id"]]
        record["full_text_saved"]=outcome["status"]=="licensed_english_fulltext_saved"
        if record["full_text_saved"]:
            record["local_full_text"]=outcome["local_text"]
            record["authors"]=outcome["bibliographic_metadata"]["authorString"]
        else:
            record.pop("local_full_text",None)
    (HERE/"papers.jsonl").write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in records),encoding="utf-8")


if __name__ == "__main__":
    main()
