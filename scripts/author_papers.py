#!/usr/bin/env python3
"""Author method-tree audit using only public, cached metadata.

Reproduce the retained audit offline:
     python scripts/author_papers.py --build
     python scripts/author_papers.py --check

Refresh discovery: --fetch, --crosscheck, --resolve, --enrich; then review
new stable work keys in tmp/authors/decisions.json before --build. --fetch
never changes the TSV. The index-based review_work.py records adjudication
of this frozen snapshot, rather than an automatic future classification.

Fetch exhausts author pages without year limits. Build uses the retained, title-and-
abstract review in tmp/authors/decisions.json; no network is used by build/check.
Raw responses use the project's URL-SHA256 cache convention. Review, exclusions,
version links and discovery coverage are retained under tmp/authors/.
"""
import argparse
import csv
import fcntl
import hashlib
import html
import json
import re
import time
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode, urlsplit
import requests

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'sources/citations_cache'
WORK = ROOT / 'tmp/authors'
FIELDS = 'author year title venue doi pmcid preprint_id paper_kind direction include why method_name proposed_paper_id already_seed open_route'.split()
AUTHORS = {
 'Paul F. O\'Reilly': ['A5022427519'],
 'Matthew Stephens': ['A5036504609', 'A5137881999', 'A5152704453', 'A5035661470'],
 'Gao Wang': ['A5100648728', 'A5100648730'],
}
ORCIDS = {'Paul F. O\'Reilly':'0000-0001-7515-0845', 'Matthew Stephens':'0000-0001-5397-9257','Gao Wang':'0000-0001-9336-402X'}
HOSTS = {'api.openalex.org','www.ebi.ac.uk','api.crossref.org','export.arxiv.org','api.biorxiv.org'}

def norm(s):
 return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD',html.unescape(s or '')).lower())
def doi(s):
 return re.sub(r'^https?://(?:dx\.)?doi.org/', '', s or '', flags=re.I).lower().strip()
def is_preprint_doi(value):
 return bool(re.match(r'10\.(?:1101|64898)/[0-9]',doi(value)))

def clean(s):
 return ' '.join(html.unescape(re.sub('<[^>]+>', ' ', s or '')).split())
def slug(s):
 return re.sub(r'[^a-z0-9]+','_',unicodedata.normalize('NFKD',s).lower()).strip('_')

class NoAuth(requests.auth.AuthBase):
 def __call__(self, request): return request
class PublicSession(requests.Session):
 def rebuild_auth(self, prepared_request, response): pass
class Client:
 def __init__(self):
  CACHE.mkdir(parents=True,exist_ok=True)
  self.s=PublicSession();self.s.auth=NoAuth()
  self.s.headers.update({'User-Agent':'AuthorMetadataClient/1.0','Accept':'application/json'})
 def get(self,url,params=None):
  if params: url+='?'+urlencode(sorted(params.items()))
  if urlsplit(url).hostname not in HOSTS: raise ValueError(url)
  p=CACHE/(hashlib.sha256(url.encode()).hexdigest()+'.json')
  if p.exists():
   rec=json.loads(p.read_text())
   if rec['status']==200:return rec['body']
  for attempt in range(3):
   with (CACHE/'metadata_request.lock').open('a+') as f:
    fcntl.flock(f,fcntl.LOCK_EX);f.seek(0);last=float(f.read().strip() or 0)
    time.sleep(max(0,.4-(time.time()-last)))
    f.seek(0);f.truncate();f.write(str(time.time()));f.flush()
   try:
    r=self.s.get(url,timeout=(15,55),allow_redirects=False)
    rec={'url':url,'status':r.status_code,'body':r.text}
   except requests.RequestException as e:rec={'url':url,'status':0,'body':'','error':str(e)}
   if p.exists():rec['previous_responses']=json.loads(p.read_text()).get('previous_responses',[])+[{k:v for k,v in json.loads(p.read_text()).items() if k!='previous_responses'}]
   p.write_text(json.dumps(rec,ensure_ascii=False)+'\n')
   if rec['status']==200:return rec['body']
   if 400<=rec['status']<500 and rec['status']!=429:break
   time.sleep(2*(attempt+1))
  raise RuntimeError(f"Metadata request failed: {rec['status']} {url}")
 def json(self,url,params=None):return json.loads(self.get(url,params))

