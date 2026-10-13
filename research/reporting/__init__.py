from datetime import date,timedelta
from pathlib import Path
from research.paths import DATA,timestamp,now
from research.db import connect,query
from research.services import ANALYSIS_FIELDS

EMPTY='No material development meeting the reporting threshold was identified today.'
SECTIONS=['Executive Summary','Top 5 Developments','Corporate Law','Financial Law','Capital Markets Law','Corporate Finance Law','Financial Institution Governance & Internal Control','AML / KYC / Financial Crime Compliance','Sanctions & International Financial Regulation','Trust Law','International Transactions','Insolvency & Restructuring','Korea / US / UK / Japan Comparative Analysis','Global Regulatory Standards','New Academic Papers','Research Implications','Research Gaps',"Potential Seminar / Master's Paper Topics",'Must Read Top 3']

def entry(d):
    fields=[('Jurisdiction','jurisdiction'),('Topic','primary_topic'),('Source Type','source_type'),('Institution / Author','author_or_institution'),('Publication Date','publication_date'),('Importance Score','importance_score'),('Why Selected','score_reason'),('Summary','summary')]+[(k.replace('_',' ').title(),k) for k in ANALYSIS_FIELDS]+[('Verification Evidence','evidence'),('Primary Source','source_url'),('PDF','pdf_url')]
    return f"### {d['title']} [{d['update_status']}]\n\n"+'\n\n'.join(f'**{label}:** {d.get(key) or "확인되지 않음"}' for label,key in fields)

def save_report(kind,period,content,documents,path=None,data_dir=None):
    relative=f'reports/{kind}/{period}.md'
    dest=Path(data_dir or DATA)/relative; dest.parent.mkdir(parents=True,exist_ok=True)
    with connect(path) as c:
        c.execute('INSERT INTO reports(kind,period,path,content,created_at) VALUES(?,?,?,?,?) ON CONFLICT(kind,period) DO UPDATE SET content=excluded.content,created_at=excluded.created_at',(kind,period,relative,content,timestamp()))
        ident=c.execute('SELECT id FROM reports WHERE kind=? AND period=?',(kind,period)).fetchone()[0]
        c.execute('DELETE FROM report_documents WHERE report_id=?',(ident,))
        c.executemany('INSERT INTO report_documents VALUES(?,?,?)',[(ident,d['id'],d['content_hash']) for d in documents])
    temp=dest.with_suffix('.tmp'); temp.write_text(content,encoding='utf-8'); temp.replace(dest)
    return content

def daily(day=None,path=None,data_dir=None):
    day=day or now().date().isoformat()
    # Refresh same day: preserve existing picks, append new eligible versions.
    rows=query("SELECT d.* FROM documents d WHERE is_test=0 AND verification_status='VERIFIED' AND publication_date IS NOT NULL AND publication_date>=? AND publication_date<=? AND importance_score>=85 AND substr(updated_at,1,10)<=? AND (NOT EXISTS(SELECT 1 FROM report_documents rd JOIN reports r ON r.id=rd.report_id WHERE rd.document_id=d.id AND rd.version_hash=d.content_hash AND r.kind='daily' AND r.period<>?) OR EXISTS(SELECT 1 FROM report_documents rd JOIN reports r ON r.id=rd.report_id WHERE rd.document_id=d.id AND r.kind='daily' AND r.period=?)) ORDER BY importance_score DESC LIMIT 5",((date.fromisoformat(day)-timedelta(days=7)).isoformat(),day,day,day,day),path)
    content=f'# Daily Legal Research Brief — {day}\n\n'
    runs=query('SELECT status,finished_at,error_count FROM collection_runs ORDER BY id DESC LIMIT 1',path=path)
    content+=('최근 수집 상태: '+str(runs[0]) if runs else '수집 실행 기록 없음 (DB 기반 보고서).')+'\n\n전체 출처의 조사 완료를 뜻하지 않습니다. 평가 대기 자료와 접근 실패 출처를 별도로 확인하세요.\n\n'
    content+='선정: 검증된 발행일·원문, 최근 7일, Priority A. 미확인 분석은 표시합니다.\n\n'
    content+='\n\n'.join(entry(d) for d in rows) if rows else EMPTY
    pending=query("SELECT title,jurisdiction,source_url,summary,verification_status FROM documents WHERE is_test=0 AND importance_score<85 AND substr(first_seen,1,10)=? ORDER BY id DESC LIMIT 10",(day,),path)
    if pending:
        content+='\n\n## 신규 수집 자료 — 중요도 검토 대기\n\n아래는 수집 목록이며, 중요 법률 변화로 선정한 자료가 아닙니다. 법적 의미·점수는 아직 검토 대기입니다.\n\n'
        content+='\n\n'.join(f"- **{d['title']}** ({d['jurisdiction']}, {d['verification_status']})\n  {d['source_url']}\n  {d['summary'] or '확인되지 않음'}" for d in pending)
    return save_report('daily',day,content,rows,path,data_dir)

