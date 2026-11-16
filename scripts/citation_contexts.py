#!/usr/bin/env python3
"""Refresh citation sentences, explicit relation readings, and the off-map frontier.

    PYTHONDONTWRITEBYTECODE=1 python scripts/citation_contexts.py
    PYTHONDONTWRITEBYTECODE=1 python scripts/citation_contexts.py --build-links
    PYTHONDONTWRITEBYTECODE=1 python scripts/citation_contexts.py --build-links --offline
    PYTHONDONTWRITEBYTECODE=1 python scripts/citation_contexts.py --check

Extraction uses retained XML/HTML/PDF text and bibliographies. Exact-whitespace
substring verification is mandatory. Existing paper/sentence/reference identities
keep context IDs; new identities use numbers above each paper's existing maximum.
All seed papers, method IDs, layout IDs and citation nodes belong to the map, with
seed paper IDs preferred for cited seed works. Abstract-only files may yield zero.

--build-links materializes explicit agent readings in tmp/refresh/readings.json;
frontier kinds come from those readings and frontier_kind_readings.json. Only the
highest-ranked 60 method works receive one public Europe PMC metadata query each,
using citation_paths.Client's rate limit, generic user agent and persistent cache.
Retained OpenAlex repository locations supplement this query without network I/O.
--offline refuses a cache miss. Other frontier routes remain NA. Diagnostics and
reading provenance remain under --scratch-dir (default tmp/refresh).
"""
import argparse
import collections
import csv
import hashlib
import html as htmlmod
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import unicodedata
from urllib.parse import parse_qs, unquote
from lxml import etree, html

ROOT = Path(__file__).resolve().parents[1]
FIELDS = 'context_id citing_paper ref_key cited_node_id cited_first_author cited_year cited_title cited_doi section sentence'.split()
LINK_FIELDS = 'context_id citing_paper citing_method_id cited_node_id cited_label relation conditions statement tag'.split()
FRONT_FIELDS = 'cited_first_author cited_year cited_title cited_doi cited_label n_relation_sentences citing_papers relations kind open_route'.split()
RELATIONS = set('uses extends special_case_of contains_special_case combines shares_structure_not_equivalent derivable_under_conditions inspired_by'.split())
OTHER = {'benchmark', 'data_or_tool', 'background'}
NA = 'NA'


def ws(s):
    return ' '.join(str(s or '').split())


def norm(s):
    return re.sub('[^a-z0-9]', '', unicodedata.normalize('NFKD', htmlmod.unescape(s or '')).encode('ascii', 'ignore').decode().lower())


def words(s):
    # PDF line wrapping splits bibliography words such as implemen- tation.
    s = re.sub(r'(?<=[A-Za-z])-\s+(?=[a-z])', '', s or '')
    return set(re.findall('[a-z0-9]+', unicodedata.normalize('NFKD', s).encode('ascii','ignore').decode().lower())) - set('a an the of for and in to with via from on by'.split())


def doi(s):
    m = re.search(r'10\.\d{4,9}/[^\s<>"&#?]+', unquote(s or ''), re.I)
    return m.group().rstrip('.,;:)').lower() if m else ''


def versionless_doi(value):
    """Strip a deposited preprint version, never a journal DOI suffix like btv659."""
    value = doi(value)
    return re.sub(r'v\d+$', '', value) if value.startswith(('10.1101/', '10.48550/arxiv.')) else value


def read(path):
    with path.open(newline='') as f:
        return list(csv.DictReader(f, delimiter='\t'))


def write(path, fields, rows):
    with path.open('w', newline='') as f:
        out = csv.DictWriter(f, fields, delimiter='\t', lineterminator='\n')
        out.writeheader()
        out.writerows({k: ws(r.get(k)) or NA for k in fields} for r in rows)


def clean(s):
    # Mirrors fetch_paper.py serialization; exact verification only collapses whitespace.
    return unicodedata.normalize('NFC', ws(htmlmod.unescape(s)))


def tag(n):
    return n.tag.rsplit('}', 1)[-1] if isinstance(n.tag, str) else ''


def quoted_title(text):
    for match in re.finditer(r'[“"]([^”"]{12,})[”"]',text):
        prefix=text[:match.start()].strip(' .;:')
        prefix=re.sub(r'\s*[([]?(?:19|20)\d{2}[a-z]?[)\]]?\s*[.,]?\s*$','',prefix)
        tokens=re.findall(r'[^\W\d_]+',prefix)
        author_words=all(t[0].isupper() or t.lower() in {'and','de','van','von','der','et','al'} for t in tokens)
        earlier_title=re.search(r'[A-Za-zÀ-ÿ]{2,}\.\s+[A-Z][a-z]{2,}',prefix)
        if author_words and not earlier_title:return match
    return None


def citation_author(prefix):
    prefix=re.sub(r'\s*[([]?(?:19|20)\d{2}[a-z]?[)\]]?\s*[.,]?\s*$','',prefix)
    prefix=re.sub(r'\bet\s+al\.?\s*$','',prefix.strip(' .;:'),flags=re.I)
    first=re.split(r',|;|\s+(?:and|&)\s+',prefix,maxsplit=1)[0].strip()
    first=re.sub(r'^(?:[A-ZÀ-ÖØ-Þ]\.\s*)+','',first).strip()
    if re.search(r'Consortium|Collaboration|Working Group',first,re.I):return first
    return first.split()[-1].strip(' .') if first.split() else ''


def is_math_reference(node):
    parent=node.getparent()
    if parent is None or tag(parent)!='sup':return False
    if re.match(r'\s*/\s*\d',parent.tail or ''):return True
    if ws(''.join(node.itertext()))!='2':return False
    previous=parent.getprevious()
    if previous is not None and tag(previous)=='sub':previous=previous.getprevious()
    base=ws(''.join(previous.itertext())) if previous is not None else ''
    if re.fullmatch(r'[α-ωΑ-Ω]',base):return True
    context=ws(''.join(parent.getparent().itertext())) if parent.getparent() is not None else ''
    return bool((base in {'r','R'} and re.search(r'correlation|squared|variance|coefficient|explained',context,re.I))
                or (base in {'h','H'} and re.search(r'heritability',context,re.I)))


def inline(node, marked=False):
    name = tag(node)
    if name in ('tex-math', 'annotation'):
        return clean(''.join(node.itertext()))
    if name in ('inline-formula', 'disp-formula', 'alternatives'):
        tex = next((n for n in node.iter() if tag(n) == 'tex-math'), None)
        math = next((n for n in node.iter() if tag(n) == 'math'), None)
        chosen = tex if tex is not None else math
        value = inline(chosen, marked) if chosen is not None else ''.join(node.itertext())
        label = next((clean(''.join(n.itertext())) for n in node if tag(n) == 'label'), '')
        return clean(value + (' ' + label if label and label not in value else ''))
    if name == 'math':
        tex = next((n for n in node.iter() if tag(n) == 'annotation' and 'tex' in n.get('encoding', '').lower()), None)
        return inline(tex, marked) if tex is not None else clean(' '.join(inline(n, marked) for n in node))
    children = [inline(n, marked) for n in node]
    if name == 'mfrac' and len(children) == 2:
        return '(' + children[0] + ')/(' + children[1] + ')'
    if name in ('msub', 'msup') and len(children) == 2:
        return children[0] + ('_{' if name == 'msub' else '^{') + children[1] + '}'
    if name == 'msubsup' and len(children) == 3:
        return children[0] + '_{' + children[1] + '}^{' + children[2] + '}'
    if name == 'msqrt':
        return 'sqrt(' + ' '.join(children) + ')'
    if name in ('mrow', 'mtable', 'mtr', 'mtd', 'munder', 'mover', 'munderover'):
        return clean(' '.join(children))
    value = node.text or ''
    for child, part in zip(node, children):
        value += part + (child.tail or '')
    value = clean(value)
    if marked and name == 'xref' and node.get('ref-type') == 'bibr':
        # Deposited XML can mistakenly tag a squared numerator as a citation.
        # An exponent immediately followed by a numeric denominator is math.
        if not is_math_reference(node):
            return '\ue000' + node.get('rid', '') + '\ue001' + value + '\ue002'
    return value


