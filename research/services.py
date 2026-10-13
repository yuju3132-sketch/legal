import hashlib
import json
import re
from datetime import date
from research.db import connect, query
from research.paths import timestamp, now
from research.classifiers import classify
from research.deduplication import canonical_url, normalize_title, find_duplicate
from research.scoring import score

UNKNOWN = '확인되지 않음'
ANALYSIS_FIELDS = ['research_relevance','legal_significance','korean_law_relevance','comparative_law_relevance','banking_practice_relevance','seminar_relevance','paper_relevance','research_gap','facts','what_is_new','core_legal_issue','difference_from_existing','governance_implication','aml_implication','sanctions_implication']

def register(document, path=None, allow_test=False, related_to=None, relation_type='UPDATE'):
    doc = dict(document)
    if doc.get('is_test') and not allow_test:
        raise ValueError('TEST_DATA는 운영 DB에 등록할 수 없습니다')
    if not doc.get('title','').strip() or not doc.get('jurisdiction'):
        raise ValueError('제목과 관할국가가 필요합니다')
    doc['canonical_url'] = canonical_url(doc['source_url'])
    if doc.get('pdf_url'): canonical_url(doc['pdf_url'])
    doc['normalized_title'] = normalize_title(doc['title'])
    if doc.get('publication_date'):
        published = date.fromisoformat(doc['publication_date'])
        if published > now().date(): raise ValueError('미래 발행일은 확인 후 등록하십시오')
    if doc.get('doi'): doc['doi'] = re.sub(r'^https?://(?:dx\.)?doi.org/','',doc['doi'].strip(),flags=re.I).lower()
    topics = doc.pop('topics',None) or classify(' '.join(str(doc.get(k) or '') for k in ('title','summary','keywords')))
    doc['primary_topic'] = doc.get('primary_topic') or topics[0]
    doc['author_or_institution'] = doc.get('author') or doc.get('institution') or UNKNOWN
    total,priority,reason,parts = score(doc.pop('components',{}),doc.get('publication_date'),now().date(),doc.pop('score_evidence',{}))
    doc.update(importance_score=total,priority=priority,score_reason=reason,score_components=json.dumps(parts))
    doc.setdefault('source_type','Guidance'); doc.setdefault('source_tier',1)
    for key in ANALYSIS_FIELDS: doc.setdefault(key,UNKNOWN)
    content = {k:v for k,v in doc.items() if k not in ('last_checked','verified_at','score_reason','importance_score','score_components','priority')}
    doc['content_hash'] = hashlib.sha256(json.dumps(content,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    stamp = timestamp()
    with connect(path) as c:
        old = find_duplicate(c,doc)
        if old and old['content_hash'] == doc['content_hash']:
            c.execute('UPDATE documents SET last_checked=? WHERE id=?',(stamp,old['id']))
            return old['id'],'DUPLICATE'
        columns = {r['name'] for r in c.execute('PRAGMA table_info(documents)')}
        doc = {k:v for k,v in doc.items() if k in columns and k not in ('id','first_seen','created_at','updated_at')}
        doc.update(last_checked=stamp,updated_at=stamp,update_status='UPDATE' if old else 'NEW',duplicate_status='MATCHED' if old else 'NEW')
        if old:
            ident = old['id']
            c.execute('UPDATE documents SET '+','.join(k+'=?' for k in doc)+' WHERE id=?',(*doc.values(),ident))
            c.execute('DELETE FROM document_topics WHERE document_id=?',(ident,))
        else:
            doc.update(first_seen=stamp,created_at=stamp)
            ident = c.execute('INSERT INTO documents('+','.join(doc)+') VALUES('+','.join('?' for _ in doc)+')',tuple(doc.values())).lastrowid
        for topic in dict.fromkeys([doc['primary_topic'],*topics]):
            c.execute('INSERT OR IGNORE INTO topics(name) VALUES(?)',(topic,))
            c.execute('INSERT INTO document_topics VALUES(?,(SELECT id FROM topics WHERE name=?))',(ident,topic))
        for field,table,relation in [('author','authors','document_authors'),('institution','institutions','document_institutions')]:
            if doc.get(field):
                c.execute(f'INSERT OR IGNORE INTO {table}(name) VALUES(?)',(doc[field],))
                c.execute(f'INSERT OR IGNORE INTO {relation} VALUES(?,(SELECT id FROM {table} WHERE name=?))',(ident,doc[field]))
        if related_to:
            if related_to == ident: raise ValueError('자기 자신을 후속자료로 연결할 수 없습니다')
            c.execute('INSERT OR IGNORE INTO relationships(from_document,to_document,relation_type) VALUES(?,?,?)',(related_to,ident,relation_type))
        return ident,'UPDATE' if old else 'NEW'

def search(text='', filters=None, sort='Newest', path=None):
    filters = filters or {}
    where = ['d.is_test=0']; values=[]
    fields = ['title','author','institution','summary','legal_significance','keywords','case_number','document_number','research_gap']
    for word in text.split():
        needle = '%'+word.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
        where.append('('+' OR '.join(f"COALESCE(d.{k},'') LIKE ? ESCAPE '\\'" for k in fields)+" OR EXISTS(SELECT 1 FROM document_topics dt JOIN topics t ON t.id=dt.topic_id WHERE dt.document_id=d.id AND t.name LIKE ? ESCAPE '\\'))")
        values.extend([needle]*(len(fields)+1))
    for field in ('jurisdiction','source_type','priority','institution'):
        if filters.get(field): where.append(f'd.{field}=?'); values.append(filters[field])
    if filters.get('topic'):
        where.append('EXISTS(SELECT 1 FROM document_topics dt JOIN topics t ON t.id=dt.topic_id WHERE dt.document_id=d.id AND (t.name=? OR t.parent=?))'); values.extend([filters['topic']]*2)
    if filters.get('year'): where.append('substr(d.publication_date,1,4)=?'); values.append(str(filters['year']))
    if filters.get('min_score'): where.append('d.importance_score>=?'); values.append(filters['min_score'])
    if filters.get('pdf'): where.append("(COALESCE(d.local_pdf_path,'')<>'' OR COALESCE(d.pdf_url,'')<>'')")
    if filters.get('since'): where.append('substr(d.first_seen,1,10)>=?'); values.append(filters['since'])
    order = {'Newest':'publication_date DESC','Highest Score':'importance_score DESC','Recently Added':'first_seen DESC'}[sort]
    return query('SELECT d.* FROM documents d WHERE '+' AND '.join(where)+' ORDER BY '+order+',id DESC',values,path)

def create_idea(data, document_ids, path=None):
    if len(set(document_ids)) < 2: raise ValueError('연구주제는 서로 다른 검증자료 2건 이상이 필요합니다')
    with connect(path) as c:
        for ident in document_ids:
            row=c.execute('SELECT verification_status,is_test FROM documents WHERE id=?',(ident,)).fetchone()
            if not row or row['verification_status']!='VERIFIED' or row['is_test']: raise ValueError('검증된 실제 자료만 근거로 사용할 수 있습니다')
        columns=['title','problem','legal_issue','jurisdictions','existing_research','research_gap','korean_connection','comparative_potential','paper_fit','seminar_fit']
        if not data.get('title') or not data.get('research_gap'): raise ValueError('제목과 Research Gap이 필요합니다')
        ident=c.execute('INSERT INTO research_ideas('+','.join(columns)+',created_at) VALUES('+','.join('?' for _ in range(11))+')',tuple(data.get(k,UNKNOWN) for k in columns)+(timestamp(),)).lastrowid
        c.executemany('INSERT INTO idea_documents VALUES(?,?)',[(ident,d) for d in set(document_ids)])
        return ident

def search_reports(text,path=None):
    if not text.strip(): return []
    clauses=[]; params=[]
    for word in text.split():
        clauses.append("content LIKE ? ESCAPE '\\'")
        params.append('%'+word.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%')
    return query('SELECT * FROM reports WHERE '+' AND '.join(clauses)+' ORDER BY period DESC',params,path)