def weekly(day=None,path=None,data_dir=None):
    day=date.fromisoformat(day) if day else now().date()
    start=day-timedelta(days=day.weekday()); end=start+timedelta(days=6)
    period=f'{day.isocalendar().year}-W{day.isocalendar().week:02d}'
    docs=query("SELECT * FROM documents WHERE is_test=0 AND verification_status='VERIFIED' AND importance_score>=70 AND publication_date IS NOT NULL AND publication_date<=? AND substr(updated_at,1,10)>=? AND substr(updated_at,1,10)<=? ORDER BY importance_score DESC",(day.isoformat(),start.isoformat(),day.isoformat()),path)
    tags={d['id']:{r['name'] for r in query('SELECT t.name,t.parent FROM topics t JOIN document_topics dt ON dt.topic_id=t.id WHERE dt.document_id=?',(d['id'],),path)} for d in docs}
    briefs=query("SELECT period FROM reports WHERE kind='daily' AND period BETWEEN ? AND ?",(start.isoformat(),end.isoformat()),path)
    content=f'# Weekly Legal Research Review — {period}\n\n분석 기준: {start} ~ {day} (Asia/Seoul). Daily {len(briefs)}건, 검증된 A/B 자료 {len(docs)}건.\n\n법적 결론은 검토자가 입력한 분석만 사용합니다. 자동 비교는 태그·국가·공식 출처의 근거 지도이며, 인과관계나 법률 동일성을 뜻하지 않습니다.\n\n'
    for index,section in enumerate(SECTIONS,1):
        content+=f'## {index}. {section}\n\n'
        if section=='Executive Summary':
            content+=f'검증 자료 {len(docs)}건. 미확인 쟁점은 원문 재검토가 필요합니다.\n\n'
        elif section in ('Top 5 Developments','Must Read Top 3'):
            subset=docs[:5 if section=='Top 5 Developments' else 3]
            content+='\n\n'.join(entry(d) for d in subset) if subset else '보고 기준에 맞는 자료 없음.'
        elif section=='Korea / US / UK / Japan Comparative Analysis':
            for jurisdiction in ('Korea','United States','United Kingdom','Japan'):
                subset=[d for d in docs if d['jurisdiction']==jurisdiction]
                content+=f'**{jurisdiction}:** '+('; '.join(f"{d['title']} — {d['comparative_law_relevance']}" for d in subset) or '비교근거 부족')+'\n\n'
        elif section=="Potential Seminar / Master's Paper Topics":
            ideas=query('SELECT * FROM research_ideas ORDER BY id DESC LIMIT 5',path=path)
            content+='\n'.join(f"- {r['title']}: {r['research_gap']}" for r in ideas) or '근거가 충분한 저장 연구주제 없음.'
        elif section in ('Research Implications','Research Gaps'):
            key='research_gap' if section=='Research Gaps' else 'research_relevance'
            content+='\n'.join(f"- {d['title']}: {d[key]}" for d in docs) or '분석자료 없음.'
        else:
            topic={'AML / KYC / Financial Crime Compliance':'AML / KYC','Sanctions & International Financial Regulation':'Sanctions','Financial Institution Governance & Internal Control':'Internal Control'}.get(section,section)
            subset=[d for d in docs if topic in tags[d['id']] or (section=='Global Regulatory Standards' and d['jurisdiction']=='Global') or (section=='New Academic Papers' and d['source_type'] in ('Paper','Working Paper'))]
            content+='\n'.join(f"- {d['title']} | {d['jurisdiction']} | {d['legal_significance']} | {d['source_url']}" for d in subset) or '검증된 A/B 자료 없음.'
        content+='\n\n'
    content+='## 교차분야 근거 지도\n\n'
    for left,right in [('AML / KYC','Internal Control'),('AML / KYC','Corporate Law'),('AML / KYC','Sanctions'),('Sanctions','International Transactions'),('Sanctions','Payments'),('Sanctions','CISG'),('Corporate Law','Director Liability'),('Capital Markets Law','Internal Control'),('Corporate Finance Law','Insolvency & Restructuring')]:
        subset=[d for d in docs if {left,right}<=tags[d['id']]]
        content+=f'- {left} × {right}: '+('; '.join(f"{d['title']} ({d['source_url']})" for d in subset) or '근거 부족')+'\n'
    return save_report('weekly',period,content,docs,path,data_dir)
