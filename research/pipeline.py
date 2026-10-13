import logging
from research.db import connect,query,initialize
from research.paths import DATA,timestamp
from research.collectors import PublicClient,CollectionError,parse_feed,verify_document
from research.services import register
from research.classifiers import classify
from research.reporting import daily,weekly
from research.pdf import archive
from research.deduplication import canonical_url,normalize_title

def log_error(run,source,category,message,path=None):
    (DATA/'logs').mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=DATA/'logs/research.log',level=logging.INFO,encoding='utf-8')
    with connect(path) as c:
        c.execute('INSERT INTO errors(run_id,source_id,category,message,created_at) VALUES(?,?,?,?,?)',(run,source,category,str(message)[:2000],timestamp()))
    logging.warning('%s [%s]: %s',source,category,message)

def collect(limit=10,path=None,download_pdfs=False):
    initialize(path)
    (DATA/'logs').mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=DATA/'logs/research.log',level=logging.INFO,encoding='utf-8')
    with connect(path) as c:
        run=c.execute('INSERT INTO collection_runs(kind,started_at,status) VALUES(?,?,?)',('daily',timestamp(),'RUNNING')).lastrowid
    counts={'discovered':0,'inserted':0,'updated':0,'duplicates':0,'error_count':0}
    client=PublicClient()
    sources=query('SELECT * FROM sources WHERE enabled=1 AND feed_url IS NOT NULL',path=path)
    for source in sources:
        try:
            body,_,_=client.get(source['feed_url'])
            rows=parse_feed(body)[:limit]
            if not rows: raise CollectionError('parsing','피드 항목 0건; 피드 확인 필요')
            with connect(path) as c: c.execute("UPDATE sources SET verification_status='VERIFIED',last_checked=? WHERE id=?",(timestamp(),source['id']))
            for row in rows:
                counts['discovered']+=1
                try:
                    if classify(row['title']+' '+row['feed_summary'])==['Unclassified']: continue
                    doc=verify_document(row,source,client); doc['verified_at']=timestamp()
                    previous=query('SELECT * FROM documents WHERE canonical_url=?',(canonical_url(doc['source_url']),),path)
                    if previous:
                        old=previous[0]; ident=old['id']
                        if old['document_hash']==doc['document_hash']:
                            with connect(path) as c: c.execute('UPDATE documents SET last_checked=? WHERE id=?',(timestamp(),ident))
                            status='DUPLICATE'
                        else:
                            # Preserve researcher's legal analysis, tags, scores and identifiers.
                            # Changed source requires manual review before it re-enters reports.
                            updates={k:doc[k] for k in ('title','publication_date','pdf_url','document_hash','evidence')}
                            updates['normalized_title']=normalize_title(doc['title'])
                            updates.update(last_checked=timestamp(),updated_at=timestamp(),verification_status='REVIEW_REQUIRED',update_status='UPDATE',content_hash=doc['document_hash'])
                            with connect(path) as c: c.execute('UPDATE documents SET '+','.join(k+'=?' for k in updates)+' WHERE id=?',(*updates.values(),ident))
                            status='UPDATE'
                    else: ident,status=register(doc,path)
                    counts[{'NEW':'inserted','UPDATE':'updated','DUPLICATE':'duplicates'}[status]]+=1
                    if download_pdfs and doc.get('pdf_url'):
                        try:
                            local,info=archive(doc,client)
                            with connect(path) as c: c.execute('UPDATE documents SET local_pdf_path=? WHERE id=?',(local,ident))
                        except Exception as exc:
                            counts['error_count']+=1; log_error(run,source['id'],'pdf',str(exc),path)
                except Exception as exc:
                    counts['error_count']+=1; log_error(run,source['id'],getattr(exc,'category','parsing'),str(exc),path)
        except Exception as exc:
            counts['error_count']+=1; log_error(run,source['id'],getattr(exc,'category','network'),str(exc),path)
            with connect(path) as c: c.execute("UPDATE sources SET verification_status='FAILED',last_checked=? WHERE id=?",(timestamp(),source['id']))
    status='NO_SOURCES' if not sources else 'PARTIAL' if counts['error_count'] else 'COMPLETED'
    with connect(path) as c:
        c.execute('UPDATE collection_runs SET finished_at=?,status=?,'+','.join(k+'=?' for k in counts)+' WHERE id=?',(timestamp(),status,*counts.values(),run))
    return dict(status=status,run_id=run,**counts)
