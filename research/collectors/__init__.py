"""Public RSS/Atom + metadata. Never synthesize missing legal analysis."""
import hashlib
import ipaddress
import socket
import time
import re
from difflib import SequenceMatcher
import xml.etree.ElementTree as ET
from datetime import datetime, date
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urljoin
from urllib.robotparser import RobotFileParser
from urllib.request import getproxies
import requests
from bs4 import BeautifulSoup
from research.deduplication import canonical_url

USER_AGENT = 'GlobalLegalResearch/1.0 (personal academic research; respects robots.txt)'

class CollectionError(Exception):
    def __init__(self,category,message):
        super().__init__(message); self.category=category

def public_url(url):
    canonical_url(url)
    host=urlsplit(url).hostname
    if host.lower() in ('localhost','localhost.localdomain') or host.lower().endswith(('.localhost','.local','.internal')):
        raise CollectionError('invalid_url','로컬 호스트는 수집하지 않습니다')
    try:
        literal=ipaddress.ip_address(host)
        if not literal.is_global: raise CollectionError('invalid_url','사설 IP는 수집하지 않습니다')
    except ValueError: pass
    try:
        addresses=socket.getaddrinfo(host,None)
    except socket.gaierror as exc:
        # Cloud egress resolves official hostnames at the HTTPS proxy.
        # Keep literal/private hosts blocked without requiring local DNS.
        if getproxies().get(urlsplit(url).scheme): return url
        raise CollectionError('network',f'DNS: {host}') from exc
    if not addresses or any(not ipaddress.ip_address(r[4][0]).is_global for r in addresses):
        raise CollectionError('invalid_url','로컬/사설 주소는 수집하지 않습니다')
    return url

class PublicClient:
    def __init__(self):
        self.session=requests.Session(); self.session.headers['User-Agent']=USER_AGENT
        self.robots={}; self.last={}

    def raw(self,url,limit=5_000_000):
        for _ in range(6):
            public_url(url)
            try:
                response=self.session.get(url,timeout=(10,30),allow_redirects=False,stream=True)
                if response.status_code in (301,302,303,307,308):
                    target=urljoin(url,response.headers.get('Location','')); response.close()
                    if not response.headers.get('Location'): raise CollectionError('parsing','리디렉션 주소 없음')
                    # Policy must also allow every redirect destination/path.
                    if urlsplit(target).path!='/robots.txt': self.allowed(target)
                    url=target; continue
                if response.status_code>=400:
                    status=response.status_code; response.close()
                    raise CollectionError(str(status),f'HTTP {status}: {url}')
                chunks=[]; length=0
                for chunk in response.iter_content(65536):
                    length+=len(chunk)
                    if length>limit: raise CollectionError('size','다운로드 크기 제한 초과')
                    chunks.append(chunk)
                response.close(); return b''.join(chunks),response.headers,url
            except requests.Timeout as exc: raise CollectionError('timeout',url) from exc
            except requests.RequestException as exc:
                category='network_policy' if 'Tunnel connection failed: 403' in str(exc) else 'network'
                raise CollectionError(category,f'{type(exc).__name__}: {url}') from exc
        raise CollectionError('network','리디렉션 한도 초과')

    def allowed(self,url):
        public_url(url)
        u=urlsplit(url); base=f'{u.scheme}://{u.netloc}'
        if base not in self.robots:
            try:
                body,_,_=self.raw(base+'/robots.txt',500_000)
                rp=RobotFileParser(); rp.parse(body.decode('utf-8','replace').splitlines())
            except CollectionError as exc:
                if exc.category=='404': rp=RobotFileParser(); rp.parse([])
                else: raise CollectionError(exc.category,f'robots.txt 확인 실패 [{exc.category}]: {base}') from exc
            self.robots[base]=rp
        rp=self.robots[base]
        if not rp.can_fetch(USER_AGENT,url): raise CollectionError('robots',f'수집 금지: {url}')
        delay=max(1,rp.crawl_delay(USER_AGENT) or rp.crawl_delay('*') or 0)
        remaining=delay-(time.monotonic()-self.last.get(base,0))
        if remaining>60: raise CollectionError('robots','crawl-delay가 60초를 초과합니다; 수동 조회하십시오')
        if remaining>0: time.sleep(remaining)
        self.last[base]=time.monotonic()

    def get(self,url,limit=5_000_000):
        self.allowed(url)
        return self.raw(url,limit)

