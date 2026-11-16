#!/usr/bin/env python3
"""Resolve STATO's named sources and build a cached, directed citation lineage.

Run from any directory with Python 3 and requests:
  python scripts/citation_paths.py --tables-dir tables --cache-dir sources/citations_cache --max-depth 3
  python scripts/citation_paths.py --offline  # fails on a cache miss; writes identical TSVs

Only the four citation TSVs, cache responses, and tmp/refresh diagnostics are written.
The verified citation_contexts.tsv supplies supplementary citation evidence when present;
rerun this entry point after citation_contexts.py to integrate newly resolved markers.
All HTTP traffic is limited globally to less than 3 requests/second; publisher sites
are never requested. Cached HTTP failures are retained too. Remove nothing to rerun.
"""
import argparse
import csv
import fcntl
import hashlib
import html
import json
import re
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit
import requests

ROOT = Path(__file__).resolve().parent.parent
NA = 'NA'
EPMC = 'https://www.ebi.ac.uk/europepmc/webservices/rest'
CR = 'https://api.crossref.org'
OA = 'https://api.openalex.org'
OCI = 'https://api.opencitations.net/index/v2'
ALLOWED = {'www.ebi.ac.uk', 'api.crossref.org', 'api.openalex.org', 'opencitations.net', 'api.opencitations.net'}

class NoAuth(requests.auth.AuthBase):
    def __call__(self, request):
        return request

class PublicSession(requests.Session):
    def rebuild_auth(self, prepared_request, response):
        pass  # public metadata only; never consult personal netrc on redirects

def pace_request(cache):
    """Keep public request starts below 3/second across refresh processes."""
    with (Path(cache) / 'metadata_request.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        lock.seek(0)
        prior = lock.read().strip()
        last = float(prior) if prior else 0.0
        time.sleep(max(0.0, .36 - (time.time() - last)))
        lock.seek(0)
        lock.truncate()
        lock.write(str(time.time()))
        lock.flush()


class Client:
    def __init__(self, cache, offline=False, retry_failed=False):
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.offline = offline
        self.retry_failed = retry_failed
        self.stats = Counter()
        self.failures = Counter()
        self.session = PublicSession()
        self.session.auth = NoAuth()
        self.session.headers.update({'User-Agent': 'CitationMetadataClient/1.0', 'Accept': 'application/json'})

    def get(self, url, params=None):
        if params:
            url += ('&' if '?' in url else '?') + urlencode(sorted(params.items()))
        host = urlsplit(url).hostname
        if host not in ALLOWED:
            raise ValueError('Non-metadata host refused: ' + str(host))
        key = hashlib.sha256(url.encode()).hexdigest()
        path = self.cache / (key + '.json')
        prior = json.loads(path.read_text()) if path.exists() else None
        if prior is not None and (prior.get('status') == 200 or not self.retry_failed or self.offline):
            rec = prior
            self.stats['cache_hits'] += 1
        else:
            if self.offline:
                raise RuntimeError('Offline cache miss: ' + url)
            pace_request(self.cache)
            try:
                r = self.session.get(url, timeout=(10, 35), allow_redirects=False)
                rec = {'url': url, 'status': r.status_code, 'body': r.text}
            except requests.RequestException as e:
                rec = {'url': url, 'status': 0, 'body': '', 'error': type(e).__name__ + ': ' + str(e)}
            if prior is not None:
                rec['previous_responses'] = prior.get('previous_responses', []) + [{k: v for k, v in prior.items() if k != 'previous_responses'}]
            path.write_text(json.dumps(rec, ensure_ascii=False, sort_keys=True) + '\n')
            self.stats[host] += 1
        if rec['status'] != 200:
            self.failures[f"{host}: HTTP {rec['status']}"] += 1
            return None
        try:
            return json.loads(rec['body'])
        except ValueError:
            self.failures[host + ': invalid JSON'] += 1
            return None


def probe(client):
    queries = [('epmc', EPMC+'/search', {'query': 'DOI:10.1534/g3.112.003665', 'format':'json','resultType':'core','pageSize':1}),
               ('crossref', CR+'/works/10.1534/g3.112.003665', None),
               ('openalex', OA+'/works/https://doi.org/10.1534/g3.112.003665', None),
               ('opencitations', OCI+'/references/doi:10.1534/g3.112.003665', None),
               ('epmc_refs', EPMC+'/MED/11290733/references', {'format':'json','pageSize':1000,'page':1}),
               ('epmc_cites', EPMC+'/MED/11290733/citations', {'format':'json','pageSize':1000,'page':1})]
    for name,url,params in queries:
        obj=client.get(url,params)
        if name.startswith('epmc'):
            result = obj or {}
            print(name, 'keys',list(result), 'counts', {k:v for k,v in result.items() if k in ['hitCount','citationCount','referenceCount']})
            for k in ['resultList','referenceList','citationList']:
                if k in result:
                    items=next(iter(result[k].values()),[])
                    print('item schema',list(items[0]) if items else [], 'n',len(items))
        else:
            print(name, 'reachable',obj is not None,'keys',list(obj)[:15] if isinstance(obj,dict) else 'list')
    print('failures',dict(client.failures))


def present(value):
    return str(value or '').strip() not in ('', NA, 'None')

def norm(text):
    return re.sub('[^a-z0-9]', '', unicodedata.normalize('NFKD', html.unescape(str(text))).encode('ascii','ignore').decode().lower())

def doi(text):
    text = html.unescape(str(text or ''))
    m = re.search(r'10\.\d{4,9}/[^\s<>"\\&#?]+', text, re.I)
    return m.group().rstrip('.,;:)').lower() if m else ''

def pmcid(text):
    m = re.search(r'PMC\d+', str(text or ''), re.I)
    return m.group().upper() if m else ''

def read_table(path):
    with Path(path).open(newline='') as f:
        return list(csv.DictReader(f, delimiter='\t'))

def write_table(path, columns, rows):
    with Path(path).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=columns, delimiter='\t', lineterminator='\n')
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k) if present(row.get(k)) else NA for k in columns})