def unmark(s):
    marks = []
    pieces = []
    end = 0
    for m in re.finditer('\ue000(.*?)\ue001(.*?)\ue002', s):
        pieces.append(s[end:m.start()])
        pos = len(''.join(pieces))
        marks.append((pos, pos + len(m[2]), m[1]))
        pieces.append(m[2]); end = m.end()
    pieces.append(s[end:])
    plain = ''.join(pieces)
    # Position mapping accounts for whitespace changes exposed by marker removal.
    return ws(plain), [(len(ws(plain[:a]+'X'))-1, len(ws(plain[:b])), rid) for a,b,rid in marks]


ABBREV = {'al', 'e.g', 'i.e', 'eg', 'ie', 'fig', 'figs', 'eq', 'eqs', 'ref', 'refs', 'dr', 'mr', 'ms', 'vs', 'etc', 'no', 'sec', 'pp', 'approx', 'cf', 'supp', 'vol'}


def sentences(text):
    """Conservative sentence spans; preserve citation groups, initials and equations."""
    start = 0
    depth = 0
    for i,c in enumerate(text):
        if c in '([': depth += 1
        if c in ')]': depth = max(0,depth-1)
        if c not in '.?!':
            continue
        if c == '.':
            if re.match(r'\.\s*\.',text[i:]) or re.search(r'\.\s*$',text[max(0,i-3):i]):continue
            if i and i+1 < len(text) and text[i-1].isdigit() and text[i+1].isdigit(): continue
            token = re.search(r'([\w.]+)$',text[:i])
            token = token[1] if token else ''
            if token.lower() in ABBREV: continue
            if len(token)==1 and token.isupper() and not re.match(r'\s*(?:In|The|Our|This|That|These|Those|We|It|Here|A|An|First|Second)\b',text[i+1:]) and not re.search(r'Appendix [A-Z]$',text[:i]):continue
            if text[max(0,i-1):i+3] in ('e.g.', 'i.e.'): continue
        stop = i+1
        trailing=re.match(r'(?:\^\{\d+(?:[,–−-]\d+)*\})+',text[stop:])
        if trailing:stop+=trailing.end()
        while stop < len(text) and text[stop] in '\"”’)]': stop += 1
        if stop < len(text) and not text[stop].isspace(): continue
        if stop < len(text) and text[stop:].lstrip()[:1].islower() and not re.match(r'(?:fSuSiE|mvSuSiE|ash|mash|smash)\b',text[stop:].lstrip()): continue
        a=start
        while a<stop and text[a].isspace(): a+=1
        if a<stop: yield a,stop,text[a:stop]
        start=stop
    while start<len(text) and text[start].isspace():start+=1
    if start<len(text): yield start,len(text),text[start:]


def first(node, names):
    for name in names:
        hits = node.xpath('.//*[local-name()=$n]',n=name)
        if hits:return ws(''.join(hits[0].itertext()))
    return ''


def free_reference(text, key=''):
    text=ws(text)
    text=re.split(r'bioRxiv preprint doi:|this version posted|The copyright holder',text)[0]
    text=re.sub(r'^\[?\d+\]?[.)]?\s*','',text)
    year = re.search(r'\b((?:19|20)\d{2}[a-z]?)\b',text)
    # Author-year bibliographies put the year before the title; numbered Vancouver after it.
    yr = year[1] if year else ''
    author = re.split(r',|\s+(?:[A-Z]\.?\s*){1,3}(?:,|\b)|\s*\(', text, maxsplit=1)[0]
    if year and '(' in text[max(0,year.start()-2):year.start()] and len(text[year.end():].strip(')., '))>12:
        rest = text[year.end():].lstrip(')., ')
        title = re.split(r'\.\s+(?=[A-Z])',rest,maxsplit=1)[0]
    else:
        # Identify end of author list without treating initials as title boundaries.
        m = re.search(r'''(?:et\s+al\.?|[A-Z]{1,4}\.)\s+([‘“"']?[A-Z][A-Za-z0-9–-]{1,}|[A-Z]\s+[a-z])''',text)
        if not m:m = re.search(r'\.\s+([A-Z][A-Za-z0-9–-]{1,}|[A-Z]\s+[a-z])',text)
        rest = text[m.start(1):] if m else text
        title = re.split(r'\.\s+',rest,maxsplit=1)[0]
    # Numeric bibliographies may place initials before surnames and separate
    # the title with commas (SIAM/LaTeXML), without author-year parentheses.
    if re.match(r'^[A-ZÀ-ÖØ-Þ]\.', text):
        titled = re.search(r',\s+((?:[A-Z][a-z]{2,}|[A-Z]\s+[a-z])[^,]+)(?:,|$)', text)
        if titled:
            title = titled[1].strip(' .')
            first_author = re.split(r',|\s+and\s+', text, maxsplit=1)[0]
            author = re.sub(r'^(?:[A-ZÀ-ÖØ-Þ]\.(?:-[A-Z]\.)?\s*)+', '', first_author).strip()
    quoted=quoted_title(text)
    if quoted:
        title=quoted[1]
        author=citation_author(text[:quoted.start()]) or author
    # Book entries in browser bibliographies put publisher/place before year.
    book = re.search(r';[^;:.]+:\s*(?:19|20)\d{2}\.\s+(.+?)(?:\.\s*\[|$)', text)
    if book and not quoted:
        title = book[1].strip(' .')
    title=re.split(r''',\s+in\s+(?=[‘“"'])''',title,maxsplit=1,flags=re.I)[0]
    return {'key':key,'author':author,'year':yr,'title':title.strip(' ."'),'doi':doi(text)}


def xml_refs(root):
    refs={}
    for ref in root.xpath('//*[local-name()="ref-list"]/*[local-name()="ref"]'):
        rid=ref.get('id','')
        label=first(ref,['label']).strip(' [].') or rid
        m=free_reference(inline(ref),label)
        m['author']=first(ref,['surname']) or m['author']
        m['year']=first(ref,['year']) or m['year']
        m['title']=first(ref,['article-title','chapter-title']) or m['title']
        for el in ref.iter():
            if el.get('ext-link-type')=='google-scholar':
                q=parse_qs(el.get('{http://www.w3.org/1999/xlink}href',''))
                m['title']=(q.get('title') or [m['title']])[0]
                m['year']=(q.get('publication_year') or [m['year']])[0]
                m['author']=(q.get('author') or [m['author']])[0]
            if el.get('pub-id-type')=='doi' or el.get('ext-link-type')=='doi':
                m['doi']=doi(el.get('{http://www.w3.org/1999/xlink}href','') or ''.join(el.itertext())) or m['doi']
        if m['key']==rid:
            # Author-year references retain the XML reference label, e.g. R48.
            m['key']=rid
        refs[rid]=m
    return refs


