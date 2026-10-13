import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import hashlib
import json
import pandas as pd
import streamlit as st
from research.db import initialize,query,connect
from research.paths import DATA,now,timestamp
from research.services import search,register,create_idea,search_reports,ANALYSIS_FIELDS
from research.reporting import daily,weekly
from research.scoring import score,WEIGHTS
from research.pdf import archive
from research.deduplication import canonical_url
from research.pipeline import log_error

st.set_page_config(page_title='Global Legal Research',page_icon='⚖',layout='wide')
initialize()
st.markdown('''<style>.stApp{background:#f5f7fa} h1,h2,h3{color:#172c49} [data-testid="stMetric"]{background:white;border-top:3px solid #a88748;padding:14px;border-radius:5px} [data-testid="stSidebar"]{background:#e9eef5} .block-container{max-width:1450px}</style>''',unsafe_allow_html=True)
PAGES=['Dashboard','Daily Brief','Weekly Review','Research Database','Document Detail','Cases','Papers','Regulation & Enforcement','AML / KYC','Sanctions','PDF Library','Research Ideas']
st.sidebar.title('⚖ Global Legal Research')
st.sidebar.caption('Commercial · Financial · Compliance')
if st.session_state.pop('go_detail',False):
    st.session_state['page']='Document Detail'
page=st.sidebar.radio('화면',PAGES,key='page')
st.title('Global Legal Research Dashboard' if page=='Dashboard' else page)
st.caption('한국 · 미국 · 영국 · 일본 · 국제기구 | 원문 우선 · 검증 가능 · 개인 연구 아카이브')
global_text=st.text_input('통합검색',placeholder='AML 경영진 책임 / 경제제재 CISG / 신디케이트론 상계',key='global_search')
st.sidebar.caption('운영 DB에는 TEST_DATA가 표시되지 않습니다.')
COUNTRIES=['Korea','United States','United Kingdom','Japan','Global','EU']
TYPES=['Case','Legislation','Legislative Material','Regulation','Enforcement','Consultation','Guidance','Paper','Working Paper','Report','Unclassified']
topics=[r['name'] for r in query('SELECT name FROM topics ORDER BY id')]
if global_text:
    matched_reports=search_reports(global_text)
    if matched_reports:
        with st.expander(f'통합검색: 관련 Daily / Weekly 보고서 {len(matched_reports)}건'):
            for r in matched_reports[:10]:
                st.caption(f"{r['kind']} · {r['period']}"); st.markdown(r['content'])

def link(label,url,key=None):
    if url:
        try: canonical_url(url); st.link_button(label,url)
        except ValueError: st.caption('URL 확인 필요')

def pdf_button(d):
    if d.get('local_pdf_path'):
        file=(DATA/d['local_pdf_path']).resolve()
        root=(DATA/'papers').resolve()
        if file.is_relative_to(root) and file.is_file():
            st.download_button('PDF 다운로드',file.read_bytes(),file.name,mime='application/pdf',key=f"pdf-{d['id']}")
    link('공개 PDF 원문',d.get('pdf_url'))

def cards(rows):
    if not rows: st.info('조건에 맞는 자료가 없습니다. 자료 등록 또는 수집 후 다시 확인하세요.'); return
    st.caption(f'{len(rows)}건 · 아래 카드는 최대 50건 표시')
    for d in rows[:50]:
        with st.container(border=True):
            st.caption(f"{d['jurisdiction']} · {d['primary_topic']} · {d['source_type']} · {d['verification_status']}")
            st.subheader(d['title'])
            st.write(f"{d['author_or_institution']} | {d['publication_date'] or '날짜 확인되지 않음'} | {d['importance_score']}/100 · Priority {d['priority']} · {d['update_status']}")
            st.write((d['summary'] or '확인되지 않음')[:500])
            cols=st.columns(3)
            with cols[0]:
                if st.button('상세보기',key=f"detail-{d['id']}"):
                    st.session_state['selected_id']=d['id']; st.session_state['go_detail']=True; st.rerun()
            with cols[1]: link('Primary Source 열기',d['source_url'])
            with cols[2]: pdf_button(d)