def oa_meta(d):
    ids=d.get('ids') or {}
    author=((d.get('authorships') or [{}])[0].get('author') or {}).get('display_name','')
    return {'oa':d.get('id','').rsplit('/',1)[-1], 'doi':doi(d.get('doi')), 'pmid':str(ids.get('pmid','')).rstrip('/').rsplit('/',1)[-1],
            'pmcid':pmcid(ids.get('pmcid')) or ('PMC'+str(ids['pmcid']).rstrip('/').rsplit('/',1)[-1] if ids.get('pmcid') else ''),
            'title':d.get('title',''), 'first_author':author, 'year':str(d.get('publication_year') or ''),
            'venue':(((d.get('primary_location') or {}).get('source') or {}).get('display_name') or ''),
            'n_citations':d.get('cited_by_count'), 'oa_refs':d.get('referenced_works',[])}

def ep_meta(d):
    return {'doi':doi(d.get('doi')), 'pmid':d.get('pmid') or (d.get('id') if d.get('source')=='MED' else ''),
            'pmcid':pmcid(d.get('pmcid')) or pmcid(d.get('id')), 'title':d.get('title',''),
            'first_author':(d.get('authorString') or '').split(',')[0], 'year':str(d.get('pubYear') or ''),
            'venue':((d.get('journalInfo') or {}).get('journal') or {}).get('title') or d.get('journalAbbreviation',''),
            'n_citations':d.get('citedByCount')}

def cr_meta(d):
    au=(d.get('author') or [{}])[0]
    year=''
    for key in ['published-print','published-online','published','issued']:
        parts=(d.get(key) or {}).get('date-parts')
        if parts and parts[0]:
            year=str(parts[0][0]); break
    return {'doi':doi(d.get('DOI')), 'title':(d.get('title') or [''])[0],
            'first_author':au.get('family') or au.get('name',''), 'year':year,
            'venue':(d.get('container-title') or [''])[0], 'n_citations':d.get('is-referenced-by-count')}

class Registry:
    """Unify identifiers, including explicitly seeded preprint/journal aliases."""
    def __init__(self):
        self.records={}
        self.alias={}
        self.parent={}
        self.serial=0
    def root(self,k):
        while k in self.parent:
            k=self.parent[k]
        return k
    def aliases(self,m):
        return [f'{k}:{str(m[k]).lower()}' for k in ['doi','pmid','pmcid','oa'] if present(m.get(k))]
    def add(self,m,kind='intermediate',forced=None):
        aliases=self.aliases(m)
        keys={self.root(self.alias[a]) for a in aliases if a in self.alias}
        if forced in self.records:
            keys.add(forced)
        if keys:
            rank={'method_paper':0,'stato_source':1,'intermediate':2}
            k=sorted(keys,key=lambda k:(rank[self.records[k]['kind']],k))[0]
            for other in sorted(keys-{k}):
                self.parent[other]=k
                old=self.records.pop(other)
                for field,value in old.items():
                    if not present(self.records[k].get(field)) and present(value):
                        self.records[k][field]=value
                self.records[k].setdefault('oa_refs',set()).update(old.get('oa_refs',set()))
                self.records[k].setdefault('_titles',set()).update(old.get('_titles',set()))
        else:
            self.serial+=1
            k=forced or 'record_'+str(self.serial)
            self.records[k]={'kind':kind,'oa_refs':set()}
        rec=self.records[k]
        rec['_span_version']=rec.get('_span_version',0)+1
        if present(m.get('title')):
            rec.setdefault('_titles',set()).add(m['title'])
        if kind=='method_paper' or (kind=='stato_source' and rec['kind']=='intermediate'):
            rec['kind']=kind
        for field,value in m.items():
            if field=='oa_refs':
                rec.setdefault(field,set()).update(x.rsplit('/',1)[-1] for x in value)
            elif field=='n_citations' and present(value):
                rec[field]=max(int(value),int(rec.get(field) or 0))
            elif present(value):
                # Seed identity fields remain the input's selected version.
                if rec['kind']!='method_paper' or field not in ['title','first_author','year','venue','doi','pmcid'] or not present(rec.get(field)):
                    rec[field]=value
        for a in aliases:
            self.alias[a]=k
        return k
    def lookup(self,field,value):
        k=self.alias.get(field+':'+str(value).lower())
        return self.root(k) if k else None

