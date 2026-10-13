import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

def normalize_title(title):
    return re.sub(r'[^\w]+',' ',unicodedata.normalize('NFKC',title).casefold()).strip()

def canonical_url(url):
    u = urlsplit(url)
    if u.scheme not in ('http','https') or not u.hostname or u.username or u.password:
        raise ValueError('공개 HTTP(S) URL만 사용할 수 있습니다')
    query = [(k,v) for k,v in parse_qsl(u.query,keep_blank_values=True) if not k.lower().startswith('utm_') and k.lower() not in ('fbclid','gclid')]
    return urlunsplit((u.scheme,u.netloc.lower(),u.path.rstrip('/') or '/',urlencode(sorted(query)),''))

def find_duplicate(c,doc):
    for column in ('canonical_url','doi','document_hash'):
        if doc.get(column):
            row = c.execute(f'SELECT * FROM documents WHERE {column}=?',(doc[column],)).fetchone()
            if row: return dict(row)
    for column in ('case_number','document_number'):
        if doc.get(column):
            row = c.execute(f'SELECT * FROM documents WHERE {column}=? AND jurisdiction=? AND institution=?',(doc[column],doc['jurisdiction'],doc.get('institution'))).fetchone()
            if row: return dict(row)
    row = c.execute('SELECT * FROM documents WHERE normalized_title=? AND jurisdiction=? AND COALESCE(author_or_institution,\'\')=? AND COALESCE(publication_date,\'\')=?',(doc['normalized_title'],doc['jurisdiction'],doc.get('author_or_institution') or '',doc.get('publication_date') or '')).fetchone()
    return dict(row) if row else None
