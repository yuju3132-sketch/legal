# Global Legal Research — Weekly

Codex AI 자동화: 미등록. 아래 Prompt는 AI 자동화 UI 입력 지침입니다.

Windows 예약: `setup.bat` 또는 `enable_auto.bat`가 Daily/Weekly/로그인 보완 작업을 등록합니다. 이 클라우드에서는 Windows 예약을 실제 등록하지 않았으며 사용자 PC의 Dashboard에서 확인합니다. 매일 배치파일을 수동으로 실행할 필요는 없습니다.

- Name: Global Legal Research — Weekly
- Schedule: 금요일 18:00 Asia/Seoul
- Working Directory (cloud): /workspace/legal
- Working Directory (Windows): 설치한 legal 폴더의 절대경로

## Prompt

AGENTS.md와 config/topics.md, sources.md, taxonomy.md, scoring.md, reporting.md를 읽고 database/research.db를 조회한다. 기존 checkout을 사용하고 worktree를 생성하지 않는다. TEST_DATA를 실제 자료로 쓰지 않는다. paywall/로그인/robots/접근통제를 우회하지 않는다. 날짜·기관·사건번호·DOI를 추측하지 않는다. 실패는 logs와 errors에 기록한다. 자료가 없으면 억지로 채우지 않는다. Python CLI와 research.services.register를 사용하며 sqlite를 임의로 덮어쓰지 않는다.
해당 주 Daily와 DB Priority A/B를 읽고 핵심 원문을 재검증한다. 사실과 법적 평가를 분리하여 분야별·국가별 비교법 분석을 수행하고 analysis 필드에 근거를 기록한다. AML×내부통제/이사책임/제재, 제재×국제거래/지급/CISG, 회사법×이사책임, 자본시장×내부통제, 기업금융×도산을 분석한다. Daily 단순 합본을 금지한다. Top 5, Research Gaps, Must Read Top 3, 근거 있는 Potential Research Topics를 작성한다. 연구 아이디어는 검증자료 2건 이상이 있을 때만 research.services.create_idea로 저장한다. research.reporting.weekly를 실행하고 자동 초안의 미확인 분석을 원문 근거로 보완한다.


## Windows Task Scheduler 대안

프로그램: legal/.venv/Scripts/python.exe (절대경로)
인수: scripts/manage.py weekly
시작 위치: legal 폴더 절대경로. UI prompt를 실행하는 Codex 자동화와 달리 이 CLI는 RSS 수집/저장된 분석 기반 보고서만 수행합니다. Windows 시간대를 서울로 설정하고 위 스케줄에 맞춰 등록합니다. 배치파일은 완료 후 pause하므로 작업 스케줄러에는 Python 명령을 직접 사용합니다. PC가 실행 중이어야 합니다.


## 간편 Windows 예약

기존 설치는 enable_auto.bat를 한 번 실행하세요. PC가 켜져 있고 로그인된 동안 앱을 닫아도 예약 실행됩니다. 자세한 조건과 해제 방법은 README의 자동화 절을 참고하세요.