class Builder:
    def __init__(self,args):
        self.args=args
        self.tables=Path(args.tables_dir).resolve()
        self.project=self.tables.parent
        self.sources=self.project/'sources'
        self.client=Client(args.cache_dir,args.offline)
        self.reg=Registry()
        self.edges=defaultdict(set)
        self.spans={}
        self.loaded_refs=set()
        self.oa_loaded=set()
        self.oa_missing=set()
        self.stored={}
        self.span_cache={}
        self.span_patterns={}
        self.span_seed_dois=None
        self.bibliography_search={}
        self.line_cache={}
        self.local_refs=[]
        self.used=set()
        self.notes=[]
        self.seed=read_table(self.project/'seed/seed_list.tsv')
        self.mapped_node_ids=({s['paper_id'] for s in self.seed}
            | {r['method_id'] for r in read_table(self.tables/'methods.tsv')}
            | {r['method_id'] for r in read_table(self.tables/'map_layout.tsv')}
            | {r['node_id'] for r in read_table(self.tables/'citation_nodes.tsv')})
        # Retain every existing public node ID in an append-only identity ledger.
        # Later refreshes add their incoming IDs while retaining earlier identity
        # metadata; cache replay therefore never retires an established node.
        ledger=Path(args.cache_dir)/'lineage_identity_baseline.json'
        previous=json.loads(ledger.read_text()) if ledger.exists() else []
        known={r['node_id'] for r in previous}
        current=read_table(self.tables/'citation_nodes.tsv') if (self.tables/'citation_nodes.tsv').exists() else []
        additions=[r for r in current if r['node_id'] not in known]
        if additions or not ledger.exists():
            previous.extend(additions)
            ledger.write_text(json.dumps(previous,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
        self.previous_nodes=previous
        self.previous_keys=set()

    def edge(self,a,b,service,span=None):
        if a and b and self.reg.root(a)!=self.reg.root(b):
            self.edges[(a,b)].add(service)
            if span:
                self.spans[(a,b)]=span

    def ep_search(self,query,size=1000):
        data=self.client.get(EPMC+'/search',{'query':query,'format':'json','resultType':'core','pageSize':size})
        if data is not None:
            self.used.add('Europe PMC')
        return (data or {}).get('resultList',{}).get('result',[])

    def oa_batch(self,field,values):
        values=sorted({str(x) for x in values if present(x)})
        result=[]
        for start in range(0,len(values),50):
            batch=values[start:start+50]
            data=self.client.get(OA+'/works',{'filter':field+':'+ '|'.join(batch), 'per-page':50})
            if data is None:
                self.notes.append('OpenAlex batch unavailable: '+field)
                continue
            self.used.add('OpenAlex')
            for item in data.get('results',[]):
                key=self.reg.add(oa_meta(item))
                self.oa_loaded.add(item['id'].rsplit('/',1)[-1])
                result.append(key)
        return result

    def enrich_oa(self,keys):
        keys={self.reg.root(k) for k in keys}
        for field in ['doi','pmid']:
            keys={self.reg.root(k) for k in keys}
            values=[self.reg.records[k].get(field) for k in sorted(keys) if not self.reg.records[k].get('oa')]
            self.oa_batch(field,values)
        ids={self.reg.records[self.reg.root(k)].get('oa') for k in keys}
        ids.discard(None)
        self.oa_batch('openalex_id',ids-self.oa_loaded-self.oa_missing)

    def ep_list(self,key,relation):
        rec=self.reg.records[self.reg.root(key)]
        if rec.get('pmid'):
            source,pid='MED',rec['pmid']
        elif rec.get('pmcid'):
            source,pid='PMC',rec['pmcid']
        else:
            return []
        out=[]
        page=1
        while True:
            data=self.client.get(f'{EPMC}/{source}/{pid}/{relation}',{'format':'json','pageSize':1000,'page':page})
            if data is None:
                break
            self.used.add('Europe PMC')
            listkey='referenceList' if relation=='references' else 'citationList'
            itemkey='reference' if relation=='references' else 'citation'
            batch=(data.get(listkey) or {}).get(itemkey,[])
            out.extend(batch)
            if not batch or page*1000>=int(data.get('hitCount',0)):
                break
            page+=1
        return out

    def source_segments(self,text):
        if not present(text):
            return [NA]
        parts=re.split(r'\s*;;\s*|\s+and\s+from:?\s*|\s+and:\s*|\s+but also\s+|\s+and\s+(?=https?://)|\s+and\s+from the\s+',text,flags=re.I)
        out=[]
        for part in parts:
            # An adjacent author/year citation or unrelated web URL begins a new source.
            part=re.sub(r'\s+(?=(?:Geman,\s*S\.|Hastings,\s*W\.))','\x00',part)
            part=re.sub(r'\s+(?=https?://(?:www\.scholarpedia|stats\.stackexchange))','\x00',part)
            part=re.sub(r'\s+(?=https?://jvanderw)','\x00',part)
            out.extend(p.strip(' ;') for p in part.split('\x00') if p.strip(' ;') and p.strip(' ;').lower()!='from')
        return out or [NA]

    def resolve_sources(self,terms):
        rows=[]
        memo={}
        for term in terms:
            for source in self.source_segments(term['definition_source']):
                row={'stato_id':term['stato_id'],'label':term['label'],'source_text':source}
                low=source.lower()
                book=bool(re.search(r'dictionary|applications of linear models in animal breeding|multiple testing procedures with applications',low))
                d=doi(source); pc=pmcid(source)
                pm=re.search(r'PMID\s*:?\s*(\d+)',source,re.I)
                pm=pm.group(1) if pm else ''
                if book:
                    row['source_kind']='book'
                elif d or pc or pm:
                    row['source_kind']='paper'
                elif re.search(r'https?://|ftp://|wikipedia',low):
                    row['source_kind']='web'
                else:
                    row['source_kind']='none'
                if row['source_kind']=='paper':
                    identity=(d,pc,pm)
                    if identity not in memo:
                        meta={'doi':d,'pmcid':pc,'pmid':pm}
                        by=[]
                        if d:
                            cr=self.client.get(CR+'/works/'+quote(d,safe=''))
                            if cr and cr.get('message'):
                                meta.update(cr_meta(cr['message'])); by.append('Crossref:DOI'); self.used.add('Crossref')
                        query='DOI:'+d if d else ('EXT_ID:'+pm+' AND SRC:MED' if pm else 'EXT_ID:'+pc)
                        found=self.ep_search(query,5)
                        for item in found:
                            m=ep_meta(item)
                            if (d and m['doi']==d) or (pc and m['pmcid']==pc) or (pm and m['pmid']==pm):
                                meta.update({k:v for k,v in m.items() if present(v)}); by.append('Europe PMC:identifier'); break
                        if not meta.get('doi') and meta.get('pmid'):
                            # The original STATO PMID remains the identity if no DOI is indexed.
                            pass
                        key=self.reg.add(meta,'stato_source')
                        memo[identity]=(key,'; '.join(by) or 'unresolved:identifier_named_by_STATO')
                    row['_key'],row['resolved_by']=memo[identity]
                rows.append(row)
        return rows

    def load_seeds(self):
        for s in self.seed:
            m={k:s.get(k,'') for k in ['title','first_author','year','venue','doi','pmcid']}
            m={k:v for k,v in m.items() if present(v)}
            if m.get('doi'):
                m['doi']=doi(m['doi'])
            key=self.reg.add(m,'method_paper',s['paper_id'])
            pre=doi(s.get('preprint_id'))
            if pre:
                pre=re.sub(r'v\d+$','',pre)
                self.reg.alias['doi:'+pre]=key
        seed_ids={row['paper_id'] for row in self.seed}
        for old in self.previous_nodes:
            # Seed records have declared input metadata and cached enrichment.
            # Feeding a previous output's extra PMID back into them changes HTTP
            # batch boundaries on the first replay after adding a seed paper.
            # The ledger preserves identity, rather than becoming a second seed.
            if old['node_id'] in seed_ids:
                key=self.reg.root(old['node_id'])
            else:
                meta={k:v for k,v in old.items() if k not in {'node_id','kind'} and present(v)}
                if meta.get('doi'):meta['doi']=doi(meta['doi'])
                key=self.reg.add(meta,old['kind'],old['node_id'])
            self.reg.records[key]['_public_id']=old['node_id']
            self.previous_keys.add(key)
        self.oa_batch('doi',[s['doi'] for s in self.seed if present(s['doi'])]+[re.sub(r'v\d+$','',doi(s['preprint_id'])) for s in self.seed if doi(s.get('preprint_id'))])
        for s in self.seed:
            if not self.reg.records[self.reg.root(s['paper_id'])].get('oa'):
                query=self.client.get(OA+'/works',{'search':s['title'],'per-page':5})
                self.used.add('OpenAlex') if query is not None else None
                for item in (query or {}).get('results',[]):
                    if SequenceMatcher(None,norm(s['title']),norm(item.get('title',''))).ratio()>=.9:
                        self.reg.alias['oa:'+item['id'].rsplit('/',1)[-1].lower()]=s['paper_id']
                        self.reg.add(oa_meta(item)); break

    def load_stored(self):
        for s in self.seed:
            pid=s['paper_id']; path=self.sources/(pid+'.txt')
            if not path.exists():
                continue
            text=path.read_text()
            # Keep exact original line slices, including any internal whitespace.
            headings=list(re.finditer(r'(?im)^#{1,6}\s*(?:references|bibliography|literature cited)\s*$',text))
            start=headings[-1].end() if headings else int(len(text)*.55)
            section=text[start:]
            next_heading=re.search(r'(?m)^##\s+',section)
            if next_heading:
                section=section[:next_heading.start()]
            entries=[line for line in section.splitlines() if len(line.strip())>25 and not line.startswith('#')]
            self.stored[pid]=(text,entries)
            xml=self.sources/(pid+'.raw.xml')
            if not xml.exists():
                continue
            try:
                root=ET.parse(xml).getroot()
            except ET.ParseError:
                self.notes.append('Stored XML parse failure: '+pid); continue
            for element in root.iter():
                if element.tag.rsplit('}',1)[-1]!='ref':
                    continue
                m={}
                reftext=''.join(element.itertext())
                for child in element.iter():
                    tag=child.tag.rsplit('}',1)[-1]
                    value=''.join(child.itertext())
                    if tag=='article-title': m['title']=value
                    if tag=='year': m['year']=value
                    if tag=='surname' and not m.get('first_author'): m['first_author']=value
                    if tag=='pub-id':
                        typ=child.get('pub-id-type')
                        if typ in ['doi','pmid','pmcid']: m[typ]=value
                    if tag=='ext-link' and doi(child.get('{http://www.w3.org/1999/xlink}href','')):
                        m['doi']=doi(child.get('{http://www.w3.org/1999/xlink}href',''))
                if m.get('doi'): m['doi']=doi(m['doi'])
                if not m.get('doi'):
                    found=doi(reftext)
                    if found: m['doi']=found
                if not m.get('pmcid') and pmcid(reftext): m['pmcid']=pmcid(reftext)
                self.local_refs.append((pid,m,reftext))

    def span(self,pid,key):
        if pid not in self.stored:
            return None
        cachekey=(pid,self.reg.root(key))
        if cachekey in self.span_cache:
            return self.span_cache[cachekey]
        target=self.reg.root(key)
        if self.span_seed_dois is None:
            self.span_seed_dois=defaultdict(set)
            for seed in self.seed:
                if doi(seed.get('preprint_id')):
                    self.span_seed_dois[self.reg.root(seed['paper_id'])].add(re.sub(r'v\d+$','',doi(seed['preprint_id'])))
        rec=self.reg.records[target]
        version=rec.get('_span_version',0)
        if target not in self.span_patterns or self.span_patterns[target][0] != version:
            ds=({rec['doi']} if present(rec.get('doi')) else set()) | self.span_seed_dois[target]
            titles={norm(t) for t in rec.get('_titles',set())|{rec.get('title','')} if len(norm(t))>=25}
            self.span_patterns[target]=(version,ds,titles)
        _,ds,titles=self.span_patterns[target]
        if pid not in self.bibliography_search:
            entries=self.stored[pid][1]
            self.bibliography_search[pid]=('\0'.join(line.lower() for line in entries),
                                          '\0'.join(norm(line) for line in entries))
        low_all,norm_all=self.bibliography_search[pid]
        # Negative matches use compiled string searches over the same entries;
        # a delimiter prevents matches spanning adjacent bibliography entries.
        if not (any(d in low_all for d in ds) or any(t in norm_all for t in titles)):
            self.span_cache[cachekey]=None
            return None
        for line in self.stored[pid][1]:
            if line not in self.line_cache:
                self.line_cache[line]=(line.lower(),norm(line))
            low,normalized=self.line_cache[line]
            if any(d in low for d in ds) or any(len(title)>=25 and title in normalized for title in titles):
                self.span_cache[cachekey]=line
                return line
        self.span_cache[cachekey]=None
        return None

    def canonical_edges(self):
        edges=defaultdict(set); spans={}
        for (a,b),services in self.edges.items():
            a,b=self.reg.root(a),self.reg.root(b)
            if a!=b:
                edges[(a,b)].update(services)
                if (a,b) in self.spans: spans[(a,b)]=self.spans[(a,b)]
        self.edges=edges
        self.spans.update(spans)

    def add_oa_edges(self,keys):
        for key in sorted({self.reg.root(k) for k in keys}):
            rec=self.reg.records[key]
            for rid in sorted(rec.get('oa_refs',set())):
                target=self.reg.lookup('oa',rid)
                if not target:
                    target=self.reg.add({'oa':rid})
                self.edge(key,target,'OpenAlex')

    def references(self,keys,epmc=False,crossref_all=False):
        keys=sorted({self.reg.root(k) for k in keys})
        self.enrich_oa(keys)
        self.add_oa_edges(keys)
        if epmc:
            for key in keys:
                if key in self.loaded_refs: continue
                self.loaded_refs.add(key)
                for ref in self.ep_list(key,'references'):
                    m=ep_meta(ref)
                    if not any(present(m.get(k)) for k in ['doi','pmid','pmcid']):
                        continue
                    target=self.reg.add(m)
                    self.edge(key,target,'Europe PMC')
        # Crossref fills a reference list only when OpenAlex has no indexed list.
        for key in keys:
            rec=self.reg.records[self.reg.root(key)]
            if (rec.get('oa_refs') and not crossref_all) or not rec.get('doi'): continue
            data=self.client.get(CR+'/works/'+quote(rec['doi'],safe=''))
            if not data: continue
            self.used.add('Crossref')
            for ref in data.get('message',{}).get('reference',[]):
                d=doi(ref.get('DOI'))
                if d:
                    self.edge(key,self.reg.add({'doi':d,'title':ref.get('article-title',''),'year':str(ref.get('year',''))}), 'Crossref')

    def source_citers(self,keys,citing_keys):
        # Server-side intersection is the reverse half of the depth-three search:
        # retain source citers that occur in a method's or first-layer paper's
        # bibliography. This avoids downloading tens of thousands of irrelevant
        # citing papers. OpenAlex's cited_by filter was checked against the exact
        # referenced_works set. Basic pagination works without a private API key.
        origins=sorted({self.reg.records[self.reg.root(k)].get('oa') for k in citing_keys
                        if self.reg.records[self.reg.root(k)].get('oa')})
        for key in sorted({self.reg.root(k) for k in keys}):
            rec=self.reg.records[key]
            if rec.get('oa'):
                for start in range(0,len(origins),50):
                    batch=origins[start:start+50]
                    page=1
                    while True:
                        data=self.client.get(OA+'/works',{'filter':'cites:'+rec['oa']+',cited_by:'+'|'.join(batch),
                            'per-page':200,'page':page,
                            'select':'id,doi,title,publication_year,ids,authorships,primary_location,cited_by_count'})
                        if data is None: break
                        self.used.add('OpenAlex')
                        for item in data.get('results',[]):
                            citing=self.reg.add(oa_meta(item))
                            self.edge(citing,key,'OpenAlex')
                        if page*200>=int(data.get('meta',{}).get('count',0)) or not data.get('results'): break
                        page+=1
            if rec.get('doi'):
                data=self.client.get(OCI+'/citations/doi:'+quote(rec['doi'],safe=''))
                if isinstance(data,list):
                    self.used.add('OpenCitations')
                    for item in data:
                        identifier=item.get('citing','')
                        m={'doi':doi(identifier),
                           'oa':(re.search(r'openalex:(W\d+)',identifier) or ['', ''])[1],
                           'pmid':(re.search(r'pmid:(\d+)',identifier) or ['', ''])[1]}
                        existing=next((self.reg.lookup(f,m[f]) for f in ['oa','doi','pmid'] if m[f] and self.reg.lookup(f,m[f])),None)
                        if existing:
                            self.edge(self.reg.add(m),key,'OpenCitations')
            # Independent biomedical citation coverage includes PMC-only records.
            for item in self.ep_list(key,'citations'):
                m=ep_meta(item)
                if any(present(m.get(k)) for k in ['pmid','pmcid','doi']):
                    citing=self.reg.add(m)
                    self.edge(citing,key,'Europe PMC')

    def match_local(self):
        self.span_cache.clear()
        self.span_patterns.clear()
        self.span_seed_dois=None
        titles=defaultdict(list)
        for k,r in self.reg.records.items():
            t=norm(r.get('title',''))
            if len(t)>=25:
                titles[t].append(k)
        for pid,m,raw in self.local_refs:
            target=None
            for field in ['doi','pmid','pmcid']:
                if present(m.get(field)):
                    target=self.reg.lookup(field,m[field])
                    if target: break
            if not target:
                t=norm(m.get('title',''))
                if t in titles:
                    candidates=titles[t]
                    target=sorted(candidates,key=lambda k:(self.reg.records[k]['kind']!='method_paper',k))[0]
            if not target:
                raw_norm=norm(raw)
                matches=[(len(t),k) for t,ks in titles.items() if t in raw_norm for k in ks]
                if matches: target=sorted(matches,reverse=True)[0][1]
            if target:
                target=self.reg.root(target)
                # XML supplies identifiers; the copied span always comes from the .txt.
                self.reg.add(dict(m,**({'oa':self.reg.records[target]['oa']} if self.reg.records[target].get('oa') else {}))) if self.reg.aliases(m) else None
                self.edge(pid,target,'stored_text',self.span(pid,target))
        for pid in self.stored:
            for target in sorted(self.reg.records):
                if target==pid: continue
                span=self.span(pid,target)
                if span: self.edge(pid,target,'stored_text',span)
        self.canonical_edges()
        self.match_contexts()

    def match_contexts(self):
        """Use exact, retained citation sentences as additional direct evidence.

        citation_contexts.py owns reference-marker resolution, including supplements.
        Reuse its verified table without another service request or another parser.
        Bibliography spans still come exclusively from the retained main text.
        """
        path=self.tables/'citation_contexts.tsv'
        if not path.exists():
            return
        if not hasattr(self,'context_evidence'):
            self.context_evidence=read_table(path)
            self.context_sources={}
        titles=defaultdict(list)
        for key,rec in self.reg.records.items():
            title=norm(rec.get('title',''))
            if len(title)>=15:
                titles[title].append(key)
        for c in self.context_evidence:
            pid=c['citing_paper']
            if pid not in self.reg.records or self.reg.records[pid]['kind']!='method_paper':
                continue
            filename=c['section'].split(' | ')[0]
            if filename not in (pid+'.txt',pid+'.supp.txt'):
                continue
            if filename not in self.context_sources:
                source=self.sources/filename
                self.context_sources[filename]=' '.join(source.read_text().split()) if source.exists() else ''
            sentence=' '.join(c['sentence'].split())
            if not sentence or sentence not in self.context_sources[filename]:
                continue
            cited=c['cited_node_id']
            if cited not in self.mapped_node_ids:
                continue
            target=cited if cited in self.reg.records and self.reg.records[cited]['kind']=='method_paper' else None
            if not target and present(c.get('cited_doi')):
                target=self.reg.lookup('doi',doi(c['cited_doi']))
            if not target:
                matches=titles.get(norm(c['cited_title']),[])
                roots={self.reg.root(k) for k in matches}
                if len(roots)==1:
                    target=roots.pop()
            if target:
                self.edge(pid,target,'stored_text',self.span(pid,target))
        self.canonical_edges()

    def choose_paths(self,source_rows,method_rows,map_rows):
        sources=defaultdict(set)
        for row in source_rows:
            if row.get('_key'):
                sources[row['stato_id']].add(self.reg.root(row['_key']))
        # A method may occur in its original paper and a later extension.
        # Preserve every declared owner rather than the last TSV row's owner.
        methods=defaultdict(set)
        for method in method_rows:
            methods[method['method_id']].add(method['paper_id'])
        for seed in self.seed:
            methods[seed['paper_id']].add(seed['paper_id'])
        pairs=set()
        for row in map_rows:
            if row['match']=='gap': continue
            pids=methods.get(row['item_id'])
            if not pids:
                # Components are mapped through their owning method.
                pids=methods.get(row['item_id'].split('.')[0],set())
            for pid in sorted(pids):
                for src in sources.get(row['stato_id'],[]):
                    pairs.add((self.reg.root(pid),row['stato_id'],src))
        mids={self.reg.root(s['paper_id']) for s in self.seed}
        for mid in mids:
            for tid,ss in sources.items():
                for src in ss:
                    if (mid,src) in self.edges: pairs.add((mid,tid,src))
        adjacency=defaultdict(set); reverse=defaultdict(set)
        for a,b in self.edges:
            adjacency[a].add(b); reverse[b].add(a)
        base={self.reg.root(s['paper_id']) for s in self.seed}|{s for ss in sources.values() for s in ss}
        selected=set(base)|{self.reg.root(k) for k in self.previous_keys}; out=[]
        def rank(path):
            internal=path[1:-1]
            return (-sum(k in base|{self.reg.root(x) for x in self.previous_keys} for k in internal), -sum(int(self.reg.records[k].get('n_citations') or 0) for k in internal), tuple(path))
        for mid,tid,src in sorted(pairs):
            found=[]
            if src in adjacency[mid] and self.args.max_depth>=1:
                found=[(mid,src)]
            elif self.args.max_depth>=2:
                found=[(mid,a,src) for a in adjacency[mid]&reverse[src] if a not in [mid,src]]
                if not found and self.args.max_depth>=3:
                    found=[(mid,a,b,src) for a in adjacency[mid] if a not in [mid,src] for b in adjacency[a]&reverse[src] if b not in [mid,a,src]]
            if found:
                for path in sorted(set(found),key=rank)[:2]:
                    selected.update(path)
                    out.append({'method_paper':mid,'stato_id':tid,'source_node':src,'length':len(path)-1,'_path':path})
            else:
                out.append({'method_paper':mid,'stato_id':tid,'source_node':src,'length':NA,'path':NA})
        return out,selected

    def public_ids(self,keys):
        mapping={}; used={s['paper_id'] for s in self.seed}|{r['node_id'] for r in self.previous_nodes}
        for k in sorted(keys):
            rec=self.reg.records[k]
            if rec['kind']=='method_paper':
                mapping[k]=k; continue
            if rec.get('_public_id'):
                mapping[k]=rec['_public_id']; continue
            author=rec.get('first_author') or 'unknown'
            # Crossref family names and Europe PMC family-initial strings are preferred.
            family=author.split(',')[0].strip()
            tokens=family.split()
            if len(tokens)>1:
                family=tokens[0] if re.fullmatch(r'[A-Z]{1,5}',tokens[-1]) else tokens[-1]
            family=norm(family) or 'unknown'
            words=re.findall(r'[A-Za-z0-9]+',unicodedata.normalize('NFKD',rec.get('title','')).encode('ascii','ignore').decode())
            stop={'a','an','the','of','and','for','in','on','to','with','from','by','using'}
            word=next((x.lower() for x in words if x.lower() not in stop),'paper')
            base=family+str(rec.get('year') or 'unknown')+word
            candidate=base; n=2
            while candidate in used:
                candidate=base+'_'+str(n); n+=1
            mapping[k]=candidate; used.add(candidate)
        return mapping

    def run(self):
        print('Loading seeds and resolving STATO sources',flush=True)
        self.load_seeds()
        mapped={r['method_id'].upper().replace('_',':') for r in read_table(self.tables/'map_layout.tsv') if r['side']=='stato'}
        terms=[r for r in read_table(self.tables/'stato_terms.tsv') if r['stato_id'] in mapped]
        srcrows=self.resolve_sources(terms)
        skeys={self.reg.root(r['_key']) for r in srcrows if r.get('_key')}
        self.enrich_oa(skeys)
        mids={self.reg.root(s['paper_id']) for s in self.seed}
        self.load_stored()
        for key in sorted(mids):
            rec=self.reg.records[self.reg.root(key)]
            if rec.get('doi'):
                data=self.client.get(OCI+'/references/doi:'+quote(rec['doi'],safe=''))
                if isinstance(data,list):
                    self.used.add('OpenCitations')
                    for item in data:
                        d=doi(item.get('cited',''))
                        if d:
                            self.edge(key,self.reg.add({'doi':d,
                                'oa':(re.search(r'openalex:(W\d+)',item.get('cited','')) or ['', ''])[1],
                                'pmid':(re.search(r'pmid:(\d+)',item.get('cited','')) or ['', ''])[1]}),'OpenCitations')
        print('Loading method references',flush=True)
        self.references(mids,epmc=True)
        # Resolve explicit deposited reference identifiers in batches, including
        # references absent from a service's indexed bibliography.
        for pid,m,raw in self.local_refs:
            if self.reg.aliases(m):
                target=self.reg.add(m)
                self.edge(pid,target,'stored_text')
        first={self.reg.root(b) for a,b in self.edges if self.reg.root(a) in mids}
        self.enrich_oa(first)
        self.match_local()
        first={self.reg.root(b) for a,b in self.edges if self.reg.root(a) in mids}
        # Only mapped STATO pairs need a multi-hop search. All method papers
        # already contribute their full direct references above, including the
        # length-one pairs independent of the ontology map.
        preliminary,_=self.choose_paths(srcrows,read_table(self.tables/'methods.tsv'),read_table(self.tables/'stato_map.tsv'))
        deep_mids={r['method_paper'] for r in preliminary if r['length']!=1}
        deep_first={self.reg.root(b) for a,b in self.edges if self.reg.root(a) in deep_mids}
        print('First reference layer:',len(first),'; mapped-pair search layer:',len(deep_first),flush=True)
        if self.args.max_depth>=3:
            self.references(deep_first,epmc=False)
        if self.args.max_depth>=2 and deep_mids:
            self.source_citers(skeys,deep_mids|deep_first)
        self.match_local()
        # Resolve aliases for second-layer records where source citers identify a
        # paper by PMID while a bibliography identifies it by OpenAlex ID/DOI.
        self.canonical_edges()
        # All competing path intermediates need citation counts before tie-breaking.
        adj=defaultdict(set)
        rev=defaultdict(set)
        for a,b in self.edges:
            adj[a].add(b)
            rev[b].add(a)
        candidates=set()
        for mid in mids:
            for source in {self.reg.root(k) for k in skeys}:
                candidates.update(adj[mid]&rev[source])
                if self.args.max_depth>=3:
                    for a in adj[mid]:
                        bs=adj[a]&rev[source]
                        if bs:
                            candidates.add(a)
                            candidates.update(bs)
        self.enrich_oa(candidates)
        self.canonical_edges()
        paths,selected=self.choose_paths(srcrows,read_table(self.tables/'methods.tsv'),read_table(self.tables/'stato_map.tsv'))
        print('Selected lineage nodes:',len(selected),'; completing direct edges',flush=True)
        expanded=set()
        while not {self.reg.root(k) for k in selected}.issubset({self.reg.root(k) for k in expanded}):
            pending={self.reg.root(k) for k in selected}-{self.reg.root(k) for k in expanded}
            self.references(pending,epmc=True,crossref_all=True)
            expanded.update(pending)
            self.match_local()
            paths,selected=self.choose_paths(srcrows,read_table(self.tables/'methods.tsv'),read_table(self.tables/'stato_map.tsv'))
        selected={self.reg.root(k) for k in selected}
        ids=self.public_ids(selected)
        for row in srcrows:
            if row.get('_key'):
                key=self.reg.root(row['_key']); rec=self.reg.records[key]
                row.update({k:rec.get(k,NA) for k in ['doi','pmid','pmcid','title','first_author','year']})
                row['node_id']=ids[key]
        nodes=[]
        for key in selected:
            rec=self.reg.records[key]
            nodes.append(dict(rec,node_id=ids[key]))
        # A seeded work becomes the canonical citation target under its paper_id.
        # Retain its former public node row as an identity alias: the old ID must
        # continue to denote the same work when existing maps refer to it.
        emitted={row['node_id'] for row in nodes}
        for old in self.previous_nodes:
            if old['node_id'] not in emitted:
                nodes.append(dict(old))
                emitted.add(old['node_id'])
        citations=[]
        for (a,b),services in self.edges.items():
            if a in selected and b in selected:
                span=self.span(a,b) or self.spans.get((a,b))
                citations.append({'citing_id':ids[a],'cited_id':ids[b],'found_in':'; '.join(sorted(services)), 'ref_span':span or NA})
        for row in paths:
            row['method_paper']=ids[row['method_paper']]
            row['source_node']=ids[row['source_node']]
            if '_path' in row: row['path']=' > '.join(ids[k] for k in row['_path'])
        write_table(self.tables/'stato_sources.tsv',['stato_id','label','source_kind','source_text','node_id','doi','pmid','pmcid','title','first_author','year','resolved_by'], sorted(srcrows,key=lambda r:(r['stato_id'],r['source_text'])))
        write_table(self.tables/'citation_nodes.tsv',['node_id','kind','title','first_author','year','venue','doi','pmid','pmcid','n_citations'],sorted(nodes,key=lambda r:r['node_id']))
        write_table(self.tables/'citations.tsv',['citing_id','cited_id','found_in','ref_span'],sorted(citations,key=lambda r:(r['citing_id'],r['cited_id'])))
        write_table(self.tables/'citation_paths.tsv',['method_paper','stato_id','source_node','length','path'],sorted(paths,key=lambda r:(r['method_paper'],r['stato_id'],r['source_node'],str(r.get('path')))))
        pair_lengths={}
        for row in paths: pair_lengths[(row['method_paper'],row['stato_id'],row['source_node'])]=str(row['length'])
        summary={'table_rows':{'stato_sources':len(srcrows),'citation_nodes':len(nodes),'citations':len(citations),'citation_paths':len(paths)},
          'mapped_stato_terms':len(terms),'terms_with_paper_source':len({r['stato_id'] for r in srcrows if r['source_kind']=='paper'}),
          'pairs_by_length':dict(sorted(Counter(pair_lengths.values()).items())), 'services_used':sorted(self.used),
          'http_failures':dict(sorted(self.client.failures.items())), 'requests':dict(sorted(self.client.stats.items())), 'notes':sorted(set(self.notes)),
          'method_to_method_edges':sum(r['citing_id'] in mids and r['cited_id'] in mids for r in citations),
          'stored_citation_spans':sum(r['ref_span']!=NA for r in citations)}
        diagnostics=Path(self.args.scratch_dir); diagnostics.mkdir(parents=True,exist_ok=True)
        (diagnostics/'lineage_summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
        print(json.dumps(summary,sort_keys=True),flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--tables-dir','--tables',default=str(ROOT/'tables'))
    ap.add_argument('--cache-dir',default=str(ROOT/'sources/citations_cache'))
    ap.add_argument('--scratch-dir',default=str(ROOT/'tmp/refresh'))
    ap.add_argument('--max-depth',type=int,choices=[1,2,3],default=3)
    ap.add_argument('--offline',action='store_true',help='reuse cache only; fail on any missing response')
    ap.add_argument('--probe',action='store_true',help='cache metadata service reachability checks')
    args=ap.parse_args()
    if args.probe: probe(Client(args.cache_dir,args.offline))
    else: Builder(args).run()

if __name__=='__main__':
    main()
