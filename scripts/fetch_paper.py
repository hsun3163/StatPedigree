#!/usr/bin/env python3
"""Fetch one paper through public repositories; run from the project root."""
import argparse
import html
import io
import json
import re
import subprocess
import shutil
import time
import unicodedata
import zipfile
from html.parser import HTMLParser
from pathlib import Path
import xml.etree.ElementTree as ET
import requests

ROOT = Path(__file__).resolve().parents[1]
API = 'https://www.ebi.ac.uk/europepmc/webservices/rest/'
class PublicSession(requests.Session):
    def rebuild_auth(self, prepared_request, response):
        # Redirected public requests also bypass personal netrc credentials.
        prepared_request.headers.pop('Authorization', None)


SESSION = PublicSession()
# Public endpoints need no account credentials. Keep environment proxy support.
SESSION.auth = lambda request: request
SESSION.headers['User-Agent'] = 'stattree-methods-source-fetch/1.0'


def get(url, **kwargs):
    """Retry transient repository failures and retain a compact request trail."""
    (ROOT / 'tmp').mkdir(exist_ok=True)
    for attempt in range(3):
        try:
            r = SESSION.get(url, timeout=60, **kwargs)
            with (ROOT / 'tmp/fetch_events.jsonl').open('a') as f:
                f.write(json.dumps(dict(url=r.url, status=r.status_code,
                                       bytes=len(r.content), attempt=attempt + 1)) + '\n')
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            with (ROOT / 'tmp/fetch_events.jsonl').open('a') as f:
                f.write(json.dumps(dict(url=url, error=str(e), attempt=attempt + 1)) + '\n')
            if attempt == 2 or (getattr(e, 'response', None) is not None
                                and e.response.status_code < 500
                                and e.response.status_code != 429):
                raise
            time.sleep(2 * (attempt + 1))


def clean(text):
    return unicodedata.normalize('NFC', re.sub(r'\s+', ' ', html.unescape(text))).strip()


def tag(node):
    return node.tag.rsplit('}', 1)[-1]


def inline(node):
    name = tag(node)
    if name in ('tex-math', 'annotation'):
        return clean(''.join(node.itertext()))
    if name in ('inline-formula', 'disp-formula', 'alternatives'):
        tex = next((n for n in node.iter() if tag(n) == 'tex-math'), None)
        math = next((n for n in node.iter() if tag(n) == 'math'), None)
        chosen = tex if tex is not None else math
        value = inline(chosen) if chosen is not None else ''.join(node.itertext())
        label = next((clean(''.join(n.itertext())) for n in node if tag(n) == 'label'), '')
        return clean(value + (' ' + label if label and label not in value else ''))
    if name == 'math':
        tex = next((n for n in node.iter() if tag(n) == 'annotation'
                    and 'tex' in n.attrib.get('encoding', '').lower()), None)
        if tex is not None:
            return inline(tex)
        return clean(' '.join(inline(n) for n in node))
    children = [inline(n) for n in node]
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
    for child in node:
        value += inline(child) + (child.tail or '')
    return clean(value)


def xml_text(raw):
    root = ET.fromstring(raw)
    if tag(root) != 'article':
        article = root.find('.//article')
        if article is not None:
            root = article
    lines = []
    title = root.find('.//article-title')
    if title is not None:
        lines.append(inline(title))

    def walk(node):
        name = tag(node)
        if name in ('ref-list', 'supplementary-material'):
            return
        if name == 'title':
            title = inline(node)
            if title.lower() not in ('abstract', 'references'):
                lines.append('## ' + title)
        elif name == 'sec':
            for child in node:
                walk(child)
        elif name in ('p', 'disp-formula', 'table-wrap', 'fig', 'list-item'):
            value = inline(node)
            if value:
                lines.append(value)
        else:
            for child in node:
                walk(child)

    for abstract in root.findall('.//article-meta/abstract'):
        lines.append('## ' + ('Abstract' if not any(l == '## Abstract' for l in lines) else 'Editorial summary'))
        walk(abstract)
    body = root.find('body')
    if body is not None:
        walk(body)
    # Some author manuscripts keep appendices in back rather than body.
    back = root.find('back')
    if back is not None:
        walk(back)
    refs = root.findall('.//ref-list/ref')
    if refs:
        lines.append('## References')
        lines.extend(inline(ref) for ref in refs)
    return '\n'.join(lines) + '\n'