def abstract(w):
 words={p:k for k,positions in (w.get('abstract_inverted_index') or {}).items() for p in positions}
 return clean(' '.join(words[p] for p in sorted(words)))

def fetch():
 WORK.mkdir(parents=True,exist_ok=True);c=Client();coverage=[];raw=[]
 for author,ids in AUTHORS.items():
  for aid in ids:
   page=1;n=0
   while True:
    data=c.json('https://api.openalex.org/works',{'filter':'author.id:'+aid,'per-page':200,'page':page})
    for w in data['results']:
     raw.append({'author':author,'profile':aid,'service':'openalex','record':w});n+=1
    if not data['results'] or n>=data['meta']['count']:break
    page+=1
   coverage.append({'author':author,'profile':aid,'service':'openalex','retrieved':n,'exhausted':True})
   print(author,aid,n,flush=True)
 queries={"Paul F. O'Reilly":'AUTH:"O\'Reilly PF"', 'Matthew Stephens':'AUTH:"Stephens Matthew"', 'Gao Wang':'AUTH:"Wang Gao"'}
 for author,q in queries.items():
  query=f'({q}) OR AUTHORID:"{ORCIDS[author]}"';cursor='*';n=0
  while True:
   data=c.json('https://www.ebi.ac.uk/europepmc/webservices/rest/search',{'query':query,'format':'json','resultType':'core','pageSize':1000,'cursorMark':cursor})
   rows=data.get('resultList',{}).get('result',[])
   raw.extend({'author':author,'service':'europepmc','record':w} for w in rows);n+=len(rows)
   nex=data.get('nextCursorMark')
   if not rows or not nex or nex==cursor or n>=int(data['hitCount']):break
   cursor=nex
  coverage.append({'author':author,'service':'europepmc','query':query,'hit_count':data['hitCount'],'retrieved':n,'exhausted':n==int(data['hitCount'])})
  print(author,'EuropePMC',n,flush=True)
 (WORK/'raw_records.json').write_text(json.dumps(raw,ensure_ascii=False))
 (WORK/'coverage.json').write_text(json.dumps(coverage,indent=2))
 prepare(raw)

def prepare(raw=None, write=True):
 raw=raw or json.loads((WORK/'raw_records.json').read_text());records=[]
 for rr in raw:
  w=rr['record'];a=rr['author']
  if rr['service']=='openalex':
   people=w.get('authorships',[])
   affiliations=[i['display_name'] for x in people if (x['author'].get('id') or '').split('/')[-1] in AUTHORS[a] for i in x.get('institutions',[])]
   names=[x['author']['display_name'] for x in people]
   source=(w.get('primary_location') or {}).get('source') or {}
   urls=[str(l.get('landing_page_url') or '') for l in w.get('locations',[])]
   ids=w.get('ids') or {}
   r={'authors':[a],'title':clean(w['title']),'doi':doi(w.get('doi')),'pmcid':'','preprint_id':'','year':w.get('publication_year'),'venue':source.get('display_name',''),'abstract':abstract(w),'coauthors':names,'affiliations':affiliations,'sources':[w['id']],'type':w.get('type',''),'links':urls}
   for u in urls:
    if 'pmc/articles/PMC' in u or 'europepmc.org/articles/PMC' in u:
     m=re.search(r'PMC\d+',u)
     if m:r['pmcid']=m[0]
    if 'arxiv.org' in u:
     m=re.search(r'(?:abs|pdf)/([^?#]+)',u)
     if m:r['preprint_id']='arXiv:'+re.sub(r'v\d+$','',m[1].removesuffix('.pdf'))
   if is_preprint_doi(r['doi']):r['preprint_id']=r['doi']
  else:
   people=w.get('authorList',{}).get('author',[]);names=[x.get('fullName','') for x in people]
   target=[]
   for x in people:
    last=norm(x.get('lastName',''));first=norm(x.get('firstName',''))
    if (a.startswith('Paul') and last=='oreilly' and first.startswith('p')) or (a.startswith('Matthew') and last=='stephens' and first.startswith('m')) or (a=='Gao Wang' and last=='wang' and first=='gao'):target.append(x)
   aff=[y.get('affiliation','') for x in target for y in x.get('authorAffiliationDetailsList',{}).get('authorAffiliation',[])]
   r={'authors':[a],'title':clean(w.get('title')),'doi':doi(w.get('doi')),'pmcid':w.get('pmcid',''),'preprint_id':'','year':w.get('pubYear'),'venue':w.get('journalInfo',{}).get('journal',{}).get('title','') or w.get('bookOrReportDetails',{}).get('publisher',''),'abstract':clean(w.get('abstractText','')),'coauthors':names,'affiliations':aff,'sources':['EPMC:'+w.get('source','')+':'+w.get('id','')],'type':'; '.join(w.get('pubTypeList',{}).get('pubType',[])),'links':[]}
   if is_preprint_doi(r['doi']):r['preprint_id']=r['doi']
   r['epmc_record']=w
  r['profile']=rr.get('profile','');records.append(r)
 # Strong identifiers and exact normalized titles first. Different-title versions are reviewed explicitly.
 merged=[];index={}
 for r in records:
  keys=[k for k in [r['doi'],r['pmcid'],norm(r['title'])] if k]
  matches=[index[k] for k in keys if k in index]
  if matches:
   dst=merged[matches[0]]
   for k in ['authors','sources','coauthors','affiliations','links']:dst[k]=list(dict.fromkeys(dst[k]+r[k]))
   for k in ['doi','pmcid','preprint_id','venue','abstract']:
    if not dst[k] or (k=='abstract' and len(r[k])>len(dst[k])):dst[k]=r[k]
   if 'epmc_record' in r:dst['epmc_record']=r['epmc_record']
   pos=matches[0]
  else:pos=len(merged);merged.append(r)
  for k in keys:index[k]=pos
 for r in merged:r['key']=r['doi'] or r['pmcid'] or norm(r['title'])
 if write:
  (WORK/'candidates.json').write_text(json.dumps(merged,ensure_ascii=False,indent=2))
  print('Candidates',len(merged),flush=True)
 return merged