def parse_date(value):
    if not value: return None
    try: return parsedate_to_datetime(value).date().isoformat()
    except (ValueError,TypeError):
        try: return datetime.fromisoformat(value.strip().replace('Z','+00:00')).date().isoformat()
        except ValueError:
            try: return date.fromisoformat(value.strip()).isoformat()
            except ValueError: return None

def parse_feed(body):
    try: root=ET.fromstring(body)
    except ET.ParseError as exc: raise CollectionError('parsing','RSS/Atom XML 아님') from exc
    rows=[]
    for node in root.iter():
        if node.tag.split('}')[-1] not in ('item','entry'): continue
        values={child.tag.split('}')[-1]:child for child in node}
        def text(key):
            n=values.get(key); return ''.join(n.itertext()).strip() if n is not None else ''
        links=[n for n in node if n.tag.split('}')[-1]=='link']
        link=next((n.get('href') for n in links if n.get('href') and n.get('rel','alternate')=='alternate'),text('link'))
        if not text('title') or not link: continue
        rows.append({'title':BeautifulSoup(text('title'),'html.parser').get_text(' ',strip=True),'source_url':link,'publication_date':parse_date(text('pubDate') or text('published') or text('updated')),'feed_summary':BeautifulSoup(text('description') or text('summary'),'html.parser').get_text(' ',strip=True)})
    return rows

def verify_document(row,source,client):
    host=urlsplit(row['source_url']).hostname
    official=urlsplit(source['homepage']).hostname.removeprefix('www.')
    if host.removeprefix('www.')!=official and not host.endswith('.'+official):
        raise CollectionError('verification','출처 도메인과 원문 도메인이 다릅니다')
    body,headers,final=client.get(row['source_url'])
    final_host=urlsplit(final).hostname.removeprefix('www.')
    if final_host!=official and not final_host.endswith('.'+official): raise CollectionError('verification','원문이 다른 기관으로 이동했습니다')
    if 'html' not in headers.get('Content-Type','').lower(): raise CollectionError('parsing','HTML 원문이 아닙니다')
    soup=BeautifulSoup(body,'html.parser')
    heading=soup.find('h1') or soup.title
    title=heading.get_text(' ',strip=True) if heading else ''
    if not title: raise CollectionError('parsing','원문 제목 없음')
    normalize=lambda s: re.sub(r'[^\w]+',' ',s.casefold()).strip()
    feed_title,page_title=normalize(row['title']),normalize(title)
    if feed_title not in page_title and page_title not in feed_title and SequenceMatcher(None,feed_title,page_title).ratio()<0.6:
        raise CollectionError('verification','피드/원문 제목 불일치; 수동 확인 필요')
    page_date=None
    for meta in soup.find_all('meta'):
        if meta.get('name',meta.get('property','')).lower() in ('citation_publication_date','article:published_time','dc.date','dcterms.date'):
            page_date=parse_date(meta.get('content')); break
    if page_date and row.get('publication_date') and page_date!=row['publication_date']:
        raise CollectionError('verification','피드/원문 발행일 불일치; 수동 확인 필요')
    published=page_date or row.get('publication_date')
    if published and date.fromisoformat(published)>date.today(): raise CollectionError('verification','미래 날짜')
    description=soup.find('meta',attrs={'name':'description'})
    summary=description.get('content','') if description else row.get('feed_summary','')
    pdf=next((urljoin(final,a['href']) for a in soup.find_all('a',href=True) if urlsplit(a['href']).path.lower().endswith('.pdf')),None)
    # A general news feed does not establish Case/Guidance/Enforcement type.
    return {'title':row['title'],'jurisdiction':source['jurisdiction'],'institution':source['name'],'publication_date':published,'source_id':source['id'],'source_type':source.get('document_type') or 'Unclassified','source_tier':source['tier'],'source_url':final,'pdf_url':pdf,'summary':summary or '확인되지 않음','verification_status':'VERIFIED','evidence':f'공식 피드 제목·날짜 + 원문 HTTP 200; 원문 제목: {title}; 발행일 근거: '+('원문 metadata' if page_date else '공식 피드' if published else '확인되지 않음'),'document_hash':hashlib.sha256(body).hexdigest()}
