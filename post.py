"""테라쎄 인스타그램 자동 게시 스크립트.

schedule.json에서 오늘(한국 시간) 날짜의 게시물을 찾아 Instagram Graph API로 올린다.
- hold: true 인 게시물은 올리지 않는다 (정보 보완 필요).
- 이미 올린 게시물은 posted.json에 기록되어 다시 올리지 않는다.

환경 변수
  IG_TOKEN    시스템 사용자 액세스 토큰 (GitHub Secrets)
  IG_USER_ID  인스타그램 계정 ID
  MODE        post(기본) | check  — check는 컨테이너만 만들어 보고 게시하지 않음
  CODE        특정 게시물 코드를 지정할 때 (예: V1111). 비우면 오늘 날짜 게시물

게시물에 "type": "story" 가 있으면 피드가 아닌 스토리로 올린다 (사진마다 스토리 1장, 캡션 없음).
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://graph.facebook.com/v24.0"
REPO = os.environ.get("GITHUB_REPOSITORY", "kskage-git/terrasse-insta")
BRANCH = os.environ.get("GITHUB_REF_NAME", "main")
IMG_BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/images/"
KST = timezone(timedelta(hours=9))

TOKEN = os.environ["IG_TOKEN"]
USER_ID = os.environ.get("IG_USER_ID", "17841478285216963")
MODE = os.environ.get("MODE", "post") or "post"
CODE = (os.environ.get("CODE") or "").strip()


def call(method, path, params=None):
    params = dict(params or {})
    params["access_token"] = TOKEN
    data = urllib.parse.urlencode(params).encode()
    if method == "GET":
        req = urllib.request.Request(f"{API}/{path}?{data.decode()}")
    else:
        req = urllib.request.Request(f"{API}/{path}", data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace").replace(TOKEN, "***")
        raise SystemExit(f"API 오류 {e.code} ({path}): {body}")


def wait_ready(container_id):
    for _ in range(30):
        st = call("GET", container_id, {"fields": "status_code,status"})
        code = st.get("status_code")
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            raise SystemExit(f"컨테이너 오류: {st}")
        time.sleep(5)
    raise SystemExit("컨테이너 준비 시간 초과")


def create_container(post):
    urls = [IMG_BASE + name for name in post["images"]]
    if len(urls) == 1:
        c = call("POST", f"{USER_ID}/media", {"image_url": urls[0], "caption": post["caption"]})
        wait_ready(c["id"])
        return c["id"]
    children = []
    for u in urls:
        c = call("POST", f"{USER_ID}/media", {"image_url": u, "is_carousel_item": "true"})
        wait_ready(c["id"])
        children.append(c["id"])
    c = call("POST", f"{USER_ID}/media", {
        "media_type": "CAROUSEL",
        "children": ",".join(children),
        "caption": post["caption"],
    })
    wait_ready(c["id"])
    return c["id"]


def publish_story(post):
    """사진마다 스토리 컨테이너를 만들고, post 모드이면 순서대로 게시한다."""
    ids = []
    for name in post["images"]:
        c = call("POST", f"{USER_ID}/media", {"image_url": IMG_BASE + name, "media_type": "STORIES"})
        wait_ready(c["id"])
        ids.append(c["id"])
    if MODE == "check":
        return None
    published = []
    for cid in ids:
        res = call("POST", f"{USER_ID}/media_publish", {"creation_id": cid})
        published.append(res["id"])
        time.sleep(3)
    return published


def main():
    schedule = json.load(open("schedule.json", encoding="utf-8"))
    posted = json.load(open("posted.json", encoding="utf-8")) if os.path.exists("posted.json") else {}
    today = datetime.now(KST).strftime("%Y-%m-%d")

    if CODE:
        todo = [p for p in schedule if p["code"] == CODE]
    else:
        todo = [p for p in schedule if p["date"] == today]

    if not todo:
        print(f"{today}: 올릴 게시물 없음")
        return

    for post in todo:
        if post.get("hold") and not CODE:
            print(f"{post['code']}: 보류(정보 보완 필요) — 건너뜀")
            continue
        if post["code"] in posted and MODE == "post":
            print(f"{post['code']}: 이미 게시됨 ({posted[post['code']]['at']}) — 건너뜀")
            continue
        if post.get("type") == "story":
            print(f"{post['code']}: 스토리 {len(post['images'])}장 컨테이너 생성")
            ids = publish_story(post)
            if ids is None:
                print(f"{post['code']}: 점검 성공 (게시하지 않음)")
                continue
            posted[post["code"]] = {"at": datetime.now(KST).isoformat(timespec="minutes"), "type": "story", "media_ids": ids}
            print(f"{post['code']}: 스토리 게시 완료 ({len(ids)}장)")
            json.dump(posted, open("posted.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            continue
        print(f"{post['code']}: 사진 {len(post['images'])}장 컨테이너 생성")
        cid = create_container(post)
        if MODE == "check":
            print(f"{post['code']}: 점검 성공 (게시하지 않음)")
            continue
        res = call("POST", f"{USER_ID}/media_publish", {"creation_id": cid})
        media_id = res["id"]
        link = call("GET", media_id, {"fields": "permalink"}).get("permalink", "")
        posted[post["code"]] = {"at": datetime.now(KST).isoformat(timespec="minutes"), "media_id": media_id, "permalink": link}
        print(f"{post['code']}: 게시 완료 {link}")
        json.dump(posted, open("posted.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