def supplement():
 """Exhaust public ORCID Crossref results and explicit arXiv author searches."""
 c=Client();records=json.loads((WORK/'candidates.json').read_text());coverage=json.loads((WORK/'coverage.json').read_text())
 index={key:r for r in records for key in [r['doi'],r['pmcid'],norm(r['title'])] if key}
 def add(r):
  match=next((index[k] for k in [r['doi'],norm(r['title'])] if k and k in index),None)
  if match:
   for k in ['authors','sources','coauthors','affiliations','links']:match[k]=list(dict.fromkeys(match[k]+r[k]))
   for k in ['doi','pmcid','preprint_id','venue','abstract']:
    if r[k] and (not match[k] or (k=='abstract' and len(r[k])>len(match[k]))):match[k]=r[k]
  else:
   r['key']=r['doi'] or r['preprint_id'] or norm(r['title']);records.append(r);match=r
  for k in [r['doi'],norm(r['title'])]:
   if k:index[k]=match
 def blank(a):return {'authors':[a],'doi':'','pmcid':'','preprint_id':'','venue':'','abstract':'','coauthors':[],'affiliations':[],'links':[],'profile':'','sources':[],'type':''}
 for a,o in ORCIDS.items():
  data=c.json('https://api.crossref.org/works',{'filter':'orcid:https://orcid.org/'+o,'rows':1000})['message']
  assert data['total-results']<=1000, 'Crossref requires further pagination'
  for w in data['items']:
   if not w.get('title') or not w['title'][0]:continue
   r=blank(a);r.update(title=clean(w['title'][0]),doi=doi(w['DOI']),abstract=clean(w.get('abstract','')),venue=clean('; '.join(w.get('container-title',[]))),year=w.get('published',w.get('created',{})).get('date-parts',[[0]])[0][0],type=w['type'],sources=['Crossref:'+w['DOI']],coauthors=[' '.join([x.get('given',''),x.get('family','')]) for x in w.get('author',[])])
   if (is_preprint_doi(r['doi']) or r['doi'].startswith('10.21203/')):r['preprint_id']=r['doi']
   r['relations']=w.get('relation',{});add(r)
  coverage.append({'author':a,'service':'crossref','query':'orcid:'+o,'retrieved':len(data['items']),'total':data['total-results'],'exhausted':True})
 ns={'a':'http://www.w3.org/2005/Atom','o':'http://a9.com/-/spec/opensearch/1.1/','x':'http://arxiv.org/schemas/atom'}
 queries={"Paul F. O'Reilly":'au:"O_Reilly_Paul"','Matthew Stephens':'au:"Stephens_Matthew"','Gao Wang':'au:"Wang_Gao" AND (cat:q-bio.GN OR cat:stat.ME OR cat:stat.CO OR cat:stat.AP OR cat:stat.ML)'}
 for a,q in queries.items():
  body=c.get('https://export.arxiv.org/api/query',{'search_query':q,'start':0,'max_results':1000});tree=ET.fromstring(body);entries=tree.findall('a:entry',ns)
  total=int(tree.findtext('o:totalResults',namespaces=ns));assert len(entries)==total
  for w in entries:
   r=blank(a);ident=re.sub(r'v[0-9]+$','',w.findtext('a:id',namespaces=ns).split('/abs/')[-1])
   r.update(title=clean(w.findtext('a:title',namespaces=ns)),abstract=clean(w.findtext('a:summary',namespaces=ns)),year=int(w.findtext('a:published',namespaces=ns)[:4]),venue='arXiv',preprint_id='arXiv:'+ident,sources=['arXiv:'+ident],type='preprint',coauthors=[e.findtext('a:name',namespaces=ns) for e in w.findall('a:author',ns)],doi=doi(w.findtext('x:doi',namespaces=ns)))
   add(r)
  coverage.append({'author':a,'service':'arxiv','query':q,'retrieved':len(entries),'total':total,'exhausted':True})
 (WORK/'candidates.json').write_text(json.dumps(records,ensure_ascii=False,indent=2));(WORK/'coverage.json').write_text(json.dumps(coverage,indent=2))
 print('Supplemented candidates',len(records))

