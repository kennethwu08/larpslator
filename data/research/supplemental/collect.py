"""Bounded metadata/terminology collection; no full publication redistribution.
Run from any directory: python data/research/supplemental/collect.py
Only source-verified labels are exported. Definitions are authored paraphrases.
"""
import hashlib,json,re,time
from datetime import datetime,timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
HERE=Path(__file__).resolve().parent
AGENT='LarpslatorResearch/0.2'
LIMIT=4*1024*1024
class Text(HTMLParser):
 def __init__(self):super().__init__();self.parts=[];self.hidden=0;self.meta={}
 def handle_starttag(self,tag,attrs):
  if tag in ('script','style'):self.hidden+=1
  a=dict(attrs)
  if tag=='meta' and a.get('content'):self.meta.setdefault(a.get('name',a.get('property','')),[]).append(a['content'])
 def handle_endtag(self,tag):
  if tag in ('script','style'):self.hidden=max(0,self.hidden-1)
 def handle_data(self,data):
  if not self.hidden:self.parts.append(data)
def fetch(url):
 with urlopen(Request(url,headers={'User-Agent':AGENT}),timeout=12) as r:
  raw=r.read(LIMIT+1)
  if len(raw)>LIMIT:raise ValueError('size limit')
  return raw,r.geturl(),r.headers.get('Content-Type','')
def allowed(url):
 u=urlsplit(url);robots=u.scheme+'://'+u.netloc+'/robots.txt'
 try:raw,_,_=fetch(robots)
 except Exception as e:
  if getattr(e,'code',None)==404:return True,'robots.txt absent (404)'
  return False,'robots unavailable: '+str(e)
 rp=RobotFileParser();rp.parse(raw.decode('utf-8',errors='replace').splitlines())
 return rp.can_fetch(AGENT,url),'robots.txt checked'
def main():
 records=[];terms=[]
 for source in json.loads((HERE/'sources.json').read_text(encoding='utf-8')):
  record={'id':source['id'],'url':source['url'],'checked_at_utc':datetime.now(timezone.utc).isoformat()}
  try:
   ok,note=allowed(source['url']);record['robots']=note
   if not ok:record['status']='skipped_robots_or_unavailable'
   else:
    raw,final,kind=fetch(source['url']);record.update(final_url=final,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),content_type=kind)
    if 'html' not in kind:record['status']='non_html_not_extracted'
    else:
     page=Text();page.feed(raw.decode('utf-8',errors='replace'));text=' '.join(page.parts)
     record.update(status='html_retrieved',citation_metadata={k:v for k,v in page.meta.items() if k.startswith('citation_') or k.startswith('DC.')})
     for item in source.get('candidates',[]):
      found=item['preferred'] in text
      if found:terms.append({**item,'domain':source['domain'],'target_language':source['language'],'source_url':final,'source_id':source['id'],'evidence':'preferred spelling occurs in retrieved source; definition is an authored paraphrase','human_review':'pending','runtime_glossary_changed':False})
     record['verified_candidate_spellings']=sum(t['source_id']==source['id'] for t in terms)
  except Exception as e:record.update(status='fetch_failed',error=str(e))
  records.append(record);time.sleep(1)
 (HERE/'collection_report.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 (HERE/'terms.jsonl').write_text(''.join(json.dumps(t,ensure_ascii=False)+'\n' for t in terms),encoding='utf-8')
 print(json.dumps({'sources':len(records),'retrieved':sum(r['status']=='html_retrieved' for r in records),'verified_terms':len(terms),'statuses':{r['id']:r['status'] for r in records}},ensure_ascii=False))
if __name__=='__main__':main()
