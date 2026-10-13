import hashlib
import re
from io import BytesIO
from pathlib import Path
from pypdf import PdfReader
from research.paths import DATA
from research.collectors import PublicClient, CollectionError

def metadata(body):
    if not body.startswith(b'%PDF-'): raise ValueError('유효한 PDF 헤더가 아닙니다')
    reader=PdfReader(BytesIO(body))
    if reader.is_encrypted: raise ValueError('암호화 PDF는 처리하지 않습니다')
    info=reader.metadata or {}
    return {'pages':len(reader.pages),'title':info.get('/Title'),'author':info.get('/Author'),'hash':hashlib.sha256(body).hexdigest()}

def archive(document,client=None,data_dir=None):
    body,_,_= (client or PublicClient()).get(document['pdf_url'],25_000_000)
    info=metadata(body)
    safe=lambda s: re.sub(r'[^\w-]+','-',str(s),flags=re.UNICODE).strip('-')[:65] or 'Unknown'
    year=(document.get('publication_date') or 'Unknown')[:4]
    country={'United States':'US','United Kingdom':'UK'}.get(document['jurisdiction'],document['jurisdiction'])
    name='_'.join(safe(s) for s in [year,country,document.get('institution') or 'Unknown',document['title']])+'_'+info['hash'][:12]+'.pdf'
    dest=Path(data_dir or DATA)/'papers'/country/name
    dest.parent.mkdir(parents=True,exist_ok=True); dest.write_bytes(body)
    return str(dest.relative_to(Path(data_dir or DATA))),info
