# Pinterest → Eagle Harvester (MVP)

Pinterest에서 키워드 기반으로 이미지를 모아, 중복 제거 후 Eagle로 자동 전송하는 수집기입니다.

## 기능
- 키워드별 Pinterest 검색 결과 수집
- `pin_id` 기준 중복 제거 (SQLite)
- Eagle API로 자동 저장 (`addFromURL`)
- 태그 자동 부여 (`키워드 + 기본 태그`)

## 준비물
1. **Eagle 앱 실행 + API 활성화**
   - 기본 API: `http://127.0.0.1:41595`
2. Python 3.10+
3. Pinterest 계정 (로그인 수집 필요 시)

## 설치/실행
```bash
cd projects/pinterest-eagle-harvester
cp .env.example .env
# .env 값 수정
./run.sh
```

## .env 핵심 설정
- `PINTEREST_KEYWORDS`: 쉼표 구분 키워드
- `MAX_PINS_PER_KEYWORD`: 키워드당 최대 수집 수
- `SCROLL_ROUNDS`: 스크롤 횟수 (많을수록 더 수집)
- `EAGLE_API_BASE`: Eagle API 주소
- `EAGLE_TOKEN`: Eagle 토큰(설정한 경우)
- `EAGLE_FOLDER_ID`: 특정 폴더에 저장하고 싶을 때

## 동작 방식
1. Pinterest 로그인(계정 정보가 있으면)
2. 키워드 검색 페이지 스크롤
3. `/pin/{id}` 링크 + 이미지 URL 추출
4. DB에서 중복 검사
5. Eagle API로 저장
6. 저장 성공 시 DB에 기록

## Eagle Plugin 버전 포함
이 레포에는 Eagle 내부에서 바로 쓸 수 있는 플러그인도 포함되어 있습니다.

- 위치: `eagle-plugin/pinterest-bulk-importer`
- 기능: Pinterest 핀 URL/이미지 URL 붙여넣기 → Eagle로 일괄 import

### 플러그인 설치
1. Eagle 앱에서 플러그인 메뉴 열기
2. `eagle-plugin/pinterest-bulk-importer` 폴더를 플러그인으로 추가
3. 플러그인 실행 후 URL 목록 붙여넣기
4. 필요시 API Base/Token/Folder ID 입력 후 가져오기 실행

## 다음 고도화 추천
- 보드/유저 단위 수집 모드 추가
- 이미지 해시 기반 중복 제거(pHash)
- 실패 재시도 큐 + 알림(Discord DM)
- 스케줄 실행(launchd/cron) + 일별 리포트