def filters(prefix,default_topic=None,default_type=None):
    cols=st.columns(4)
    with cols[0]: country=st.selectbox('국가',['전체']+COUNTRIES,key=prefix+'country')
    with cols[1]: topic=st.selectbox('Topic',['전체']+topics,index=(topics.index(default_topic)+1) if default_topic else 0,key=prefix+'topic')
    with cols[2]: priority=st.selectbox('Priority',['전체','A','B','C','D'],key=prefix+'priority')
    with cols[3]: minimum=st.slider('최저 점수',0,100,0,key=prefix+'score')
    cols=st.columns(4)
    with cols[0]: year=st.selectbox('발행연도',['전체']+[r['year'] for r in query("SELECT DISTINCT substr(publication_date,1,4) year FROM documents WHERE publication_date IS NOT NULL ORDER BY year DESC")],key=prefix+'year')
    with cols[1]: source_type=st.selectbox('자료 유형',['전체']+TYPES,index=TYPES.index(default_type)+1 if default_type else 0,key=prefix+'type')
    with cols[2]: only_pdf=st.checkbox('PDF 있음',key=prefix+'pdf')
    with cols[3]: sort=st.selectbox('정렬',['Newest','Highest Score','Recently Added'],key=prefix+'sort')
    result={'jurisdiction':country,'topic':topic,'priority':priority,'min_score':minimum,'year':year,'source_type':source_type,'pdf':only_pdf}
    return {k:v for k,v in result.items() if v!='전체'},sort

def manual_registration():
    with st.expander('원문 확인 후 자료 등록'):
        st.caption('추측한 날짜·사건번호·저자를 입력하지 마세요. 미확인 날짜는 비워 둡니다. 상세 화면에서 검토 점수와 분석을 추가합니다.')
        with st.form('register'):
            title=st.text_input('제목'); url=st.text_input('Primary Source URL')
            country=st.selectbox('관할',COUNTRIES); kind=st.selectbox('유형',TYPES)
            institution=st.text_input('기관'); author=st.text_input('저자')
            published=st.text_input('원문 발행일 YYYY-MM-DD (미확인: 빈칸)')
            selected=st.multiselect('복수 Topic',topics)
            case=st.text_input('사건번호'); number=st.text_input('문서번호'); doi=st.text_input('DOI')
            citation=st.text_input('인용 표기'); pdf=st.text_input('공개 PDF URL')
            summary=st.text_area('원문 근거 요약'); evidence=st.text_area('검증 근거 (원문 위치·확인 내용)')
            tier=st.selectbox('Source Tier',list(range(6)),index=1)
            checked=st.checkbox('원문 기관·제목·발행일을 직접 확인했습니다')
            related=st.number_input('후속자료의 선행 DB ID (없음: 0)',min_value=0,step=1)
            relation=st.selectbox('후속 관계',['UPDATE','APPEAL','FINAL_DECISION','FINAL_RULE','JOURNAL_PUBLICATION','FOLLOW_UP'])
            if st.form_submit_button('DB 등록'):
                try:
                    if checked and (not evidence or not published): raise ValueError('검증 완료에는 발행일과 검증 근거가 필요합니다')
                    ident,status=register(dict(title=title,source_url=url,jurisdiction=country,source_type=kind,institution=institution,author=author,publication_date=published or None,topics=selected or None,case_number=case or None,document_number=number or None,doi=doi or None,citation=citation,pdf_url=pdf or None,summary=summary,source_tier=tier,evidence=evidence,verification_status='VERIFIED' if checked else '확인되지 않음',verified_at=timestamp() if checked else None),related_to=int(related) or None,relation_type=relation)
                    st.success(f'{status} · DB ID {ident}')
                except Exception as exc: st.error(str(exc))