def enrich():
 """Retrieve core title/abstract/full-text identifiers in bounded DOI batches."""
 c=Client();records=json.loads((WORK/'candidates.json').read_text());dec=json.loads((WORK/'decisions.json').read_text())
 chosen=[r for r in records if r['key'] in dec['decisions'] and r['doi']]
 for start in range(0,len(chosen),35):
  batch=chosen[start:start+35];query=' OR '.join('DOI:"'+r['doi']+'"' for r in batch)
  data=c.json('https://www.ebi.ac.uk/europepmc/webservices/rest/search',{'query':query,'format':'json','resultType':'core','pageSize':1000})
  lookup={}
  for w in data.get('resultList',{}).get('result',[]):
   k=doi(w.get('doi'));old=lookup.get(k,{})
   if k not in lookup or (bool(w.get('pmcid')),bool(w.get('abstractText')))>(bool(old.get('pmcid')),bool(old.get('abstractText'))):lookup[k]=w
  for r in batch:
   w=lookup.get(r['doi'])
   if w:
    r['epmc_record']=w;r['pmcid']=w.get('pmcid') or r['pmcid']
    if w.get('abstractText'):r['abstract']=clean(w['abstractText'])
    r['sources']=list(dict.fromkeys(r['sources']+['EPMC:'+w.get('source','')+':'+w.get('id','')]))
    if not r['venue']:r['venue']=w.get('journalInfo',{}).get('journal',{}).get('title','')
    # Prefer journal's issue year over the online-first date held by OpenAlex.
    if w.get('pubYear'):r['year']=w['pubYear']
  print('Enriched',min(start+35,len(chosen)),'/',len(chosen),flush=True)
 # Seed accession cross-checks recover preprints whose DOI search returns only a PPR record.
 seeds=list(csv.DictReader((ROOT/'seed/seed_list.tsv').open(),delimiter='\t'))
 missing=[s for s in seeds if s['pmcid'] not in ('','NA') and any(not r['pmcid'] and (r['doi']==doi(s['doi']) or norm(r['title'])==norm(s['title'])) for r in records)]
 for start in range(0,len(missing),35):
  q=' OR '.join('PMCID:'+s['pmcid'] for s in missing[start:start+35])
  data=c.json('https://www.ebi.ac.uk/europepmc/webservices/rest/search',{'query':q,'format':'json','resultType':'core','pageSize':1000})
  for w in data.get('resultList',{}).get('result',[]):
   for r in records:
    if (r['doi'] and r['doi']==doi(w.get('doi'))) or norm(r['title'])==norm(w.get('title')):
     r['pmcid']=w.get('pmcid') or r['pmcid'];r['sources'].append('EPMC:'+w.get('source','')+':'+w.get('id',''))
 (WORK/'candidates.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))

def resolve():
 """Follow repository publication links and retain journal-version metadata."""
 c=Client();records=json.loads((WORK/'candidates.json').read_text());review=json.loads((WORK/'decisions.json').read_text());notes=[]
 ax=ET.fromstring((WORK/'arxiv_matthew.xml').read_text());ns={'a':'http://www.w3.org/2005/Atom','x':'http://arxiv.org/schemas/atom'}
 axdoi={norm(e.findtext('a:title',namespaces=ns)):doi(e.findtext('x:doi',namespaces=ns)) for e in ax.findall('a:entry',ns)}
 for n,r in enumerate(records):
  if r['key'] not in review['decisions']:continue
  if is_preprint_doi(r['doi']):r['preprint_id']=r['preprint_id'] or r['doi']
  published=axdoi.get(norm(r['title']), '')
  if is_preprint_doi(r['doi']):
   server='medrxiv' if ('medrxiv' in r['venue'].lower() or re.search(r'\.2[0-9]{7}$',r['doi'])) else 'biorxiv'
   try:
    d=c.json('https://api.biorxiv.org/details/'+server+'/'+r['doi'])
    versions=d.get('collection',[])
    pub=[v.get('published','') for v in versions if v.get('published') not in [None,'','NA']]
    if pub:published=doi(pub[-1])
    notes.append({'key':r['key'],'server':server,'versions':len(versions),'published':published})
   except RuntimeError as e:notes.append({'key':r['key'],'error':str(e)})
  # Non-journal repository DOIs must yield to the explicit journal DOI.
  if published and published!=r['doi'] and not is_preprint_doi(published):
   try:
    w=c.json('https://api.crossref.org/works/'+published)['message']
    r['doi_aliases']=list(dict.fromkeys(r.get('doi_aliases',[])+[r['doi']]))
    r['doi']=published;r['title']=clean(w['title'][0]);r['venue']=clean('; '.join(w.get('container-title',[])))
    r['year']=w.get('published-print',w.get('published',{})).get('date-parts',[[r['year']]])[0][0]
    r['type']=w.get('type','journal-article');r['sources'].append('Crossref:'+published)
    if w.get('abstract'):r['abstract']=clean(w['abstract'])
   except RuntimeError as e:notes.append({'key':r['key'],'error':str(e)})
  # Search has not supplied abstracts for some conference items; Crossref may.
  if not r['abstract'] and r['doi']:
   try:
    w=c.json('https://api.crossref.org/works/'+r['doi'])['message']
    if w.get('abstract'):r['abstract']=clean(w['abstract'])
   except RuntimeError as e:notes.append({'key':r['key'],'error':str(e)})
 (WORK/'candidates.json').write_text(json.dumps(records,ensure_ascii=False,indent=2));(WORK/'publication_links.json').write_text(json.dumps(notes,indent=2))
 print('Repository publication links resolved',len(notes),flush=True)

def crosscheck():
 """Independent initials/affiliation search catches author-profile splitting."""
 c=Client();records=json.loads((WORK/'candidates.json').read_text());coverage=json.loads((WORK/'coverage.json').read_text())
 queries={"Paul F. O'Reilly":'AUTH:"O\'Reilly PF"', 'Matthew Stephens':'AUTH:"Stephens Matthew"', 'Gao Wang':'AUTH:"Wang Gao"'}
 index={k:r for r in records for k in [r['key'],r['doi'],r['pmcid'],norm(r['title'])] if k}
 identity_rejected=[]
 for a,q in queries.items():
  cursor='*';raw=[];n=0
  while True:
   d=c.json('https://www.ebi.ac.uk/europepmc/webservices/rest/search',{'query':q,'format':'json','resultType':'core','pageSize':1000,'cursorMark':cursor})
   results=d.get('resultList',{}).get('result',[]);raw.extend({'author':a,'service':'europepmc','record':w} for w in results);n+=len(results)
   nxt=d.get('nextCursorMark')
   if n>=d['hitCount'] or not results or not nxt or nxt==cursor:break
   cursor=nxt
  coverage.append({'author':a,'service':'europepmc','query':q,'hit_count':d['hitCount'],'retrieved':n,'exhausted':n==d['hitCount']})
  for r in prepare(raw,write=False):
   matches=[index[k] for k in [r['doi'],r['pmcid'],norm(r['title'])] if k and k in index]
   people=r['epmc_record'].get('authorList',{}).get('author',[])
   full=any((a=='Gao Wang' and norm(p.get('lastName',''))=='wang' and norm(p.get('firstName',''))=='gao') or (a=='Matthew Stephens' and norm(p.get('lastName',''))=='stephens' and norm(p.get('firstName',''))=='matthew') or (a.startswith('Paul') and norm(p.get('lastName',''))=='oreilly' and norm(p.get('firstName','')).startswith('paul')) for p in people)
   if matches:
    dst=matches[0]
    for k in ['authors','sources','coauthors','affiliations','links']:dst[k]=list(dict.fromkeys(dst[k]+r[k]))
    if not dst['pmcid']:dst['pmcid']=r['pmcid']
    if len(r['abstract'])>len(dst['abstract']):dst['abstract']=r['abstract']
   elif full:
    records.append(r)
    for k in [r['key'],r['doi'],r['pmcid'],norm(r['title'])]:
     if k:index[k]=r
   else:identity_rejected.append({'author':a,'title':r['title'],'key':r['key'],'reason':'Initials-only namesake without established target identity.'})
  print(a,'initials/affiliation crosscheck',n,flush=True)
 (WORK/'candidates.json').write_text(json.dumps(records,ensure_ascii=False,indent=2));(WORK/'coverage.json').write_text(json.dumps(coverage,indent=2));(WORK/'crosscheck_identity_rejected.json').write_text(json.dumps(identity_rejected,ensure_ascii=False,indent=2))
 print('Crosschecked candidates',len(records),flush=True)

def build():
 records=json.loads((WORK/'candidates.json').read_text());review=json.loads((WORK/'decisions.json').read_text())
 seeds=list(csv.DictReader((ROOT/'seed/seed_list.tsv').open(),delimiter='\t'))
 decisions=review['decisions'];excluded=set(review.get('excluded',{}));aliases=review.get('versions',{})
 bykey={r['key']:r for r in records}
 for child,parent in aliases.items():
  c,p=bykey[child],bykey[parent]
  for k in ['authors','sources']:p[k]=list(dict.fromkeys(p[k]+c[k]))
  pre=c['preprint_id'] or (c['doi'] if (is_preprint_doi(c['doi']) or c['doi'].startswith('10.21203/')) else '')
  if pre:p['preprint_id']='; '.join(dict.fromkeys(z.strip() for value in [p['preprint_id'],pre] for z in value.split(';') if z.strip()))
 rows=[]
 for r in records:
  if r['key'] in excluded or r['key'] in aliases:continue
  d=decisions[r['key']]
  r.update(d.get('metadata_override',{}))
  if not r['preprint_id'] and (is_preprint_doi(r['doi']) or r['doi'].startswith('10.21203/')):r['preprint_id']=r['doi']
  r['preprint_id']='; '.join(z.strip() for z in r['preprint_id'].split(';') if z.strip() and not re.match(r'10\.1101/(?:gr|gad|pdb|csh)',z.strip()))
  co=set(norm(n) for n in r['coauthors'])
  inferred=set(r['authors'])
  if 'matthewstephens' in co:inferred.add('Matthew Stephens')
  if 'gaowang' in co:inferred.add('Gao Wang')
  if 'paulforeilly' in co:inferred.add("Paul F. O'Reilly")
  authors=[a for a in AUTHORS if a in inferred and a not in d.get('remove_authors',[])]
  if not authors:continue
  kind,direction,name=d['paper_kind'],d['direction'],d.get('method_name','NA')
  inc=kind=='statistical_method' and ("Paul F. O'Reilly" in authors or direction in {'susie','prs'})
  inc=inc or (d.get('only_method_description',False) and "Paul F. O'Reilly" in authors)
  seed=next((s for s in seeds if (r['doi'] and r['doi']==doi(s['doi'])) or (doi(s['doi']) in r.get('doi_aliases',[])) or (r['pmcid'] and r['pmcid']==s['pmcid']) or norm(r['title'])==norm(s['title'])),None)
  # DOI/title of a journal version can match a seeded preprint.
  if not seed:
   childkeys=[k for k,v in aliases.items() if v==r['key']]
   seed=next((s for s in seeds if any(doi(s['doi'])==bykey[k]['doi'] or norm(s['title'])==norm(bykey[k]['title']) for k in childkeys)),None)
  route='NA'
  if inc:
   route='pmc' if r['pmcid'] else 'arxiv' if 'arXiv:' in r['preprint_id'] else 'biorxiv' if any(z.strip().startswith('10.1101/') for z in r['preprint_id'].split(';')) else 'biorxiv' if any(z.strip().startswith('10.64898/') for z in r['preprint_id'].split(';')) else 'europepmc' if r.get('epmc_record',{}).get('inEPMC')=='Y' else 'none_found'
  proposed=seed['paper_id'] if seed else slug(name) if name!='NA' else slug(r['title'])
  rows.append(dict(zip(FIELDS,['; '.join(authors),str(r['year']),r['title'],r['venue'] or 'NA',r['doi'] or 'NA',r['pmcid'] or 'NA',r['preprint_id'] or 'NA',kind,direction,'yes' if inc else 'no',d['why'],name,proposed,'yes' if seed else 'no',route])))
 rows.sort(key=lambda x:(x['author'],x['year'],x['title'].lower()))
 with (ROOT/'tables/author_papers.tsv').open('w',newline='') as f:
  writer=csv.DictWriter(f,FIELDS,delimiter='\t',lineterminator='\n');writer.writeheader();writer.writerows(rows)
 check()

def check():
 rows=list(csv.DictReader((ROOT/'tables/author_papers.tsv').open(),delimiter='\t'))
 assert list(rows[0])==FIELDS
 kinds={'statistical_method','software_or_version','tutorial_or_review','application','data_resource','other'}
 keys=set()
 for r in rows:
  assert set(r['author'].split('; '))<=set(AUTHORS) and r['author']
  assert r['title'].strip() and r['year'].isdigit()
  assert r['paper_kind'] in kinds and r['direction'] in {'prs','susie','other'}
  assert len(r['why'].split())<=20,(r['title'],r['why'])
  assert r['include'] in {'yes','no'} and r['already_seed'] in {'yes','no'}
  assert r['open_route'] in ({'pmc','europepmc','arxiv','biorxiv','none_found'} if r['include']=='yes' else {'NA'})
  assert not re.search(r'10\.1101/(?:gr|gad|pdb|csh)',r['preprint_id'])
  assert r['proposed_paper_id'] and re.fullmatch('[a-z0-9_]+',r['proposed_paper_id'])
  key=r['doi'] if r['doi']!='NA' else norm(r['title']);assert key not in keys,key;keys.add(key)
 print('Distinct works:',len(rows))
 for a in AUTHORS:
  selected=[r for r in rows if a in r['author'].split('; ')];yes=[r for r in selected if r['include']=='yes'];new=[r for r in yes if r['already_seed']=='no']
  print(a, json.dumps({'works':len(selected),'paper_kind':dict(Counter(r['paper_kind'] for r in selected)),'include':dict(Counter(r['include'] for r in selected)),'already_seed_included':sum(r['already_seed']=='yes' for r in yes),'open_route':dict(Counter(r['open_route'] for r in selected)),'new_open_route':dict(Counter(r['open_route'] for r in new))},sort_keys=True))
 print('CHECK PASSED')

if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);g=ap.add_mutually_exclusive_group(required=True)
 for arg in ['fetch','prepare','supplement','enrich','resolve','crosscheck','build','check']:g.add_argument('--'+arg,action='store_true')
 args=ap.parse_args()
 if args.fetch:
  fetch();supplement()
 elif args.prepare:prepare()
 elif args.supplement:supplement()
 elif args.enrich:enrich()
 elif args.resolve:resolve()
 elif args.crosscheck:crosscheck()
 elif args.build:build()
 else:check()
