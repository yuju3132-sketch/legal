# Global Commercial, Financial & Compliance Law Research Agent

**처음 한 번:** Python 3.10 이상(권장 3.12)을 python.org에서 설치하며 **Add Python to PATH**를 선택한 뒤 `setup.bat`를 더블클릭합니다. 인터넷 연결이 필요합니다.

**평소 사용:** `run_app.bat` 더블클릭 → 서버 시작 후 기본 브라우저에서 Global Legal Research Dashboard가 열립니다.

**수동 Daily:** `run_daily.bat` — 공개 피드를 수집하고 DB로 Daily를 만듭니다.

**수동 Weekly:** `run_weekly.bat` — 이번 주 A/B 검토자료로 Weekly 초안을 만듭니다.

**백업:** `backup.bat` — SQLite 안전 백업과 PDF·보고서·설정 ZIP을 `backups/`에 저장합니다. 이 폴더를 다른 디스크에 복사하세요.

## 사용하는 순서

1. Dashboard에서 수집상태와 오류를 확인합니다. 첫 화면이 비어 있어도 오류가 아닙니다.
2. Research Database의 “원문 확인 후 자료 등록”에서 자료를 입력할 수 있습니다. 추측하지 말고 미확인 날짜는 비웁니다.
3. 상세보기에서 “원문 검토 · 점수 · 법적 분석 수정”을 엽니다. A~E 점수와 각각의 근거를 입력하고 법적 평가를 작성합니다. 자동 수집자료는 평가 대기이며 Priority D로 시작합니다.
4. Daily/Weekly 화면에서 DB로 보고서를 생성합니다. 원문 검증·발행일·점수 기준을 충족하지 않으면 빈 보고서가 정상입니다.
5. 상단 통합검색은 공백으로 나눈 단어를 모두 포함하는 자료를 찾습니다. 자료 카드 상세보기, 원문 링크, PDF 다운로드를 사용하세요.
6. 연구주제는 검증된 실제 자료 2건 이상을 선택하고 Research Gap을 직접 작성해 저장합니다.

법적 분석을 자동으로 창작하는 LLM은 연결하지 않았습니다. Weekly는 분야/국가/교차태그 근거 지도와 저장된 분석으로 만드는 구조화 초안입니다. 원문 재검토와 심층 비교법 분석은 연구자 또는 automation prompt를 수행하는 에이전트가 담당합니다. 법률자문이나 고객/거래 제재 스크리닝 도구가 아닙니다.

## 주요 구조

```text
legal/
  AGENTS.md, README.md, requirements.txt, requirements.lock.txt
  setup.bat, run_app.bat, run_daily.bat, run_weekly.bat, backup.bat
  app/Home.py                 12개 화면, 통합검색, 등록/검토 UI
  config/                     연구범위, 출처, 분류, 점수, 보고서 정책
  database/schema.sql         초기화/마이그레이션 구조
  database/research.db         SQLite 장기기억 (첫 실행 시 생성)
  research/db.py, services.py, pipeline.py, pdf.py
  research/collectors/, classifiers/, deduplication/, scoring/, reporting/
  scripts/manage.py, launch_app.py
  papers/{Korea,US,UK,Japan,Global}/
  reports/{daily,weekly,topic_reviews}/
  automation/DAILY.md, WEEKLY.md
  logs/, backups/, tests/fixtures/
```

## 데이터와 출처

SQLite는 documents/topics/authors/institutions/sources/reports/research_ideas/relationships/collection_runs/errors와 연결 테이블을 관리합니다. 검색은 SQL 매개변수와 문자열/키워드 기반이며 별도 벡터 DB가 필요 없습니다. TEST_DATA는 pytest의 임시 디렉터리만 사용하고 운영 검색/보고서에서 제외합니다.

출처 레지스트리 60곳 이상 중 BIS·FSB·Federal Reserve·FCA의 RSS/Atom만 기본 활성화됩니다. HTML 일반 검색, 한국·일본 포털, paywall 자료는 자동 수집을 구현했다고 주장하지 않습니다. 출처의 공식성·현재 피드는 실제 사용 시 확인하며 접근 실패는 추정 자료로 대체하지 않습니다. HTTPS/TLS 검증, robots 확인, 속도·크기 제한을 적용합니다. 오류가 있으면 해당 사이트만 건너뛰고 CLI는 exit 2로 부분 실패를 알립니다. HTTP 200은 법적 내용 전체의 검토 완료를 뜻하지 않습니다.