def detail():
    rows=search(sort='Recently Added')
    if not rows: st.info('등록된 자료가 없습니다. Research Database에서 자료를 등록하세요.'); return
    ids=[d['id'] for d in rows]; selected=st.session_state.get('selected_id',ids[0])
    ident=st.selectbox('자료',ids,index=ids.index(selected) if selected in ids else 0,format_func=lambda i: next(d['title'] for d in rows if d['id']==i))
    d=next(d for d in rows if d['id']==ident)
    st.subheader(d['title']); link('Primary Source',d['source_url']); pdf_button(d)
    tagrows=query('SELECT t.name FROM document_topics dt JOIN topics t ON t.id=dt.topic_id WHERE document_id=?',(ident,))
    st.write('복수 Topic: '+', '.join(r['name'] for r in tagrows))
    for key in ['jurisdiction','source_type','publication_date','institution','author','citation','case_number','document_number','doi','importance_score','priority','score_reason','summary','verification_status','evidence']+ANALYSIS_FIELDS:
        st.markdown(f'**{key.replace("_"," ").title()}**'); st.write(d.get(key) or '확인되지 않음')
    related=query('SELECT r.relation_type,d.id,d.title FROM relationships r JOIN documents d ON d.id=CASE WHEN r.from_document=? THEN r.to_document ELSE r.from_document END WHERE r.from_document=? OR r.to_document=?',(ident,ident,ident))
    st.subheader('관련자료 / 후속판례'); st.dataframe(pd.DataFrame(related),hide_index=True) if related else st.caption('등록된 명시적 관계 없음')
    if d.get('pdf_url') and not d.get('local_pdf_path') and st.button('공개 PDF 보관'):
        try:
            local,info=archive(d)
            with connect() as c: c.execute('UPDATE documents SET local_pdf_path=? WHERE id=?',(local,ident))
            st.success(f"PDF 저장: {info['pages']} pages · SHA256 {info['hash']}")
        except Exception as exc:
            log_error(None,d.get('source_id'),'pdf',str(exc))
            st.error(f'PDF 저장 실패: {exc}. 자료는 DB에 유지됩니다.')
    with st.expander('원문 검토 · 점수 · 법적 분석 수정'):
        with st.form('review'):
            kind=st.selectbox('확인한 자료 유형',TYPES,index=TYPES.index(d['source_type']) if d['source_type'] in TYPES else 10)
            published=st.text_input('확인한 발행일 YYYY-MM-DD',d['publication_date'] or '')
            evidence=st.text_area('원문 검증 근거',d['evidence'] or '')
            verified=st.checkbox('원문과 발행일을 직접 재검증했습니다',value=d['verification_status']=='VERIFIED')
            selected_topics=st.multiselect('검토한 복수 Topic',topics,default=[t['name'] for t in tagrows if t['name'] in topics])
            primary=st.selectbox('Primary Topic',topics,index=topics.index(d['primary_topic']) if d['primary_topic'] in topics else 0)
            summary=st.text_area('Summary',d['summary'] or '')
            analysis={k:st.text_area(k.replace('_',' ').title(),d.get(k) or '확인되지 않음') for k in ANALYSIS_FIELDS}
            parts=json.loads(d['score_components'] or '{}'); components={}; reasons={}
            for key,cap in list(WEIGHTS.items())[:5]:
                components[key]=st.number_input(f'{key} 점수 (상한 {cap})',0,cap,int(parts.get(key,0)))
                reasons[key]=st.text_input(f'{key} 점수 근거',key='reason'+key)
            if st.form_submit_button('검토 저장'):
                try:
                    from datetime import date
                    if published and date.fromisoformat(published)>now().date(): raise ValueError('미래 발행일은 등록할 수 없습니다')
                    if verified and (not published or not evidence): raise ValueError('검증 완료에는 발행일과 근거가 필요합니다')
                    total,priority,reason,parts=score(components,published or None,now().date(),reasons)
                    updates=dict(analysis,summary=summary,source_type=kind,publication_date=published or None,primary_topic=primary,evidence=evidence,verification_status='VERIFIED' if verified else '확인되지 않음',verified_at=timestamp() if verified else None,importance_score=total,priority=priority,score_reason=reason,score_components=json.dumps(parts),updated_at=timestamp(),update_status='UPDATE')
                    updates['content_hash']=hashlib.sha256(json.dumps(dict(d,**updates),sort_keys=True).encode()).hexdigest()
                    with connect() as c:
                        c.execute('UPDATE documents SET '+','.join(k+'=?' for k in updates)+' WHERE id=?',(*updates.values(),ident))
                        c.execute('DELETE FROM document_topics WHERE document_id=?',(ident,))
                        for topic in dict.fromkeys([primary,*selected_topics]): c.execute('INSERT INTO document_topics VALUES(?,(SELECT id FROM topics WHERE name=?))',(ident,topic))
                    st.success('검토 저장 완료'); st.rerun()
                except ValueError as exc: st.error(str(exc))

if global_text and page not in ('Research Database','Document Detail'):
    st.subheader('통합 검색 결과'); cards(search(global_text))
elif page=='Dashboard':
    rows=search(sort='Highest Score'); today=now().date(); week=today.fromordinal(today.toordinal()-today.weekday()).isoformat()
    todayrows=[d for d in rows if d['first_seen'][:10]==today.isoformat()]
    counts=[len(todayrows),sum(d['priority']=='A' for d in rows),sum(d['first_seen'][:10]>=week for d in rows),sum(d['priority'] in ('A','B') for d in rows),len(search(filters={'topic':'AML / KYC','since':today.isoformat()})),len(search(filters={'topic':'Sanctions','since':today.isoformat()}))]
    for col,label,count in zip(st.columns(6),['오늘 신규','Priority A','이번 주 신규','Must Read A/B','AML/KYC 신규','Sanctions 신규'],counts): col.metric(label,count)
    st.subheader('최근 핵심자료'); cards(rows[:10])
    with st.expander('수집 상태 · 출처 · 오류'):
        st.dataframe(pd.DataFrame(query('SELECT * FROM collection_runs ORDER BY id DESC LIMIT 10')),hide_index=True)
        st.dataframe(pd.DataFrame(query('SELECT name,jurisdiction,enabled,verification_status,last_checked FROM sources')),hide_index=True)
        st.dataframe(pd.DataFrame(query('SELECT category,message,created_at FROM errors ORDER BY id DESC LIMIT 20')),hide_index=True)
