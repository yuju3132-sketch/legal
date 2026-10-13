from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from research.services import register
from research.reporting import daily,weekly

PAGES=['Dashboard','Daily Brief','Weekly Review','Research Database','Document Detail','Cases','Papers','Regulation & Enforcement','AML / KYC','Sanctions','PDF Library','Research Ideas']

@pytest.mark.parametrize('page',PAGES)
@pytest.mark.parametrize('populated',[False,True])
def test_all_pages(tmp_path,monkeypatch,page,populated,doc):
    # AppTest executes in-process, isolate the entire data root per test.
    import research.paths as paths
    import research.db as dbmod
    import research.reporting as reporting
    import research.pdf as pdfmod
    monkeypatch.setattr(paths,'DATA',tmp_path); monkeypatch.setattr(paths,'DB',tmp_path/'database/research.db')
    monkeypatch.setattr(dbmod,'DB',paths.DB); monkeypatch.setattr(reporting,'DATA',tmp_path); monkeypatch.setattr(pdfmod,'DATA',tmp_path)
    dbmod.initialize()
    if populated:
        register(doc)
        daily(); weekly()
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app/Home.py'),default_timeout=20).run()
    app.sidebar.radio[0].set_value(page).run()
    assert not app.exception, '\n'.join(str(x.value) for x in app.exception)

def test_card_detail_navigation(tmp_path,monkeypatch,doc):
    import research.db as dbmod
    import research.paths as paths
    monkeypatch.setattr(dbmod,'DB',tmp_path/'research.db'); monkeypatch.setattr(paths,'DATA',tmp_path)
    dbmod.initialize(); register(doc)
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app/Home.py')).run()
    app.button[0].click().run()
    assert not app.exception
    assert app.sidebar.radio[0].value=='Document Detail'

def test_manual_registration_and_review(tmp_path,monkeypatch):
    import research.db as dbmod
    import research.paths as paths
    monkeypatch.setattr(dbmod,'DB',tmp_path/'research.db'); monkeypatch.setattr(paths,'DATA',tmp_path)
    dbmod.initialize()
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app/Home.py')).run()
    app.sidebar.radio[0].set_value('Research Database').run()
    def widget(group,label): return next(w for w in group if w.label==label)
    widget(app.text_input,'제목').set_value('TEST_DATA manual AML control')
    widget(app.text_input,'Primary Source URL').set_value('https://example.com/TEST_DATA/manual')
    widget(app.text_input,'원문 발행일 YYYY-MM-DD (미확인: 빈칸)').set_value(paths.now().date().isoformat())
    widget(app.text_area,'검증 근거 (원문 위치·확인 내용)').set_value('TEST_DATA mock source evidence')
    widget(app.checkbox,'원문 기관·제목·발행일을 직접 확인했습니다').check()
    widget(app.button,'DB 등록').click().run()
    assert not app.exception
    assert len(dbmod.query('SELECT * FROM documents'))==1
    app.sidebar.radio[0].set_value('Document Detail').run()
    for key,cap in [('A',25),('B',20),('C',15),('D',15),('E',15)]:
        widget(app.number_input,f'{key} 점수 (상한 {cap})').set_value(cap)
        widget(app.text_input,f'{key} 점수 근거').set_value('TEST_DATA review evidence')
    widget(app.button,'검토 저장').click().run()
    assert not app.exception
    assert dbmod.query('SELECT priority FROM documents')[0]['priority']=='A'
