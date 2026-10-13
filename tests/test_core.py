import json
from io import BytesIO
from datetime import timedelta
import pytest
from pypdf import PdfWriter
from research.db import query,initialize,connect
from research.services import register,search,create_idea,search_reports
from research.scoring import score
from research.reporting import daily,weekly,EMPTY,SECTIONS
from research.collectors import parse_feed,parse_date,PublicClient,CollectionError,public_url,verify_document
from research.pdf import metadata,archive
from research.pipeline import collect
from research.paths import now

def test_db_repeatable(db):
    initialize(db)
    assert len(query('SELECT * FROM schema_migrations',path=db))==1
    assert len(query('SELECT * FROM sources',path=db))>=60

def test_insert_and_cross_tag(db,doc):
    ident,status=register(doc,db)
    assert status=='NEW'
    tags={r['name'] for r in query('SELECT t.name FROM topics t JOIN document_topics d ON d.topic_id=t.id WHERE d.document_id=?',(ident,),db)}
    assert {'AML / KYC','Internal Control','Corporate Law'}<=tags
    assert query('SELECT * FROM documents',path=db)[0]['importance_score']==100

def test_url_duplicate_and_update(db,doc):
    ident,_=register(doc,db)
    assert register(doc,db)==(ident,'DUPLICATE')
    changed=dict(doc,summary='TEST_DATA changed verified content')
    assert register(changed,db)==(ident,'UPDATE')
    assert len(query('SELECT * FROM documents',path=db))==1

@pytest.mark.parametrize('field,value',[('doi','10.0000/TEST_DATA'),('case_number','TEST_DATA CASE 1'),('document_number','TEST_DATA DOC 1'),('document_hash','TEST_DATA_HASH')])
def test_identity_duplicate(db,doc,field,value):
    ident,_=register(dict(doc,**{field:value}),db)
    incoming=dict(doc,source_url='https://example.com/TEST_DATA/two',**{field:value})
    assert register(incoming,db)[0]==ident

def test_url_normalization(db,doc):
    ident,_=register(dict(doc,source_url='https://example.com/TEST_DATA/one?utm_source=abc'),db)
    assert register(doc,db)[0]==ident

def test_related_update(db,doc):
    ident,_=register(doc,db)
    second,_=register(dict(doc,title='TEST_DATA final decision',source_url='https://example.com/final'),db,related_to=ident,relation_type='FINAL_DECISION')
    assert query('SELECT * FROM relationships',path=db)[0]['to_document']==second

def test_scoring():
    assert score({'A':25},now().date().isoformat(),evidence={'A':'TEST_DATA'})[0]==35
    assert score({},None)[0]==0
    with pytest.raises(ValueError): score({'A':26})
    with pytest.raises(ValueError): score({'B':10})

@pytest.mark.parametrize('total,priority',[(85,'A'),(84,'B'),(70,'B'),(69,'C'),(50,'C'),(49,'D')])
def test_priority_boundaries(total,priority):
    remaining=total; points={}
    for key,cap in [('A',25),('B',20),('C',15),('D',15),('E',15)]:
        points[key]=min(cap,remaining); remaining-=points[key]
    assert score(points,None,evidence={k:'TEST_DATA' for k in points})[1]==priority

def test_search_and_filters(db,doc):
    register(dict(doc,case_number='TEST_DATA_123',keywords='경영진 책임'),db)
    assert len(search('AML 경영진',path=db))==1
    assert len(search('TEST_DATA_123',path=db))==1
    assert not search(filters={'jurisdiction':'Japan'},path=db)
    assert search(filters={'topic':'AML / KYC','priority':'A','min_score':90,'year':now().year},path=db)
    assert not search(filters={'pdf':True},path=db)
    assert not search('%',path=db)

def test_daily_weekly_zero(db,tmp_path):
    assert EMPTY in daily(path=db,data_dir=tmp_path)
    report=weekly(path=db,data_dir=tmp_path)
    for section in SECTIONS: assert section in report
    assert '근거 부족' in report

def test_reports_versions(db,doc,tmp_path):
    ident,_=register(doc,db)
    first=daily(path=db,data_dir=tmp_path)
    assert 'TEST_DATA AML' in first
    assert daily(path=db,data_dir=tmp_path)==first
    tomorrow=(now().date()+timedelta(days=1)).isoformat()
    assert EMPTY in daily(tomorrow,db,tmp_path)
    register(dict(doc,summary='TEST_DATA new version'),db)
    assert 'TEST_DATA new version' in daily(tomorrow,db,tmp_path)
    assert 'TEST_DATA AML' in weekly(path=db,data_dir=tmp_path)
    assert search_reports('TEST_DATA AML',db)
    assert not search_reports('%nonexistent',db)

def test_unverified_excluded(db,doc,tmp_path):
    register(dict(doc,verification_status='확인되지 않음'),db)
    assert EMPTY in daily(path=db,data_dir=tmp_path)

def test_test_data_guard(db,doc,tmp_path):
    with pytest.raises(ValueError): register(dict(doc,is_test=1),db)
    register(dict(doc,is_test=1),db,allow_test=True)
    assert not search(path=db)
    assert EMPTY in daily(path=db,data_dir=tmp_path)

