# Global Legal Research — Daily

등록 상태: 미등록. 이 파일은 UI 입력 지침입니다.

- Name: Global Legal Research — Daily
- Schedule: 월~금 07:00 Asia/Seoul
- Working Directory (cloud): /workspace/legal
- Working Directory (Windows): 설치한 legal 폴더의 절대경로

## Prompt

AGENTS.md와 config/topics.md, sources.md, taxonomy.md, scoring.md, reporting.md를 읽고 database/research.db를 조회한다. 기존 checkout을 사용하고 worktree를 생성하지 않는다. TEST_DATA를 실제 자료로 쓰지 않는다. paywall/로그인/robots/접근통제를 우회하지 않는다. 날짜·기관·사건번호·DOI를 추측하지 않는다. 실패는 logs와 errors에 기록한다. 자료가 없으면 억지로 채우지 않는다. Python CLI와 research.services.register를 사용하며 sqlite를 임의로 덮어쓰지 않는다.
직전 collection_runs 이후 Korea / US / UK / Japan / Global과 Core 1~7을 조사한다. KoFIU, FinCEN, FATF, OFAC, FCA, Japan FSA를 반드시 확인하되 접근 실패는 명시한다. 공개 primary source와 발행일을 검증하고 메타데이터를 추출한다. 기존 DB 중복 조회·cross-tagging·UPDATE 관계·근거 있는 100점 평가·합법적 PDF 저장을 수행한다. 사실과 법적 평가를 구분하고 확인되지 않은 항목은 명시한다. research.services.register로 등록하고 research.reporting.daily로 보고서를 생성한다. 최근 7일 검증된 Priority A 중 핵심 3~5건 이하만 선정한다. 수집 상태와 미확인 출처를 함께 보고한다.


## Windows Task Scheduler 대안

프로그램: legal/.venv/Scripts/python.exe (절대경로)
인수: scripts/manage.py daily
시작 위치: legal 폴더 절대경로. UI prompt를 실행하는 Codex 자동화와 달리 이 CLI는 RSS 수집/저장된 분석 기반 보고서만 수행합니다. Windows 시간대를 서울로 설정하고 위 스케줄에 맞춰 등록합니다. 배치파일은 완료 후 pause하므로 작업 스케줄러에는 Python 명령을 직접 사용합니다. PC가 실행 중이어야 합니다.