class MarkHTML(HTMLParser):
    """The existing source HTML serializer with bibliography anchors marked."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines=[];self.buf=[];self.skip=0;self.heading=False;self.anchors=[]
    def flush(self):
        text=clean(''.join(self.buf))
        if text:self.lines.append(('## ' if self.heading else '')+text)
        self.buf=[]
    def handle_starttag(self,name,attrs):
        a=dict(attrs)
        if name in ('script','style','nav'):self.skip+=1
        if self.skip:return
        if name in ('p','h1','h2','h3','h4','li','div'):
            self.flush();self.heading=name in ('h1','h2','h3','h4')
        if name=='img' and a.get('alt'):self.buf.append(' '+a['alt']+' ')
        if name=='math' and a.get('alttext'):self.buf.append(' '+a['alttext']+' ')
        if name=='a':
            rid=a.get('href','').removeprefix('#')
            mark=rid.startswith('bib.') or 'xref-bibr' in a.get('class','').split()
            self.anchors.append(mark)
            if mark:self.buf.append('\ue000'+rid+'\ue001')
    def handle_endtag(self,name):
        if name in ('script','style','nav') and self.skip:self.skip-=1;return
        if self.skip:return
        if name=='a' and self.anchors:
            if self.anchors.pop():self.buf.append('\ue002')
        if name in ('p','h1','h2','h3','h4','li','div'):
            self.flush();self.heading=False
    def handle_data(self,data):
        if not self.skip:self.buf.append(data)


def html_refs(root):
    refs={}
    previous_authors = ''
    for ref in root.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," ltx_bibitem ")]'):
        rid=ref.get('id','')
        labels=ref.xpath('./span[contains(@class,"ltx_tag")]')
        label=ws(''.join(labels[0].itertext())) if labels else rid
        blocks=ref.xpath('./span[contains(@class,"ltx_bibblock")]')
        blocks=[b for b in blocks if 'ltx_bib_cited' not in b.get('class','').split()
                and not re.fullmatch(r'(?:Document|Link|DOI|\s|[,;:])+',ws(''.join(b.itertext())),re.I)]
        text=ws(' '.join(''.join(b.itertext()) for b in blocks))
        m=free_reference(text,label)
        year=re.search(r'\b(?:19|20)\d{2}[a-z]?\b',label)
        if year:m['year']=year[0]
        if len(blocks)>1 and not re.search(r'\b(?:19|20)\d{2}\b', ws(''.join(blocks[0].itertext()))):
            m['title']=ws(''.join(blocks[1].itertext())).rstrip('.')
        quoted=re.match(r'''^[‘“'"]([^’”'"]{15,})[’”'"]''',m['title'])
        if quoted:m['title']=quoted[1]
        # Author-year labels provide clean surnames; numeric labels are keys,
        # so take their author from the actual bibliography block instead.
        if re.search(r'[A-Za-z]', label):
            m['author']=re.split(r'\s+(?:et\b|and\b)|\s*\(',label)[0]
        elif blocks:
            authors = ws(''.join(blocks[0].itertext())).rstrip('.')
            author = re.split(r',|\s+(?:and|&)\s+', authors, maxsplit=1)[0]
            m['author'] = re.sub(r'^(?:[A-Z]\.\s*)+', '', author).strip()
        # LaTeXML/SIAM explicitly marks author names and work titles. A rule
        # in place of names repeats the preceding bibliography's authors.
        names = ref.xpath('.//*[contains(@class, "ltx_font_smallcaps")]')
        titles = ref.xpath('.//*[contains(@class, "ltx_font_italic")]')
        repeated = ref.xpath('.//*[contains(@class, "ltx_rule")]')
        authors = ws(''.join(names[0].itertext())) if names else (previous_authors if repeated else '')
        if authors and titles:
            candidate=ws(''.join(titles[0].itertext())).rstrip('.')
            if candidate.lower() not in {'in','and','ed','eds','vol','pp'}:m['title']=candidate
            family = re.split(r',|\s+and\s+', authors, maxsplit=1)[0]
            m['author'] = re.sub(r'^(?:[A-ZÀ-ÖØ-Þ]\.(?:-[A-Z]\.)?\s*)+', '', family).strip()
            previous_authors = authors
        quoted=quoted_title(text)
        if quoted:
            m['title']=quoted[1]
            m['author']=citation_author(text[:quoted.start()]) or m['author']
        elif titles:
            # A book title can be italicized in a single bibliography block.
            # Article titles precede their italicized venue in a separate
            # sentence; do not substitute that venue for the work's title.
            candidate=ws(''.join(titles[0].itertext())).rstrip('.')
            prefix=text.partition(candidate)[0].strip()
            name_tokens=re.findall(r'[^\W\d_]+',prefix)
            names_only=bool(name_tokens) and all(t[0].isupper() or t.lower() in {'and','de','van','von','der'} for t in name_tokens)
            earlier_sentence=re.search(r'[A-Za-zÀ-ÿ]{2,}\.\s+\S',prefix)
            if candidate and candidate.lower() not in {'in','and','ed','eds','vol','pp'} and names_only and not earlier_sentence:
                m['title']=candidate
                m['author']=citation_author(prefix) or m['author']
        # ar5iv exposes bibliography metadata explicitly for many styles.
        # These fields outrank block positions and venue/backlink text.
        def semantic(cls):
            hits=ref.xpath('.//*[contains(concat(" ",normalize-space(@class)," "),$c)]',c=' '+cls+' ')
            return ws(''.join(hits[0].itertext())) if hits else ''
        title=semantic('ltx_bib_title');author=semantic('ltx_bib_author');year=semantic('ltx_bib_year')
        if title and title.lower() not in {'in','and','ed','eds','vol','pp'}:m['title']=title.strip(' .“”"')
        if author:m['author']=citation_author(author) or m['author']
        year_match=re.search(r'(?:19|20)\d{2}[a-z]?',year)
        if year_match:m['year']=year_match[0]
        for anchor in ref.xpath('.//a[@href]'):
            identifier=doi(anchor.get('href',''))
            if identifier:
                m['doi']=identifier;break
        refs[rid]=m
    for ref in root.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," ref-cit ")]'):
        number=ref.get('id','').rsplit('.',1)[-1]
        if not number.isdigit():continue
        def value(cls):
            hits=ref.xpath('.//*[contains(concat(" ",normalize-space(@class)," "),$c)]',c=' '+cls+' ')
            return ws(''.join(hits[0].itertext())) if hits else ''
        m=free_reference(ws(''.join(ref.itertext())),number)
        m.update(author=value('cit-name-surname') or m['author'],title=value('cit-article-title') or m['title'],year=value('cit-pub-date') or m['year'],doi=doi(ref.get('data-doi','')) or m['doi'])
        labels=ref.xpath('ancestor-or-self::*[local-name()="li"][1]//*[contains(concat(" ",normalize-space(@class)," ")," ref-label ")]')
        label=re.search(r'\d+',''.join(labels[0].itertext())) if labels else None
        if label:m['key']=label[0]
        refs['ref-'+number]=m
    return refs


def prepare_html_citations(root):
    """Use retained local bibliographies and leave mathematical powers unmarked.

    Some deposited publisher HTML links supplementary [1..N] to the main
    reference list. The separate local list and its explicit labels recover
    those links without changing any retained source text.
    """
    anchors=root.xpath('//*[local-name()="a"]')
    for anchor in anchors:
        if is_math_reference(anchor):
            anchor.set('class',' '.join(c for c in anchor.get('class','').split() if c!='xref-bibr'))
            anchor.attrib.pop('href',None)
    class_test='contains(concat(" ",normalize-space(@class)," ")," ref-list ")'
    lists=root.xpath('//*['+class_test+'][not(ancestor::*['+class_test+'])]')
    if len(lists)>1:
        positions={node:i for i,node in enumerate(root.iter())}
        spans=[(positions[b],max(positions[n] for n in b.iter()),b) for b in lists]
        local=[]
        for start,end,bibliography in spans[1:]:
            mapping={}
            for entry in bibliography.xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," ref-cit ")]'):
                identifier=entry.get('id','').rsplit('.',1)[-1]
                labels=entry.xpath('ancestor-or-self::*[local-name()="li"][1]//*[contains(concat(" ",normalize-space(@class)," ")," ref-label ")]')
                label=re.search(r'\d+',''.join(labels[0].itertext())) if labels else None
                if identifier.isdigit() and label:mapping[label[0]]='ref-'+identifier
            local.append((start,end,mapping))
        for anchor in anchors:
            pos=positions[anchor]
            if any(a<=pos<=b for a,b,_ in spans):continue
            supplementary=any(re.match(r'^\s*(?:Supplementary|Supplemental|Supporting)\b',
                ws(''.join(heading.itertext())),re.I)
                for section in anchor.iterancestors()
                for heading in section.xpath('./h2|./h3|./h4|./h5'))
            if pos<=spans[0][1] and not supplementary:continue
            match=re.fullmatch(r'#ref-(\d+)',anchor.get('href',''))
            if not match:continue
            following=next((item for item in local if pos<item[0]),local[-1])
            if match[1] in following[2]:anchor.set('href','#'+following[2][match[1]])
    return html.tostring(root,encoding='unicode')


class Matcher:
    def __init__(self):
        seeds=read(ROOT/'seed/seed_list.tsv')
        method_rows=read(ROOT/'tables/methods.tsv')
        layout=read(ROOT/'tables/map_layout.tsv')
        self.nodes=read(ROOT/'tables/citation_nodes.tsv')
        self.allowed=({n['node_id'] for n in self.nodes}|{r['paper_id'] for r in seeds}|
                      {r['method_id'] for r in method_rows}|{r['method_id'] for r in layout})
        seed_ids={s['paper_id'] for s in seeds}
        # Seed identity wins when a newly seeded work already had a lineage ID.
        self.nodes=[n for n in self.nodes if n['node_id'] not in seed_ids]
        self.nodes += [dict(node_id=s['paper_id'],title=s['title'],first_author=s['first_author'],year=s['year'],doi=s['doi']) for s in seeds]
        self.dois={doi(n['doi']):n['node_id'] for n in self.nodes if doi(n['doi'])}
        self.titles={norm(n['title']):n['node_id'] for n in self.nodes if n['title']!=NA}
        self.seed_ids=seed_ids
        for s in seeds:
            for value in (s['doi'],s['preprint_id']):
                if doi(value):self.dois[versionless_doi(value)]=s['paper_id']
    def match(self,m):
        d=versionless_doi(m.get('doi',''))
        if d and d in self.dois:return self.dois[d],'doi'
        if norm(m['title']) in self.titles:return self.titles[norm(m['title'])],'title'
        candidates=[]
        for n in self.nodes:
            # Years may differ between preprint, online publication and journal issue.
            if not m['year'] or not n['year'].isdigit():continue
            yr=re.search(r'\d{4}',m['year'])
            if not yr or abs(int(yr[0])-int(n['year']))>1:continue
            if re.match(r'Supporting data\b',m['title'],re.I):continue
            a=words(m['author']);b=words(n['first_author'])
            if not a&b:continue
            x,y=words(m['title']),words(n['title']);shared=len(x&y)
            mt, nt = norm(m['title']), norm(n['title'])
            # Some JATS mixed-citations concatenate author/publisher text with
            # the title. Require the same author/year and a substantial exact
            # title substring before accepting that retained format.
            glued = re.match(r'^[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+[A-Z]', m['title'])
            contained = bool(glued) and min(len(mt), len(nt)) >= 25 and nt in mt
            if contained or (shared>=4 and shared/max(1,len(x|y))>=.65):
                candidates.append(n['node_id'])
        preferred=set(candidates)&self.seed_ids
        if len(preferred)==1:return preferred.pop(),'author_year_title'
        if len(set(candidates))==1:return candidates[0],'author_year_title'
        return NA,''


def numeric_refs(text):
    """Read explicit numbered bibliography entries, including PDF-flattened lists."""
    starts=list(re.finditer(r'(?:^|\s)(?:\*\s*)?(?:\[(\d+)\]|(\d{1,3})\.(?!\d))\s*(?=[A-ZÀ-ÖØ-Þ])',text))
    result={}
    for i,m in enumerate(starts):
        end=starts[i+1].start() if i+1<len(starts) else len(text)
        key=m[1] or m[2]
        result[key]=free_reference(text[m.end():end],key)
    return result


def refs_for_text(text, main):
    refs={m['key'].strip(' [].'):m for m in main.values()}
    heading=re.search(r'(?im)^(?:## )?(?:\d{2,5}[ \t]+)?(?:References?(?=[ \t]*(?::|$|\d{2,5}[ \t]+1\.))[ \t]*:?|Bibliography\b|(?:\d+\s+)?Supplementary References(?=\s*\[|[ \t]*$))',text)
    if not heading:
        # DOCX/table supplements often end in an unheaded local bibliography.
        # Require a year on the first entry to distinguish numbered algorithms.
        heading=re.search(r'(?m)^(?=1\.\s+[A-Z][^\n]*(?:19|20)\d{2})',text)
    if not heading:return refs
    tail=text[heading.end():]
    if re.match(r'\s*\d{2,5}[ \t]+\d{1,3}\.[ \t]*[A-Z]',tail):
        # Numbered manuscript lines precede the actual bibliography numbers.
        # Remove those prefixes only in reference metadata, never in sentences.
        tail=re.sub(r'(?m)^[ \t]*\d{2,5}[ \t]+(?=\d{1,3}\.[ \t]*[A-Z])','',tail)
    local=numeric_refs(tail) if re.match(r'\s*(?:\*\s*)?(?:\[\d+\]|\d+\.)\s*',tail) else {}
    if local:
        if min(int(k) for k in local)>max([int(k) for k in refs if k.isdigit()] or [0]):refs.update(local)
        else:refs=local
    else:
        # Select first-author starts since the previous parenthesized year. The
        # source may flatten several references onto a single PDF text line.
        flat=ws(tail);previous=0
        for i,ym in enumerate(re.finditer(r'\((?:19|20)\d{2}[a-z]?\)\.',flat)):
            prefix=flat[previous:ym.start()]
            starts=list(re.finditer(r"(?<![\w,])(?:[A-Z]\.\s+)?[A-Z][A-Za-z’\-]+,\s+(?:[A-Z]\.|[A-Z],)|(?:[A-Z]\.\s+[A-Z][A-Za-z’\-]+|[A-Z][A-Za-z’\-]+\s+Aps)\s*$",prefix))
            if starts:
                start=previous+starts[0].start()
                rest=flat[ym.end():]
                stop=re.search(r'\.\s+(?=[A-Z])',rest)
                end=ym.end()+stop.end() if stop else len(flat)
                item=free_reference(flat[start:end],f'local{i+1}')
                if item['title']:refs['local'+str(i+1)]=item
            previous=ym.end()
    return refs


def supplement_aliases(text, refs, main):
    """Retain local numbering and recognize bibliography-backed author-year aliases.

    PDF small capitals can split surnames (S TEPHENS). These repairs apply only
    to bibliography metadata; retained source sentences remain byte faithful.
    """
    refs=dict(refs)
    if '## References' in text:
        tail=text.split('## References',1)[1]
        smallcaps=re.sub(r'\b([A-Z])\s+([A-Z]{2,})\b',r'\1\2',ws(tail))
        starts=list(re.finditer(r"(?:^|(?<=\.\s))([A-Z][A-Z’\-]+)\s*,\s*.*?\(((?:19|20)\d{2}[a-z]?)\)\.\s*",smallcaps))
        for i,m in enumerate(starts):
            end=starts[i+1].start() if i+1<len(starts) else len(smallcaps)
            body=smallcaps[m.end():end]
            title=re.split(r'\.\s+(?=[A-Z])',body,maxsplit=1)[0].strip(' .')
            key='author_year_'+norm(m[1])+m[2]
            if title:refs[key]={'key':key,'author':m[1].title(),'year':m[2],'title':title,'doi':doi(body)}
    # Main references are available for narrative citations even if a supplement
    # resets its numeric bibliography. Never substitute main numeric keys.
    existing={(norm(r['author']),r['year'],norm(r['title'])) for r in refs.values()}
    for key,r in main.items():
        ident=(norm(r['author']),r['year'],norm(r['title']))
        if ident not in existing:
            refs['main:'+key]=r
    # A unique author-year near match resolves only the observed narrative form.
    # This covers online-year versus issue-year citations in peer-review files.
    for m in re.finditer(r"(?<!and )(?<!& )\b([A-Z][A-Za-z’\-]+)\s*(?:\(|,\s*)((?:19|20)\d{2})\)?",text):
        author,year=m[1],m[2]
        exact=[r for r in refs.values() if norm(author) in {norm(t) for t in r['author'].replace('.',' ').split()} and r['year']==year]
        if exact:continue
        candidates=[r for r in refs.values() if norm(author) in {norm(t) for t in r['author'].replace('.',' ').split()} and re.fullmatch(r'\d{4}',r['year']) and abs(int(r['year'])-int(year))==1]
        identities={norm(r['title']) for r in candidates}
        if len(identities)==1:
            r=sorted(candidates,key=lambda r:r['key'])[0]
            refs['year_alias:'+author+year]=dict(r,key='year_alias:'+author+year,year=year)
    return refs


def supplement_regions(part):
    """Scope inline peer-review bibliographies to their reviewer/reply section.

    Numbering can restart several times in a single retained PDF. A bibliography
    ending a reviewer or author reply owns that section, rather than the main
    article's same-numbered references. Return exact source slices.
    """
    lines=part.splitlines(keepends=True)
    offsets=[];offset=0
    for line in lines:
        offsets.append(offset);offset+=len(line)
    blocks=[]
    for i,line in enumerate(lines):
        if not re.match(r'^(?:\[1\]\s+|References:\s*1\.\s*)[A-Z]',line) or not re.search(r'\b(?:19|20)\d{2}\b',line):
            continue
        j=i+1
        while j<len(lines) and not re.match(r'^(?:Reviewer|Reviewers|Re\.|## )',lines[j]):
            # Reference continuations can wrap journal names or URLs.
            if not lines[j].strip():break
            j+=1
        end=offsets[j] if j<len(lines) else len(part)
        bibliography=part[offsets[i]:end]
        local=numeric_refs(bibliography)
        if not local:continue
        previous=blocks[-1]['end'] if blocks else 0
        headers=list(re.finditer(r'(?m)^Reviewer\s*#\d+[^\n]*',part[previous:offsets[i]]))
        start=previous+headers[-1].start() if headers else previous
        blocks.append(dict(start=start,end=end,ref_start=offsets[i],refs=local))
    if not blocks:return [(0,part,None,[])]
    regions=[]
    for i,block in enumerate(blocks):
        start=block['start'] if i else 0
        end=blocks[i+1]['start'] if i+1<len(blocks) else len(part)
        excluded=[part[b['ref_start']:b['end']] for b in blocks if start<=b['ref_start']<end]
        regions.append((part[:start].count('\n'),part[start:end],block['refs'],excluded))
    return regions


def numbers(s):
    out=[]
    for part in s.replace('–','-').replace('−','-').split(','):
        part=part.strip()
        if re.fullmatch(r'\d+\s*-\s*\d+',part):
            a,b=map(int,re.split(r'\s*-\s*',part))
            if 0<a<=b<5000:out.extend(map(str,range(a,b+1)))
        elif part.isdigit():out.append(part)
    return out


def text_marks(line,refs,unresolved):
    marks=[]
    mathspans=[m.span() for m in re.finditer(r'\$\$[\s\S]*?\$\$|(?<!\$)\$(?!\$)[^$]*\$',line)]
    # Retained supplements may contain R function definitions. Bracketed
    # array indices inside their balanced bodies are executable syntax.
    code_spans=[]
    for function in re.finditer(r'(?:<-|=)\s*function\s*\(',line):
        brace=line.find('{',function.end())
        if brace<0:continue
        depth=0
        for pos in range(brace,len(line)):
            if line[pos]=='{':depth+=1
            elif line[pos]=='}':
                depth-=1
                if depth==0:
                    code_spans.append((function.start(),pos+1));break
    for m in re.finditer(r'\[(\d+(?:\s*[,–−-]\s*\d+)*)\]|\^\{(\d+(?:\s*[,–−-]\s*\d+)*)\}',line):
        if (m[1] and re.search(r'[A-Za-z0-9_)\]]$',line[:m.start()])
                and any(a<=m.start()<b for a,b in code_spans)):continue
        if m[2] and (any(a<=m.start()<b for a,b in mathspans) or re.search(r'(?:[0-9\u0370-\u03ff]|\b[A-Za-z]|\b[hNnM]_(?:\{[^{}]*\}|\w))$',line[:m.start()])):continue
        # Console vector indices and table row labels precede numeric columns,
        # rather than prose. Their bracketed numbers are not sentence markers.
        if re.match(r'\s+[+-]?\d+(?:\.\d+)?\s+[+-]?\d',line[m.end():]):continue
        keys=numbers(m[1] or m[2])
        if '0' in keys:continue  # mathematical intervals, never reference zero
        for k in keys:
            if k in refs:marks.append((m.start(),m.end(),k))
            else:unresolved.append({'marker':m[0],'ref':k})
    # Author-year citation groups: match actual bibliography surnames, not arbitrary years.
    seen=set()
    for k,r in refs.items():
        year=re.search(r'(?:19|20)\d{2}[a-z]?',r.get('year',''))
        if not year:continue
        tokens=[t for t in re.findall(r'[^\W\d_]+',r['author']) if len(t)>1]
        if not tokens:continue
        # Query metadata often uses initials first, structured metadata surname first.
        surname=tokens[-1] if len(tokens)>1 and len(tokens[0])<=2 else tokens[0]
        pair=(norm(surname),year[0])
        if pair in seen:continue
        seen.add(pair)
        pat=r'\b(?:'+re.escape(ws(r['author']).rstrip('.'))+'|'+re.escape(surname)+')'+r'(?:,\s+[A-Z][\w’\-]+)*\s*(?:\s+(?:and|&)\s+[A-Z][\w’\-]+|\s+et\.?\s*al\.?)?\s*(?:[,;(]|\[|\^\{)?\s*'+year[0]+r'\b(?:\)|\]|\})?'
        for m in re.finditer(pat,line,re.I):marks.append((m.start(),m.end(),k))
    # Report unresolved author-year citations instead of silently assuming an
    # absent bibliography entry. Only narrative/group citation shapes are counted.
    pat=r"\b[A-Z][A-Za-zÀ-ÿ’\-]+(?:\s+(?:et\.?\s*al\.?|and\s+[A-Z][A-Za-zÀ-ÿ’\-]+))?\s*(?:,\s*|\(\s*)(?:19|20)\d{2}[a-z]?\)?"
    for m in re.finditer(pat,line):
        if not any(a<=m.start()<b or m.start()<=a<m.end() for a,b,_ in marks):
            unresolved.append({'marker':m[0],'ref':'unresolved author-year'})
    return marks


def source_lines(text):
    heading=NA;inrefs=False
    # Browser exports include numeric author-affiliation superscripts before
    # the abstract; these markers are not bibliographic citations.
    start = re.search(r'(?im)^## (?:Abstract|Summary)\s*$', text)
    first_content = text[:start.start()].count('\n') + 1 if start else 0
    for n,line in enumerate(text.splitlines(),1):
        if n < first_content:
            continue
        line=ws(line)
        if line.startswith('## '):
            heading=line[3:]
            inrefs=heading.lower() in ('references','bibliography')
            continue
        if re.match(r'^(?:REFERENCES|References)\b|^(?:\d+\s+)?Supplementary References(?:\s+\[|$)',line):inrefs=True;continue
        if line and not inrefs:yield n,heading,line


def extract(args):
    matcher=Matcher();rows=[];audit={'papers':{},'failed_substring_rows':0,'matching':collections.Counter(),'source_hashes':{}}
    previous_path=args.output_dir/'citation_contexts.tsv'
    if not previous_path.exists():previous_path=ROOT/'tables/citation_contexts.tsv'
    previous=read(previous_path) if previous_path.exists() else []
    stable={};scoped_stable={};detailed_stable={};used_context_ids=set();highest=collections.defaultdict(int)
    def identity(c):
        return (c['citing_paper'],c['section'].split(' | ')[0],c['sentence'],c['ref_key'])
    for c in previous:
        stable.setdefault(identity(c),c['context_id'])
        scoped_stable.setdefault((identity(c),c['section']),c['context_id'])
        work=versionless_doi(c['cited_doi']) or norm(c['cited_title'])
        detailed_stable.setdefault((identity(c),c['section'],work),c['context_id'])
        number=re.search(r':x(\d+)$',c['context_id'])
        if number:highest[c['citing_paper']]=max(highest[c['citing_paper']],int(number[1]))
    reused=0
    paths=sorted(p for p in (ROOT/'sources').glob('*.txt') if '.raw.' not in p.name)
    papers=sorted({p.name.removesuffix('.supp.txt').removesuffix('.txt') for p in paths})
    if args.paper_ids:
        unknown=set(args.paper_ids)-set(papers)
        if unknown:raise ValueError('No stored text for '+', '.join(sorted(unknown)))
        papers=sorted(args.paper_ids)
    for paper in papers:
        main_path=ROOT/'sources'/f'{paper}.txt'
        texts={p.name:p.read_text() for p in [main_path,ROOT/'sources'/f'{paper}.supp.txt'] if p.exists()}
        for name,t in texts.items():audit['source_hashes'][name]=hashlib.sha256(t.encode()).hexdigest()
        main=texts[main_path.name];refs={};blocks=[];unresolved=[];unmatched=[]
        xmlpath=ROOT/'sources'/f'{paper}.raw.xml';htmlpath=ROOT/'sources'/f'{paper}.raw.html'
        if xmlpath.exists():
            tree=etree.parse(str(xmlpath),etree.XMLParser(resolve_entities=False,no_network=True))
            refs=xml_refs(tree)
            for node in tree.xpath('//*[local-name()="xref"][@ref-type="bibr"]'):
                if node.xpath('ancestor::*[local-name()="ref-list" or local-name()="td" or local-name()="th"]'):continue
                parent=node.getparent()
                while parent is not None and tag(parent) not in ('p','fig','table-wrap','list-item','disp-formula'):
                    parent=parent.getparent()
                if parent is not None and parent not in blocks:blocks.append(parent)
            blocks=[unmark(inline(b,True)) for b in blocks]
        if htmlpath.exists() and not blocks:
            raw=htmlpath.read_text();document=html.fromstring(raw);html_references=html_refs(document)
            raw=prepare_html_citations(document)
            parser=MarkHTML();parser.feed(raw);parser.flush()
            html_blocks=[unmark(s) for s in parser.lines if '\ue000' in s]
            # A retained XML document may contain only abstract metadata while
            # the neighboring HTML supplies the stored full text and citations.
            if html_blocks or not refs:
                refs=html_references;blocks=html_blocks
        # LDpred's main HTML was retained as text without its reference list. Cached
        # Crossref bibliography keys explicitly encode bib1...bib65, unlike EPMC order.
        if paper=='ldpred' and not refs:
            key='https://api.crossref.org/works/10.1016%2Fj.ajhg.2015.09.001'
            path=ROOT/'sources/citations_cache'/(hashlib.sha256(key.encode()).hexdigest()+'.json')
            if path.exists():
                obj=json.loads(json.loads(path.read_text())['body'])['message']
                for r in obj.get('reference',[]):
                    m=re.search(r'_bib(\d+)$',r.get('key',''))
                    if m:refs[m[1]]={'key':m[1],'title':r.get('article-title') or r.get('series-title',''),'author':r.get('author',''),'year':r.get('year',''),'doi':doi(r.get('DOI',''))}
                audit['ldpred_bibliography']=str(path.relative_to(ROOT))+' (explicit numbered bib keys)'
        found=[];covered=set();main_lines=list(source_lines(main))
        for plain,marks in blocks:
            # Bibliography back-links may serialize as a bare number. They have
            # no containing prose and must not align to digits in unrelated text.
            if re.fullmatch(r'\d+(?:\s*[,–−-]\s*\d+)*', plain):
                audit.setdefault('isolated_numeric_blocks_skipped', 0)
                audit['isolated_numeric_blocks_skipped'] += 1
                continue
            matches=[(n,h,l,l.find(plain)) for n,h,l in main_lines if plain in l]
            if matches:
                n,heading,line,offset=matches[0]
                mapped=[(a+offset,b+offset,rid,n,heading,line) for a,b,rid in marks]
            else:
                mapped=[]
                # Captions inside figures/tables can be serialized separately. Align
                # each marker using exact local text, then take the stored sentence.
                for a,b,rid in marks:
                    candidates=[]
                    for radius in (160,80,40,20):
                        lo=max(0,a-radius);hi=min(len(plain),b+radius)
                        anchor=plain[lo:hi]
                        candidates=[(n,h,l,l.find(anchor)+a-lo) for n,h,l in main_lines if anchor in l]
                        if len(candidates)==1:break
                    if len(candidates)==1:
                        n,h,l,pos=candidates[0];mapped.append((pos,pos+b-a,rid,n,h,l))
                    else:
                        unmatched.append({'paragraph':plain,'refs':[rid]})
            for a,b,rids,n,heading,line in mapped:
                covered.add(n)
                for rid in rids.split():
                    if rid not in refs:
                        unresolved.append({'marker':line[a:b],'ref':rid});continue
                    for x,y,sentence in sentences(line):
                        if x<=a<y:
                            found.append((0,n,x,refs[rid],heading,sentence));break
            # Numeric ranges may use only endpoint xrefs in the source markup.
            for m in re.finditer(r'(?<!\d)(\d{1,3})\]?\s*[–−-]\s*\[?(\d{1,3})(?!\d)',plain):
                if not matches or not any(a<=m.end() and b>=m.start() for a,b,_ in marks):continue
                n,heading,line,offset=matches[0]
                for k in numbers(m[1]+'-'+m[2]):
                    r=next((r for r in refs.values() if r['key'].strip(' [].')==k or r['key'] in ('B'+k,'R'+k)),None)
                    if r:
                        for x,y,sentence in sentences(line):
                            if x<=offset+m.start()<y:found.append((0,n,x,r,heading,sentence));break
        # Fall back only for text with no raw in-text markup. Unaligned structured
        # blocks are reported rather than guessing where individual bare digits occur.
        if not blocks:
            local=refs_for_text(main,refs)
            wrapped=[]
            for n,h,line in main_lines:
                # Browser/PDF serializers may wrap an author-year marker between
                # its author and year. Join only that explicit citation boundary.
                if (wrapped and re.search(r'et\.?\s+al\.?\s*[,(\[]?\s*$',wrapped[-1][2])
                        and re.match(r'^(?:\(|\[|\^\{)?\s*(?:19|20)\d{2}',line)):
                    wrapped[-1][2]+=' '+line
                else:
                    wrapped.append([n,h,line])
            for n,h,line in wrapped:
                for a,b,k in text_marks(line,local,unresolved):
                    for x,y,s in sentences(line):
                        if x<=a<y:found.append((0,n,x,local[k],h,s));break
        for filename,text in texts.items():
            if not filename.endswith('.supp.txt'):continue
            # Numbering is local to each stored PDF; References resets at each heading.
            parts=re.split(r'(?=^## Supplement:)',text,flags=re.M)
            base=0
            for part in parts:
                for region_line,region,local_override,excluded in supplement_regions(part):
                    # Unheaded numbered bibliographies are local to this file.
                    refhead=re.search(r'(?m)^((?:\d+\s+){0,12})References?(?=[ \t]*(?::|$|\d{2,5}[ \t]+1\.))(?:[ \t]*:[ \t]*|[ \t]+|$)',region)
                    unheaded=re.search(r'(?m)^(?=1\.\s+[A-Z][^\n]*(?:19|20)\d{2})',region)
                    prepared=re.sub(r'\bSupplementary figures\b', '\n## Supplementary figures\n',region)
                    if refhead and '## References' not in region:
                        prepared=region[:refhead.start()]+'\n## References\n'+region[refhead.end():]
                    elif unheaded and '## References' not in region:
                        prepared=region[:unheaded.start()]+'\n## References\n'+region[unheaded.start():]
                    local=supplement_aliases(prepared,local_override if local_override is not None else refs_for_text(prepared,refs),refs)
                    chunks=[]
                    for n,h,line in source_lines(prepared):
                        if chunks and chunks[-1][1]==h:chunks[-1][2]+=' '+line
                        else:chunks.append([n,h,line])
                    for n,h,line in chunks:
                        spans=list(sentences(line))
                        skip=[]
                        for refblock in excluded:
                            refline=ws(refblock)
                            pos=line.find(refline)
                            if pos>=0:skip.append((pos,pos+len(refline)))
                        for a,b,k in text_marks(line,local,unresolved):
                            if any(lo<=a<hi for lo,hi in skip):continue
                            for x,y,s in spans:
                                if x<=a<y:found.append((1,base+region_line+n,x,local[k],h,s));break
                base+=len(part.splitlines())
        seen=set();count=0
        for source,n,x,r,heading,s in sorted(found,key=lambda t:(t[0],t[1],t[2],t[3]['key'])):
            work=versionless_doi(r['doi']) or norm(r['title'])
            ident=(source,s,r['key'],work)
            if ident in seen:continue
            seen.add(ident)
            # Wrapped reference-list entries can survive PDF paragraph joining.
            # A numbered entry containing this reference's own title is a
            # bibliography record, rather than an in-text citation sentence.
            if (source and re.match(r'^\[\d+\]\s+[A-Z]',s)
                    and len(norm(r['title']))>=20 and norm(r['title']) in norm(s)):
                audit.setdefault('bibliography_rows_skipped',0)
                audit['bibliography_rows_skipped']+=1
                continue
            name=f'{paper}.supp.txt' if source else f'{paper}.txt'
            if s not in ws(texts[name]):
                audit['failed_substring_rows']+=1;continue
            count+=1
            r=dict(r)
            self_node=next((n for n in matcher.nodes if n['node_id']==paper),None)
            ry=re.search(r'\d{4}',r.get('year',''))
            if (self_node and versionless_doi(r.get('doi',''))==versionless_doi(self_node.get('doi',''))
                    and versionless_doi(r.get('doi','')) and ry and str(self_node.get('year','')).isdigit()
                    and abs(int(ry[0])-int(self_node['year']))>1
                    and norm(r.get('title',''))!=norm(self_node.get('title',''))):
                audit.setdefault('conflicting_self_reference_identifiers',[]).append(
                    {'paper':paper,'ref_key':r['key'],'rejected_doi':r['doi'],'bibliography_title':r['title'],'bibliography_year':r['year']})
                r['doi']=''
            node,method=matcher.match(r)
            if method:audit['matching'][method]+=1
            row=dict(zip(FIELDS,['',paper,r['key'],node,r['author'],r['year'],r['title'],r['doi'],f'{name} | {heading}',s]))
            old_id=next((candidate for candidate in
                (detailed_stable.get((identity(row),row['section'],work)),
                 scoped_stable.get((identity(row),row['section'])),stable.get(identity(row)))
                if candidate and candidate not in used_context_ids),None)
            if old_id:row['context_id']=old_id;reused+=1
            else:
                highest[paper]+=1
                row['context_id']=f'{paper}:x{highest[paper]:03d}'
            used_context_ids.add(row['context_id'])
            rows.append(row)
        audit['papers'][paper]={'contexts':count,'references':len(refs),'raw_blocks':len(blocks),'unmatched_blocks':unmatched,'unresolved_markers':unresolved}
    bytitle=collections.defaultdict(list)
    for row in rows:bytitle[norm(row['cited_title'])].append(row)
    for row in rows:
        peers=bytitle[norm(row['cited_title'])]
        for field in ('cited_first_author','cited_year','cited_doi'):
            if not row.get(field) or row[field]==NA:
                values={r[field] for r in peers if r.get(field) and r[field]!=NA}
                if len(values)==1:row[field]=values.pop()
    # Metadata completion can unify an identifier-free copy with a DOI-backed
    # copy. Retain the first stable row of that same citation context.
    unique=[];completed=set()
    for row in rows:
        work=versionless_doi(row['cited_doi']) or norm(row['cited_title'])
        key=(*identity(row),work)
        if key not in completed:unique.append(row);completed.add(key)
    rows=unique
    if len({r['context_id'] for r in rows})!=len(rows):raise ValueError('Context ID allocation collision')
    write(args.output_dir/'citation_contexts.tsv',FIELDS,rows)
    audit['reused_context_ids']=reused
    audit['contexts']=len(rows);audit['contexts_sha256']=hashlib.sha256((args.output_dir/'citation_contexts.tsv').read_bytes()).hexdigest()
    (args.scratch_dir/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'papers':len(papers),'contexts':len(rows),'per_paper':{p:d['contexts'] for p,d in audit['papers'].items()},'failed_substring_rows':audit['failed_substring_rows'],'unresolved':{p:len(d['unresolved_markers']) for p,d in audit['papers'].items() if d['unresolved_markers']},'unaligned':{p:len(d['unmatched_blocks']) for p,d in audit['papers'].items() if d['unmatched_blocks']}},sort_keys=True))


def frontier_identity(c):
    return doi(c.get('cited_doi', '')) or norm(c.get('cited_title', ''))


def cached_open_routes(cache):
    """Reuse retained OpenAlex locations without making a metadata request."""
    routes = {}
    priority = {'pmc': 0, 'arxiv': 1, 'biorxiv': 2, 'europepmc': 3}
    for path in sorted(Path(cache).glob('*.json')):
        record = json.loads(path.read_text())
        if not isinstance(record, dict) or record.get('status') != 200 or not record.get('url', '').startswith('https://api.openalex.org/works'):
            continue
        try:
            payload = json.loads(record['body'])
        except (ValueError, KeyError):
            continue
        items = payload.get('results', []) if 'results' in payload else [payload]
        for item in items:
            locations = json.dumps([item.get('locations', []), item.get('best_oa_location'), item.get('ids', {})]).lower()
            route = None
            if re.search(r'(?:pmc\d+|pmc/articles/|/articles/pmc)', locations):
                route = 'pmc'
            elif 'arxiv.org' in locations:
                route = 'arxiv'
            elif 'biorxiv.org' in locations:
                route = 'biorxiv'
            elif 'europepmc.org' in locations:
                route = 'europepmc'
            if not route:
                continue
            value = {'open_route': route, 'cache_file': path.name, 'work_id': item.get('id', '')}
            keys = [doi(item.get('doi', '')), norm(item.get('title', ''))]
            for key in keys:
                if key and (key not in routes or priority[route] < priority[routes[key]['open_route']]):
                    routes[key] = value
    return routes


def frontier_route(row, client, audit, cached_routes):
    """One Europe PMC lookup per ranked work; replay its exact cached response."""
    from citation_paths import EPMC
    from difflib import SequenceMatcher
    d = doi(row['cited_doi'])
    title = row['cited_title'] if row['cited_title'] != NA else ''
    query = ('DOI:"' + d.replace('"', '') + '"') if d else ('TITLE:"' + title.replace('"', '').replace('\\', ' ') + '"')
    data = client.get(EPMC + '/search', {'query': query, 'format': 'json', 'resultType': 'core', 'pageSize': 5})
    if data is None:
        raise RuntimeError('Frontier metadata lookup failed; retain its cached response for diagnosis: ' + query)
    candidates = data.get('resultList', {}).get('result', [])
    matched = []
    for item in candidates:
        same_doi = bool(d and doi(item.get('doi', '')) == d)
        same_title = bool((not d or not doi(item.get('doi', ''))) and title and
                          SequenceMatcher(None, norm(title), norm(item.get('title', ''))).ratio() >= .92)
        if same_doi or same_title:
            matched.append(item)
    route = 'none_found'
    if d.startswith('10.48550/arxiv.') or re.search(r'\barxiv\s*[:.]?\s*\d{4}\.\d{4,5}', title, re.I):
        route = 'arxiv'
    elif d.startswith('10.1101/'):
        route = 'biorxiv'
    for item in matched:
        urls = json.dumps(item.get('fullTextUrlList', {})).lower()
        if item.get('pmcid'):
            route = 'pmc'; break
        if 'arxiv.org' in urls:
            route = 'arxiv'
        elif 'biorxiv.org' in urls or doi(item.get('doi', '')).startswith('10.1101/'):
            route = 'biorxiv'
        elif item.get('isOpenAccess') == 'Y' and (item.get('inEPMC') == 'Y' or 'europepmc.org' in urls):
            route = 'europepmc'
    cached = cached_routes.get(d) if d else cached_routes.get(norm(title))
    if route == 'none_found' and cached:
        route = cached['open_route']
    audit.append({'service': 'Europe PMC', 'cached_repository_evidence': cached,
                  'identity': frontier_identity(row), 'query': query, 'matched_records': len(matched),
                  'lookup_available': data is not None, 'open_route': route})
    return route


def build_links(args):
    """Materialize explicit sentence readings and refresh the off-map frontier."""
    contexts = read(args.output_dir / 'citation_contexts.tsv')
    index = {r['context_id']: r for r in contexts}
    decisions = json.loads((args.scratch_dir / 'readings.json').read_text())
    rows = []
    decision_index = collections.defaultdict(list)
    seen = set()
    for d in decisions:
        c = index[d['context_id']]
        if d.get('source_sentence') != c['sentence'] or d.get('source_ref_key') != c['ref_key']:
            raise ValueError('Reading no longer matches extracted sentence/reference: ' + d['context_id'])
        r = {**{k: c[k] for k in ('context_id', 'citing_paper', 'cited_node_id')},
             'citing_method_id': d.get('citing_method_id', NA), 'cited_label': d['cited_label'],
             'relation': d['relation'], 'conditions': d.get('conditions', NA),
             'statement': d['statement'], 'tag': 'agent-read'}
        ident = tuple(r.get(k, NA) for k in LINK_FIELDS)
        if ident in seen:
            continue
        seen.add(ident)
        rows.append(r)
        decision_index[c['context_id']].append(d)
    order = {cid: i for i, cid in enumerate(index)}
    rows.sort(key=lambda r: (order[r['context_id']], r['citing_method_id'], r['relation']))
    missing = {c['context_id'] for c in contexts if c['cited_node_id'] != NA} - {r['context_id'] for r in rows}
    if missing:
        raise ValueError('On-map contexts without explicit readings: ' + ', '.join(sorted(missing)))
    write(args.output_dir / 'context_links.tsv', LINK_FIELDS, rows)

    parent = {}
    def root(key):
        parent.setdefault(key, key)
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key
    title_dois = collections.defaultdict(set)
    for c in contexts:
        if doi(c['cited_doi']) and c['cited_title'] != NA:
            title_dois[norm(c['cited_title'])].add(doi(c['cited_doi']))
    def identities(c):
        keys = []
        d = doi(c['cited_doi'])
        if d:
            keys.append(('doi', d))
        t = norm(c['cited_title'])
        # A short/malformed shared title must not merge conflicting explicit
        # DOIs. Bibliography aliases remain an explicit, reviewed decision.
        if c['cited_title'] != NA and t and (not d or len(title_dois[t]) <= 1):
            keys.append(('title', t))
        return keys or [('unknown', c['context_id'])]
    for c in contexts:
        keys = identities(c)
        for key in keys[1:]:
            parent[root(key)] = root(keys[0])
    # Explicitly reviewed bibliography aliases also unify short book titles
    # and their publisher-qualified or malformed retained variants.
    kind_path = args.scratch_dir / 'frontier_kind_readings.json'
    kind_records = json.loads(kind_path.read_text()) if kind_path.exists() else []
    for decision in kind_records:
        aliases = decision.get('identity_aliases', [])
        if not aliases:
            continue
        keys = [(('doi', doi(value)) if doi(value) else ('title', norm(value))) for value in aliases]
        for key in keys[1:]:
            parent[root(key)] = root(keys[0])
    # The same work can have bibliography title variants (for example, a
    # discussion suffix). Apply the matcher's author/year/title-word criterion
    # before counting works; conflicting explicit DOIs remain separate.
    bibliographies = {}
    by_author_year = collections.defaultdict(list)
    for c in contexts:
        year = re.search(r'\d{4}', c['cited_year'])
        title = norm(c['cited_title']) if c['cited_title'] != NA else ''
        author = {w for w in words(c['cited_first_author']) if len(w) > 2}
        if not (year and title and author):
            continue
        key = (doi(c['cited_doi']), title, tuple(sorted(author)), year[0])
        if key in bibliographies:
            continue
        bibliographies[key] = c
        for surname in sorted(author):
            for other in by_author_year[(surname, year[0])]:
                left, right = doi(c['cited_doi']), doi(other['cited_doi'])
                if left and right and left != right:
                    continue
                x, y = words(c['cited_title']), words(other['cited_title'])
                if len(x & y) >= 4 and len(x & y) / max(1, len(x | y)) >= .65:
                    parent[root(identities(c)[0])] = root(identities(other)[0])
            by_author_year[(surname, year[0])].append(c)
    mapped = {root(identities(c)[0]) for c in contexts if c['cited_node_id'] != NA}
    groups = collections.defaultdict(list)
    for r in rows:
        identity = root(identities(index[r['context_id']])[0])
        if r['cited_node_id'] == NA and r['relation'] in RELATIONS and identity not in mapped:
            groups[identity].append(r)
    kinds = {}
    for d in kind_records:
        for key in (doi(d.get('cited_doi', '')), norm(d.get('cited_title', ''))):
            if key:
                kinds[key] = d['kind']
    frontier = []
    untyped = []
    for group in groups.values():
        cs = [index[r['context_id']] for r in group]
        c = max(cs, key=lambda c: sum(c[k] != NA for k in ('cited_doi', 'cited_title', 'cited_year')))
        explicit = {d['frontier_kind'] for r in group for d in decision_index[r['context_id']] if d.get('frontier_kind')}
        recorded = {kinds[key] for x in cs for key in (doi(x['cited_doi']), norm(x['cited_title'])) if key in kinds}
        selected = explicit or recorded
        if len(selected) != 1:
            untyped.append({'identity': frontier_identity(c), 'context_ids': [r['context_id'] for r in group], 'kinds': sorted(selected)})
            continue
        kind = next(iter(selected))
        if kind not in {'method', 'data', 'software', 'review'}:
            raise ValueError('Invalid frontier kind: ' + kind)
        frontier.append({**{k: c[k] for k in FRONT_FIELDS[:4]},
                         'cited_label': '; '.join(sorted({r['cited_label'] for r in group})),
                         'n_relation_sentences': len({(r['citing_paper'], index[r['context_id']]['sentence']) for r in group}),
                         'citing_papers': '; '.join(sorted({r['citing_paper'] for r in group})),
                         'relations': '; '.join(sorted({r['relation'] for r in group})),
                         'kind': kind, 'open_route': NA})
    if untyped:
        (args.scratch_dir / 'untyped_frontier.json').write_text(json.dumps(untyped, indent=2, sort_keys=True) + '\n')
        raise ValueError('Frontier works need explicit kind readings: ' + str(len(untyped)))
    frontier.sort(key=lambda r: (-r['n_relation_sentences'], norm(r['cited_title']), r['cited_doi']))
    # Preserve the complete bibliography-equivalence group for sentence review.
    # These audit fields stay in the pending packet, outside the TSV schema.
    members = collections.defaultdict(list)
    for c in contexts:
        members[root(identities(c)[0])].append(c)
    for row in frontier:
        group = members[root(identities(row)[0])]
        row['_identity_aliases'] = sorted({value for c in group
            for _, value in identities(c) if value and value != norm(NA)})
        row['_context_ids'] = [c['context_id'] for c in group]
    (args.scratch_dir / 'frontier_pending.json').write_text(json.dumps(frontier, ensure_ascii=False, indent=2) + '\n')
    from citation_paths import Client
    client = Client(args.cache_dir, args.offline, retry_failed=True)
    cached_routes = cached_open_routes(args.cache_dir)
    route_audit = []
    for row in [r for r in frontier if r['kind'] == 'method'][:60]:
        row['open_route'] = frontier_route(row, client, route_audit, cached_routes)
    write(args.output_dir / 'frontier.tsv', FRONT_FIELDS, frontier)
    (args.scratch_dir / 'frontier_routes.json').write_text(json.dumps({'lookups': route_audit,
        'requests': dict(client.stats), 'failures': dict(client.failures)}, indent=2, sort_keys=True) + '\n')
    check(args)



def check(args):
    contexts=read(args.output_dir/'citation_contexts.tsv');index={r['context_id']:r for r in contexts};errors=[]
    if len(index)!=len(contexts):errors.append('Duplicate context IDs')
    sources={}
    allowed=Matcher().allowed
    for c in contexts:
        if c['cited_node_id']!=NA and c['cited_node_id'] not in allowed:
            errors.append(c['context_id']+': invalid cited node ID')

        name=c['section'].split(' | ')[0]
        if name not in sources:sources[name]=ws((ROOT/'sources'/name).read_text())
        if c['sentence'] not in sources[name]:errors.append(c['context_id']+': failed exact substring')
    counts={}
    if (args.output_dir/'context_links.tsv').exists():
        links=read(args.output_dir/'context_links.tsv');covered={r['context_id'] for r in links}
        missing={r['context_id'] for r in contexts if r['cited_node_id']!=NA}-covered
        if missing:errors.append('On-map contexts without readings: '+', '.join(sorted(missing)))
        method_rows=read(ROOT/'tables/methods.tsv');methods={r['method_id'] for r in method_rows};pairs={(r['method_id'],r['paper_id']) for r in method_rows};mapids={r['method_id'] for r in read(ROOT/'tables/map_layout.tsv')}
        for r in links:
            c=index.get(r['context_id'])
            if not c:errors.append(r['context_id']+': missing context');continue
            if r['citing_paper']!=c['citing_paper'] or r['cited_node_id']!=c['cited_node_id']:errors.append(r['context_id']+': mismatched identity')
            if r['relation'] not in RELATIONS|OTHER:errors.append(r['context_id']+': invalid relation')
            mid=r['citing_method_id'];base=mid.removesuffix('.component')
            if mid!=NA and base not in methods|mapids:errors.append(r['context_id']+': unknown citing method')
            if mid!=NA and (base,r['citing_paper']) not in pairs:errors.append(r['context_id']+': citing method belongs to another paper')
            if r['tag']!='agent-read':errors.append(r['context_id']+': missing agent-read')
            if len(r['statement'].split())>30:errors.append(r['context_id']+': statement over 30 words')
        counts=dict(collections.Counter(r['relation'] for r in links))
    result={'contexts':len(contexts),'exact_substring_failures':sum('substring' in s for s in errors),'link_rows_by_relation':counts,'errors':errors}
    (args.scratch_dir/'validation.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,sort_keys=True))
    if errors:raise SystemExit(1)


def main():
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--paper-ids',nargs='+');p.add_argument('--output-dir',type=Path,default=ROOT/'tables');p.add_argument('--scratch-dir',type=Path,default=ROOT/'tmp/refresh')
    m=p.add_mutually_exclusive_group();m.add_argument('--build-links',action='store_true');m.add_argument('--check',action='store_true')
    p.add_argument('--cache-dir',type=Path,default=ROOT/'sources/citations_cache');p.add_argument('--offline',action='store_true',help='Use cached frontier metadata only')
    args=p.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True);args.scratch_dir.mkdir(parents=True,exist_ok=True)
    if args.build_links:build_links(args)
    elif args.check:check(args)
    else:extract(args)

if __name__=='__main__':main()
