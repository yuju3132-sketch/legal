# 검증 기록 — 2026-10-13 (Asia/Seoul)

- Python 3.12.14 / Streamlit 1.50.0 / Linux 클라우드에서 실행했습니다.
- `python -m pytest -q`: **58 passed**. 12개 화면 각각 빈 DB / TEST_DATA 임시 DB로 실행, 카드 상세 이동, 화면에서 수동 등록·점수 검토 저장을 확인했습니다.
- DB 생성/재초기화, 등록, URL/DOI/사건번호/문서번호/hash 중복, UPDATE 관계, 교차태그, 점수 경계, 통합검색과 필터, 보고서 검색, Daily 중복보고 제한, Weekly 19개 섹션, 0건, 미검증 제외, 연구주제 근거 조건을 확인했습니다.
- PDF는 TEST_DATA blank PDF로 metadata/hash/archive를 검증했습니다. 실제 법률 PDF를 다운로드한 것은 아닙니다.
- 잘못된 URL·사설 주소·피드 파싱·원문 제목/날짜 불일치·mock timeout·수집 실패 지속·사용자 분석 보존을 확인했습니다.
- 실제 Streamlit 서버 실행: `/` 및 `/_stcore/health` HTTP 200, health 본문 `ok`. 화면 렌더링은 Streamlit AppTest로 검사했으며 실제 브라우저 픽셀/모바일 화면 검사는 하지 않았습니다.
- `bash scripts/cloud_setup.sh`, `pip check`, DB initialize, offline Daily, Weekly, backup을 실제 실행했습니다. DB 및 백업 `PRAGMA integrity_check` = `ok`, 자산 ZIP 무결성 통과.
- 실제 수집을 두 차례 시도했습니다. 첫 번째 로컬 DNS 실패 이후 HTTPS 프록시를 사용하는 경로로 수정했으며, 직접 요청에서 프록시 CONNECT `403 Forbidden`을 확인했습니다. 수집 결과 PARTIAL, 출처 4곳 실패, **실제 자료 0건 / 실제 PDF 0건**. 이를 접근통제 우회로 해결하지 않았습니다.
- 운영 DB는 비어 있고 TEST_DATA는 테스트 파일/임시 DB에만 있습니다. 62개 출처 등록은 현재 접속·공식 페이지 검증 완료를 뜻하지 않습니다.
- 클라우드 설정 초안에 install_script, start_skill, 네트워크 도메인 8개를 저장했습니다. 적용·게시·새 작업에서 복원은 검증하지 않았습니다. 환경 설정에서 변경을 검토·저장하고 Publish한 뒤 실제 수집을 다시 실행해야 합니다.
- Windows `.bat` 파일은 작성했지만 Windows에서 실행하지 않았습니다. Codex 자동화는 실제 등록하지 않았고 UI 입력용 완성된 문서를 제공합니다.

현재 이용 가능한 기능: 로컬 DB·검색·수동 검증/분석·점수 검토·관계·Daily/Weekly 초안·앱·백업. 남은 작업: 네트워크 허용 적용 후 라이브 수집 재검증, 한국/일본 등 나머지 기관의 개별 수집 adapter, 심층 법적 분석을 위한 연구자 검토, Windows 실기기 확인. 전체 출처 자동 조사 완료나 완전한 환경 준비 완료로 해석하지 마세요.


## 자동 수집 개선 — 2026-10-13

Windows 사용자 계정의 예약 등록/조회/갱신/해제 코드, Daily/Weekly/로그인 보완, 동시 실행 방지, 기간별 중복 실행 방지, 실패 상태/재시도, Dashboard 자동 실행 상태, 평가 대기 자료의 Daily 목록을 추가했습니다. setup.bat는 설치 완료 후 예약 등록을 시도합니다. 기존 설치는 enable_auto.bat 한 번으로 등록합니다. 실제 Windows 등록은 Linux 환경에서 수행하지 않았으며, mock 단위 테스트와 Microsoft 공식 XML 스키마 검증은 Windows 실기기 검증을 대신하지 않습니다. 네트워크 접근·자료 수집 범위의 기존 제한은 그대로입니다.

자동화 개선 후 전체 pytest **86 passed**. Daily/Weekly/Logon 예약 XML 3종 모두 Microsoft 공식 Task Scheduler XSD를 통과했습니다. 공식 스키마의 버전/트리거 순서 제약을 반영했습니다. 실제 Linux worker로 별도 한글·공백 데이터 경로에서 Weekly subprocess와 상태 파일 저장도 실행 확인했습니다. 예약 등록/갱신/해제·누락/비활성 작업·시간대·재시도·작업 잠금은 mock/단위 테스트 범위이며 Windows 실기기 예약 등록은 미검증입니다.
