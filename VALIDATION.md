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