elif page in ('Daily Brief','Weekly Review'):
    kind='daily' if page=='Daily Brief' else 'weekly'
    chosen=st.date_input('기준 날짜',now().date())
    if st.button('DB로 보고서 생성 / 갱신'):
        (daily if kind=='daily' else weekly)(chosen.isoformat()); st.success('생성 완료 (신규 웹 수집은 run_daily.bat)')
    reports=query('SELECT * FROM reports WHERE kind=? ORDER BY period DESC',(kind,))
    if reports:
        period=st.selectbox('날짜 / 주차',[r['period'] for r in reports])
        report=next(r for r in reports if r['period']==period)
        if kind=='weekly':
            sections=report['content'].split('\n## ')
            section=st.selectbox('섹션 Navigation',['전체']+[s.split('\n',1)[0] for s in sections[1:]])
            st.markdown(report['content'] if section=='전체' else '## '+next(s for s in sections[1:] if s.startswith(section+'\n')))
        else:
            st.markdown(report['content']); f,sort=filters('daily')
            docs=search(filters=f,sort=sort); selected_ids={r['document_id'] for r in query('SELECT document_id FROM report_documents WHERE report_id=?',(report['id'],))}
            cards([d for d in docs if d['id'] in selected_ids])
        st.download_button('Markdown 다운로드',report['content'],period+'.md')
    else: st.info('아직 보고서가 없습니다. 위 버튼 또는 실행 파일로 생성하세요.')
elif page=='Document Detail': detail()
elif page=='Research Ideas':
    ideas=query('SELECT * FROM research_ideas ORDER BY id DESC')
    if not ideas: st.info('검증자료 2건 이상을 근거로 연구주제를 작성하세요.')
    for idea in ideas:
        with st.expander(idea['title']):
            for key,value in idea.items(): st.write(f'{key}: {value or "확인되지 않음"}')
            st.dataframe(pd.DataFrame(query('SELECT d.title,d.source_url FROM idea_documents i JOIN documents d ON d.id=i.document_id WHERE i.idea_id=?',(idea['id'],))),hide_index=True)
    with st.form('idea'):
        data={k:st.text_area(label) for k,label in [('title','제목 후보'),('problem','문제의식'),('legal_issue','핵심 법적쟁점'),('jurisdictions','관련 국가'),('existing_research','기존 연구'),('research_gap','Research Gap'),('korean_connection','한국법 연결'),('comparative_potential','비교법 가능성'),('paper_fit','석사논문 적합도'),('seminar_fit','세미나 적합도')]}
        docs=search(); ids=st.multiselect('주요 근거자료',[d['id'] for d in docs],format_func=lambda i: next(d['title'] for d in docs if d['id']==i))
        if st.form_submit_button('연구주제 저장'):
            try: create_idea(data,ids); st.success('저장 완료')
            except ValueError as exc: st.error(str(exc))
else:
    default_topic={'AML / KYC':'AML / KYC','Sanctions':'Sanctions'}.get(page)
    default_type={'Cases':'Case','Papers':'Paper'}.get(page)
    f,sort=filters(page,default_topic,default_type)
    if page=='Regulation & Enforcement':
        institution=st.selectbox('기관',['전체']+[r['name'] for r in query('SELECT name FROM sources ORDER BY name')])
        if institution!='전체': f['institution']=institution
    if page=='PDF Library': f['pdf']=True
    rows=search(global_text,f,sort)
    if page=='Regulation & Enforcement': rows=[d for d in rows if d['source_type'] in ('Regulation','Enforcement','Consultation','Guidance','Legislation')]
    if page=='Papers' and f.get('source_type')=='Paper': rows+=search(global_text,dict(f,source_type='Working Paper'),sort)
    if page in ('AML / KYC','Sanctions') and rows:
        st.dataframe(pd.DataFrame(rows).groupby(['jurisdiction','primary_topic']).size().reset_index(name='자료수'),hide_index=True)
    if page=='Research Database': manual_registration()
    cards(rows)
    if rows: st.download_button('검색 결과 CSV 내보내기',pd.DataFrame(rows).to_csv(index=False).encode('utf-8-sig'),'research.csv','text/csv')
