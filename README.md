# 테라쎄 인스타그램 자동 게시

terrasse.official 인스타그램 게시물을 매일 오전 9시(한국 시간)에 자동으로 올립니다.

- `schedule.json` — 날짜별 게시물(사진, 캡션). `hold: true`는 정보 보완 전까지 올리지 않음
- `images/` — 게시용 사진
- `posted.json` — 게시된 기록(자동 생성)
- `post.py`, `.github/workflows/post.yml` — 게시 스크립트와 예약 실행 설정

토큰은 저장소 Settings → Secrets and variables → Actions의 `IG_TOKEN`에만 저장합니다.