class TextHTML(HTMLParser):
    """Small HTML-to-paragraph converter for repository full-text pages."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines, self.buf, self.skip = [], [], 0
        self.heading = False
    def flush(self):
        text = clean(''.join(self.buf))
        if text:
            self.lines.append(('## ' if self.heading else '') + text)
        self.buf = []
    def handle_starttag(self, name, attrs):
        attrs = dict(attrs)
        if name in ('script', 'style', 'nav'):
            self.skip += 1
        if self.skip:
            return
        if name in ('p', 'h1', 'h2', 'h3', 'h4', 'li', 'div'):
            self.flush()
            self.heading = name in ('h1', 'h2', 'h3', 'h4')
        if name == 'img' and attrs.get('alt'):
            self.buf.append(' ' + attrs['alt'] + ' ')
        if name == 'math' and attrs.get('alttext'):
            self.buf.append(' ' + attrs['alttext'] + ' ')
    def handle_endtag(self, name):
        if name in ('script', 'style', 'nav') and self.skip:
            self.skip -= 1
            return
        if not self.skip and name in ('p', 'h1', 'h2', 'h3', 'h4', 'li', 'div'):
            self.flush()
            self.heading = False
    def handle_data(self, data):
        if not self.skip:
            self.buf.append(data)
    def text(self, raw):
        self.feed(raw)
        self.flush()
        return '\n'.join(self.lines) + '\n'


def supplement(paper, pmcid):
    """Only the Europe PMC OA package may supply supplementary files."""
    url = API + pmcid + '/supplementaryFiles'
    try:
        r = get(url)
    except requests.HTTPError as error:
        if error.response.status_code in (400, 403, 404):
            print('SUPPLEMENT unavailable in Europe PMC OA package:', error)
            return
        raise
    if not zipfile.is_zipfile(io.BytesIO(r.content)):
        (ROOT / 'tmp' / (paper + '_supplement_response.xml')).write_bytes(r.content)
        error = ET.fromstring(r.content).find('.//errMsg')
        if error is not None:
            print('SUPPLEMENT unavailable in Europe PMC OA package:', error.text)
            return
        raise ValueError('Supplement endpoint returned a non-ZIP response: ' + r.text[:300])
    archive = ROOT / 'sources' / (paper + '.supp.raw.zip')
    archive.write_bytes(r.content)
    chunks = []
    with zipfile.ZipFile(io.BytesIO(r.content)) as package:
        for member in package.infolist():
            if member.is_dir():
                continue
            name = member.filename
            ext = Path(name).suffix.lower()
            # Ignore package image assets; retain source archive unchanged.
            if ext not in ('.xml', '.nxml', '.html', '.htm', '.txt', '.tex', '.pdf'):
                continue
            data = package.read(member)
            if ext in ('.xml', '.nxml'):
                text = xml_text(data)
            elif ext in ('.html', '.htm'):
                text = TextHTML().text(data.decode('utf-8', errors='replace'))
            elif ext == '.pdf':
                if not shutil.which('pdftotext'):
                    raise RuntimeError('PDF supplement requires pdftotext; on Minerva: module load poppler/22.07.0')
                proc = subprocess.run(['pdftotext', '-layout', '-', '-'], input=data,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if proc.returncode:
                    raise RuntimeError('pdftotext: ' + proc.stderr.decode('utf-8', errors='replace').strip())
                # PDF paragraph boundaries are blank lines; equations retain their labels.
                # Isolate standalone section labels before joining wrapped PDF paragraphs.
                pdf = proc.stdout.decode('utf-8')
                heading = re.compile(r'^(?:Supplementary text|Background on wavelet regression|Supplementary references|References|(?:[A-Z]?\d+(?:\.\d+)*\.? )?(?:Methods|Discussion|Introduction|Appendix)(?: [A-Z])?)$', re.I)
                prepared = []
                for line in pdf.splitlines():
                    line = line.strip()
                    if heading.fullmatch(line):
                        prepared.extend(['', '## References' if 'references' in line.lower() else '## ' + line, ''])
                    else:
                        prepared.append(line)
                paragraphs = [clean(p) for p in re.split(r'\n\s*\n', '\n'.join(prepared)) if clean(p)]
                text = '\n'.join(paragraphs)
                # A supplement may place figures after its bibliography. Keep references last.
                if '## References\n' in text:
                    before, tail = text.split('## References\n', 1)
                    ref = re.match(r'(.*?)(?=\n(?:Supplementary (?:Figure|Table)|## )|\Z)', tail, re.S)
                    if ref:
                        refs = re.split(r'(?=\[\d+\])', ref.group(1))
                        text = before + tail[ref.end():] + '\n## References\n' + '\n'.join(clean(x) for x in refs if clean(x))

            else:
                text = '\n'.join(clean(p) for p in re.split(r'\n\s*\n', data.decode('utf-8')) if clean(p))
            chunks.append('## Supplement: ' + name + '\n' + text)
    if chunks:
        (ROOT / 'sources' / (paper + '.supp.txt')).write_text(
            unicodedata.normalize('NFC', '\n'.join(chunks)) + '\n', encoding='utf-8')
    print('SUPPLEMENT', len(chunks), 'text documents; archive', len(r.content), 'bytes')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paper_id', help='Local paper identifier (letters, digits, underscore, hyphen)')
    route = parser.add_mutually_exclusive_group(required=True)
    route.add_argument('--pmcid', metavar='PMCxxxx')
    route.add_argument('--arxiv', metavar='ID[vN]')
    route.add_argument('--biorxiv', metavar='DOI[vN]', help='bioRxiv or medRxiv DOI with optional vN')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.paper_id):
        parser.error('paper_id must be a simple local identifier')
    out = ROOT / 'sources'
    out.mkdir(exist_ok=True)
    if args.pmcid:
        if not re.fullmatch(r'PMC[0-9]+', args.pmcid):
            parser.error('PMCID must have the form PMC123456')
        metadata_response = get(API + 'search', params=dict(query='PMCID:' + args.pmcid,
                                format='json', resultType='core'))
        metadata = metadata_response.json()['resultList']['result']
        if not metadata:
            raise ValueError('No Europe PMC record for ' + args.pmcid)
        record = metadata[0]
        try:
            url = (API + args.pmcid + '/fullTextXML' if record.get('isOpenAccess') == 'Y'
                   else 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi')
            params = {} if record.get('isOpenAccess') == 'Y' else dict(db='pmc', id=args.pmcid[3:])
            r = get(url, params=params)
            raw, ext = r.content, 'xml'
            text = xml_text(raw)
        except requests.HTTPError as error:
            if error.response.status_code != 404:
                raise
            # Abstract-only is explicit when the repository has no open full-text route.
            raw, ext = metadata_response.content, 'json'
            abstract = record.get('abstractText', '')
            text = clean(record['title']) + '\n## Abstract\n' + TextHTML().text(abstract)
            print('ABSTRACT ONLY:', args.pmcid)
        (out / (args.paper_id + '.raw.' + ext)).write_bytes(raw)
        (out / (args.paper_id + '.txt')).write_text(text, encoding='utf-8')
        if ext == 'xml':
            supplement(args.paper_id, args.pmcid)
    elif args.arxiv:
        ident = args.arxiv
        if not re.fullmatch(r'(?:[0-9]{4}\.[0-9]{4,5}|[a-z-]+(?:\.[A-Z]{2})?/[0-9]{7})(?:v[0-9]+)?', ident):
            parser.error('Invalid arXiv identifier')
        # HTML preserves equations and structure without requiring PDF extraction.
        r = get('https://export.arxiv.org/html/' + ident)
        (out / (args.paper_id + '.raw.html')).write_bytes(r.content)
        (out / (args.paper_id + '.txt')).write_text(TextHTML().text(r.text), encoding='utf-8')
    else:
        match = re.fullmatch(r'(10\.1101/[0-9.]+)(?:v([0-9]+))?', args.biorxiv)
        if not match:
            parser.error('Expected a bioRxiv/medRxiv 10.1101 DOI and optional vN')
        doi, version = match.groups()
        data = get('https://api.biorxiv.org/details/biorxiv/' + doi).json()
        server = 'biorxiv'
        if not data.get('collection'):
            server = 'medrxiv'
            data = get('https://api.biorxiv.org/details/medrxiv/' + doi).json()
        versions = data.get('collection', [])
        if version:
            versions = [x for x in versions if str(x['version']) == version]
        if not versions:
            raise ValueError('Preprint DOI/version not found: ' + args.biorxiv)
        record = max(versions, key=lambda x: int(x['version']))
        url = 'https://www.' + server + '.org/content/' + doi + 'v' + str(record['version']) + '.full'
        r = get(url)
        (out / (args.paper_id + '.raw.html')).write_bytes(r.content)
        (out / (args.paper_id + '.txt')).write_text(TextHTML().text(r.text), encoding='utf-8')
    print(args.paper_id, (out / (args.paper_id + '.txt')).stat().st_size, 'text bytes')


if __name__ == '__main__':
    main()
