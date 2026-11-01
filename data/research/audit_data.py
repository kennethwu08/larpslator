"""Validate data artifacts without importing backend code or contacting an API."""
import json,re,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def pairs(items):
 out={}
 for k,v in items:
  if k in out:raise ValueError('duplicate JSON key: '+k)
  out[k]=v
 return out
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'),object_pairs_hook=pairs)
def script(s):
 if re.search('[\uac00-\ud7a3]',s):return 'Korean'
 if re.search('[\u0b80-\u0bff]',s):return 'Tamil'
 return 'English'
def norm(term,value):
 if isinstance(value,dict):return {k:v for k,v in value.items() if isinstance(v,list)}
 if isinstance(value,str):return {script(value):[value]}
 if isinstance(value,list) and value and script(value[0])!=script(term):return {script(value[0]):value}
 return {}
def main():
 errors=[];files=0;rows=0;coverage={};conflicts=[]
 for p in sorted(ROOT.rglob('*')):
  if p.suffix not in ('.json','.jsonl'):continue
  if p.name=='data-audit.json':continue
  files+=1
  try:
   if p.suffix=='.json':read(p)
   else:
    for n,line in enumerate(p.read_text(encoding='utf-8-sig').splitlines(),1):
     if line.strip():json.loads(line,object_pairs_hook=pairs);rows+=1
  except Exception as e:errors.append({'file':str(p.relative_to(ROOT)),'error':str(e)})
 for domain in ['cs','tennis','pickleball','math']:
  sources=[ROOT/'glossaries'/f'{domain}.json']
  if domain=='math':sources.append(ROOT/'glossaries/academia.json')
  merged={}
  for p in sources:
   if not p.exists():continue
   for term,v in read(p).items():
    entry=norm(term,v)
    if not isinstance(term,str) or not term.strip() or not entry:errors.append({'file':str(p.relative_to(ROOT)),'term':term,'error':'empty or skipped glossary entry'});continue
    for lang,opts in entry.items():
     if not opts or any(not isinstance(x,str) or not x.strip() for x in opts):errors.append({'file':str(p.relative_to(ROOT)),'term':term,'error':'invalid options'});continue
     merged.setdefault(term,{}).setdefault(lang,[]).extend(opts)
  for p in sorted((ROOT/'glossaries/selected').glob(domain+'-*.json')):
   for term,value in read(p).items():
    if not isinstance(value,str) or not value.strip():errors.append({'file':str(p.relative_to(ROOT)),'term':term,'error':'selected value must be a nonempty string'});continue
    lang=script(value);existing=merged.setdefault(term,{}).setdefault(lang,[])
    if existing and existing[0]!=value:conflicts.append({'domain':domain,'term':term,'language':lang,'main_preferred':existing[0],'selected_preferred':value})
    if value not in existing:existing.append(value)
  coverage[domain]={'unique_source_terms':len(merged),'English_to_Tamil':sum(script(t)=='English' and bool(v.get('Tamil')) for t,v in merged.items()),'English_to_Korean':sum(script(t)=='English' and bool(v.get('Korean')) for t,v in merged.items()),'Tamil_source_terms':sum(script(t)=='Tamil' for t in merged)}
 evaluation=[json.loads(l) for l in (ROOT/'eval-ta.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
 for n,row in enumerate(evaluation,1):
  if row.get('domain') not in coverage:errors.append({'file':'eval-ta.jsonl','row':n,'error':'unknown domain'})
 report={'checked_at_utc':datetime.now(timezone.utc).isoformat(),'scope':'data only; structural consistency, not semantic translation or deployed API validation','status':'pass' if not errors and not conflicts else 'review_required','json_and_jsonl_files_checked':files,'jsonl_rows_parsed':rows,'errors':errors,'preference_conflicts':conflicts,'glossary_coverage_before_builtin_seeds':coverage,'evaluation_rows':len(evaluation),'warnings':['Tamil wording and evaluation references await human review.','No Tamil-source terms: reverse Tamil glossary matching is not covered by this contribution.','med.json is legacy and not loaded; academia.json is the supported math alias.','FASTAPI_ENTRYPOINT_NOT_FOUND is a deployment configuration failure, not a data parse failure.','Vercel was connected to JustinC-08/larpslator; earlier dashboard push targeted kennethwu08/larpslator. Verify intended repository with deployment owner.']}
 (ROOT/'research/data-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(report,ensure_ascii=False,indent=2))
 return 1 if errors or conflicts else 0
if __name__=='__main__':sys.exit(main())