def test_ideas_require_evidence(db,doc):
    one,_=register(doc,db)
    with pytest.raises(ValueError): create_idea({'title':'TEST_DATA'},[one],db)
    two,_=register(dict(doc,title='TEST_DATA second source',source_url='https://example.com/two'),db)
    ident=create_idea({'title':'TEST_DATA supported question','research_gap':'TEST_DATA gap'},[one,two],db)
    assert len(query('SELECT * FROM idea_documents WHERE idea_id=?',(ident,),db))==2

def test_pdf_metadata(tmp_path):
    writer=PdfWriter(); writer.add_blank_page(width=100,height=100); writer.add_metadata({'/Title':'TEST_DATA PDF','/Author':'TEST_DATA'})
    stream=BytesIO(); writer.write(stream)
    body=stream.getvalue(); info=metadata(body)
    assert info['pages']==1 and info['title']=='TEST_DATA PDF' and len(info['hash'])==64
    with pytest.raises(ValueError): metadata(b'not pdf')
    class MockClient:
        def get(self,*args): return body,{},'https://example.com/test.pdf'
    local,_=archive({'title':'TEST_DATA','jurisdiction':'Korea','pdf_url':'https://example.com/test.pdf','publication_date':'2026-01-01'},MockClient(),tmp_path)
    assert (tmp_path/local).is_file()

def test_feed_fixture():
    from pathlib import Path
    body=(Path(__file__).parent/'fixtures/feed.xml').read_bytes()
    row=parse_feed(body)[0]
    assert row['title']=='TEST_DATA AML control'
    assert row['publication_date']=='2026-01-01'
    assert parse_date('not-a-date') is None
    with pytest.raises(CollectionError): parse_feed(b'<broken')

@pytest.mark.parametrize('url',['file:///etc/passwd','http://127.0.0.1/private','http://localhost/','https://user:secret@example.com/'])
def test_invalid_url(url):
    with pytest.raises((ValueError,CollectionError)): public_url(url)

def test_network_failure_continues(db,monkeypatch):
    def fail(*args): raise CollectionError('timeout','TEST_DATA simulated timeout')
    monkeypatch.setattr(PublicClient,'get',fail)
    result=collect(path=db)
    assert result['status']=='PARTIAL' and result['error_count']==4
    assert len(query('SELECT * FROM errors WHERE category=?',('timeout',),db))==4
    assert not query('SELECT * FROM documents',path=db)

def test_verify_fixture():
    source={'id':'TEST_DATA','homepage':'https://example.com/','jurisdiction':'Global','name':'TEST_DATA institution','tier':0}
    row={'title':'TEST_DATA AML','source_url':'https://example.com/article','publication_date':'2026-01-01','feed_summary':'TEST_DATA'}
    class MockClient:
        def get(self,*args): return b'<html><h1>TEST_DATA AML</h1><meta name="citation_publication_date" content="2026-01-01"></html>',{'Content-Type':'text/html'},row['source_url']
    assert verify_document(row,source,MockClient())['verification_status']=='VERIFIED'
    with pytest.raises(CollectionError): verify_document(dict(row,publication_date='2025-01-01'),source,MockClient())

def test_collection_preserves_review(db,doc,monkeypatch):
    import research.pipeline as pipeline
    source=query('SELECT * FROM sources WHERE enabled=1 LIMIT 1',path=db)[0]
    with connect(db) as c: c.execute('UPDATE sources SET enabled=0 WHERE id<>?',(source['id'],))
    ident,_=register(dict(doc,document_hash='TEST_DATA old hash',legal_significance='TEST_DATA human analysis'),db)
    monkeypatch.setattr(PublicClient,'get',lambda *args: (b'<rss><channel><item><title>TEST_DATA AML</title><link>https://example.com/TEST_DATA/one</link></item></channel></rss>',{},''))
    monkeypatch.setattr(pipeline,'verify_document',lambda *args: dict(doc,document_hash='TEST_DATA new hash',pdf_url=None,evidence='TEST_DATA changed page'))
    assert collect(path=db)['updated']==1
    saved=query('SELECT * FROM documents WHERE id=?',(ident,),db)[0]
    assert saved['legal_significance']=='TEST_DATA human analysis'
    assert saved['importance_score']==100
    assert saved['verification_status']=='REVIEW_REQUIRED'

def test_mismatched_title_rejected():
    class Client:
        def get(self,*args): return b'<h1>TEST_DATA error page forbidden</h1>',{'Content-Type':'text/html'},'https://example.com/article'
    with pytest.raises(CollectionError):
        verify_document({'title':'AML internal control','source_url':'https://example.com/article'}, {'homepage':'https://example.com/'},Client())

def test_automatic_pending_digest(db,doc,tmp_path):
    register(dict(doc,components={},score_evidence={}),db)
    content=daily(path=db,data_dir=tmp_path)
    assert EMPTY in content
    assert '신규 수집 자료 — 중요도 검토 대기' in content
    assert 'TEST_DATA AML' in content
    assert not query('SELECT * FROM report_documents',path=db)