피드는 자동 분류와 검증 메타데이터를 기록합니다. 원문에 없는 사건번호/DOI/날짜/법적 분석을 생성하지 않습니다. 제목·URL·DOI·기관/관할별 사건번호·문서번호·hash·저자/기관/날짜를 중복 대조합니다. 같은 식별자 변경은 UPDATE, 새로운 상급심/최종규칙은 선행자료 ID를 지정해 연결합니다.

PDF는 상세 화면의 “공개 PDF 보관” 또는 CLI `--pdf`로 합법적으로 공개된 것만 다운로드합니다. 실패해도 자료는 남습니다. 파일명과 SHA256을 계산하고 DB에 상대경로를 연결합니다. 실제 PDF가 저장된 경우 다운로드 버튼이 나타납니다.

## 종료·오류·업데이트

앱 종료: 서버 창에서 Ctrl+C를 누릅니다. 브라우저를 닫는 것만으로 서버가 종료되지는 않습니다. 8501 포트를 사용합니다. 이미 사용 중이면 기존 앱을 먼저 종료합니다. 서버는 로컬 컴퓨터에서만 접근 가능합니다.

오류: 실행창의 메시지와 `logs/research.log`, Dashboard의 오류 표를 확인하세요. 403/404/timeout/robots 차단은 우회하지 않습니다. 사이트 변경은 `config/sources.json`의 검증된 feed_url을 수정하고 재초기화합니다. 기존 source 검증상태/사용자가 DB에서 바꾼 enabled/feed 설정은 초기화가 덮어쓰지 않습니다. Windows Python 미설치/권한/방화벽은 사용자 PC에서 점검해야 합니다.

업데이트 전 `backup.bat`로 백업하세요. 소스 업데이트 후 `setup.bat`를 다시 실행합니다. DB는 지우지 않으며 versioned migration을 추가할 구조가 있습니다. `requirements.txt`는 직접 의존성 고정, `requirements.lock.txt`는 검증한 Python 3.12/Linux 환경의 전체 버전 기록입니다. Windows는 `requirements.txt`로 호환 wheel을 설치합니다.

## 자동화

이 작업은 Codex 자동화를 실제 등록하지 않습니다. `automation/DAILY.md`와 `WEEKLY.md`의 Name, Schedule, Working Directory, Prompt를 Codex 자동화 UI에 입력하세요. Daily 월~금 07:00 / Weekly 금요일 18:00, **Asia/Seoul**. UI가 자동화를 지원하지 않으면 같은 문서의 Windows 작업 스케줄러 설정을 사용합니다. CLI 자동화는 평가 점수/법적 분석을 자동 작성하지 않습니다.

## 개발·Linux/클라우드

```bash
cd /workspace/legal
python -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python scripts/manage.py init
.venv/bin/python -m pytest -q
.venv/bin/python scripts/manage.py daily --offline
.venv/bin/python scripts/manage.py weekly
.venv/bin/python -m streamlit run app/Home.py --server.address=127.0.0.1 --server.headless=true --browser.gatherUsageStats=false
```

`LEGAL_DATA_DIR`로 별도 데이터 루트를 지정할 수 있습니다. 이는 비밀 값이 아니며 테스트/백업 분리에 사용합니다. 라이브 프로세스는 클라우드 스냅샷에 유지되지 않으므로 새 작업에서 서버를 다시 시작해야 합니다. 클라우드에서 localhost 미리보기 링크는 제공하지 않습니다.

## 백업·확장

연구자산은 research.db와 papers/, reports/, config/입니다. 실행 중 DB를 파일 복사하기보다 backup.bat의 SQLite backup API를 사용하세요. 복구는 앱을 종료한 뒤 research.db와 자산 ZIP을 복원합니다. 스키마/버전도 보관하세요. CSV 내보내기는 앱에 제공됩니다. Semantic/Vector search, LLM 보조분석, citation/case graph, 번역, 알림, cloud 인증, Zotero/BibTeX/Excel은 향후 확장 항목이며 현재 기능으로 표시하지 않습니다.
