import re
import json
import urllib.parse
from logger import setup_logger
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

logger = setup_logger()

HASHTAG_REGEX = r"#(\w+)"
TEST_MAX_RESULTS = 3  # zet op None om uit te zetten

VIDEOS_TAB_SELECTOR = (
    "button[data-testid='tux-web-tab-bar'] span:has-text(\"Video's\"), "
    "button[data-testid='tux-web-tab-bar'] span:has-text('Videos'), "
    "button[data-testid='tux-web-tab-bar'] span:has-text('Video')"
)

FIRST_VIDEO_SELECTOR = "#grid-item-container-0 a[href*='/video/']"
VIDEO_LIST_SELECTOR = "#search_video-item-list div[id^='grid-item-container-']"


# -----------------------------
# Helpers
# -----------------------------
async def safe_text(el):
    if not el:
        return ""
    try:
        return await el.inner_text()
    except:
        return ""


def extract_hashtags(text: str):
    return re.findall(HASHTAG_REGEX, text or "")


# -----------------------------
# Bio links
# -----------------------------
async def extract_bio_links(page):
    try:
        container = page.locator("div.css-8ak5ua-7937d88b--DivShareLinks")
        if await container.count() == 0:
            return []

        anchors = container.locator("a[data-e2e='user-link']")
        out = []

        for i in range(await anchors.count()):
            href = await anchors.nth(i).get_attribute("href")
            if not href:
                continue

            if "target=" in href:
                try:
                    parsed = urllib.parse.urlparse(href)
                    qs = urllib.parse.parse_qs(parsed.query)
                    href = urllib.parse.unquote(qs.get("target", [href])[0])
                except:
                    pass

            out.append(href)

        return list(set(out))

    except Exception as e:
        print("[BIO_ERROR]", e)
        return []


# -----------------------------
# Profile stats
# -----------------------------
async def extract_profile_stats(page):
    print("[PROFILE_DEBUG] extracting profile stats")

    try:
        data = await page.evaluate("() => window.__UNIVERSAL_DATA__ || null")

        if not data:
            raw = await page.evaluate("""
                () => document.querySelector('#__UNIVERSAL_DATA_FOR_REHYDRATION__')?.textContent || null
            """)
            if raw:
                data = json.loads(raw)

        if not data:
            return {}

        scope = data.get("__DEFAULT_SCOPE__", {})

        user_block = None
        for k, v in scope.items():
            if "user" in k.lower():
                user_block = v
                break

        if not user_block:
            return {}

        user_info = user_block.get("userInfo") or {}
        stats = user_info.get("stats") or {}
        user = user_info.get("user") or {}

        return {
            "nickname": user.get("nickname"),
            "verified": user.get("verified"),
            "followers": stats.get("followerCount"),
            "following": stats.get("followingCount"),
            "likes": stats.get("heartCount"),
            "videos": stats.get("videoCount"),
        }

    except Exception as e:
        print("[PROFILE_STATS_ERROR]", e)
        return {}


# -----------------------------
# Video stats parsers
# -----------------------------
def parse_from_universal_data(data):
    try:
        scope = data.get("__DEFAULT_SCOPE__", {})
        item = scope.get("webapp.video-detail", {}) \
            .get("itemInfo", {}) \
            .get("itemStruct", {})

        if not item:
            return None

        stats = item.get("stats", {}) or {}
        print("[VIDEO_DEBUG] stats keys:", list(stats.keys())[:30])

        return {
            "video_id": item.get("id"),
            "description": item.get("desc", ""),
            "hashtags": [h.get("hashtagName") for h in item.get("textExtra", []) if h.get("hashtagName")],
            "create_time": item.get("createTime"),
            "duration": item.get("video", {}).get("duration"),
            "stats": {
                "views": stats.get("playCount"),
                "likes": stats.get("diggCount"),
                "comments": stats.get("commentCount"),
                "shares": stats.get("shareCount"),
                "saves": stats.get("collectCount"),
                "downloads": stats.get("downloadCount"),
                "forwards": stats.get("forwardCount"),
            },
        }
    except:
        return None


def parse_from_sigi_state(data, video_id):
    try:
        item = data.get("ItemModule", {}).get(str(video_id))
        if not item:
            return None

        stats = item.get("stats", {}) or {}

        return {
            "video_id": item.get("id"),
            "description": item.get("desc", ""),
            "hashtags": [h.get("hashtagName") for h in item.get("textExtra", []) if h.get("hashtagName")],
            "create_time": item.get("createTime"),
            "duration": item.get("video", {}).get("duration"),
            "stats": {
                "views": stats.get("playCount"),
                "likes": stats.get("diggCount"),
                "comments": stats.get("commentCount"),
                "shares": stats.get("shareCount"),
                "saves": stats.get("collectCount"),
                "downloads": stats.get("downloadCount"),
                "forwards": stats.get("forwardCount"),
            },
        }
    except:
        return None


def _find_item_struct(obj):
    if isinstance(obj, dict):
        if {"id", "desc", "video", "stats"} <= set(obj.keys()):
            return obj
        for v in obj.values():
            found = _find_item_struct(v)
            if found:
                return found
    elif isinstance(obj, list):
        for it in obj:
            found = _find_item_struct(it)
            if found:
                return found
    return None

def _find_item_struct_by_id(obj, target_id: str):
    if isinstance(obj, dict):
        if obj.get("id") == str(target_id) and "stats" in obj and "video" in obj:
            return obj
        for v in obj.values():
            found = _find_item_struct_by_id(v, target_id)
            if found:
                return found
    elif isinstance(obj, list):
        for it in obj:
            found = _find_item_struct_by_id(it, target_id)
            if found:
                return found
    return None



def parse_video_from_rehydration(data, target_id=None):
    try:
        scope = data.get("__DEFAULT_SCOPE__", {})

        item = None

        # 1) Eerst: exact match op video id (meest betrouwbaar)
        if target_id:
            item = _find_item_struct_by_id(scope, str(target_id))

        # 2) fallback: oude zoekmethode
        if not item:
            item = _find_item_struct(scope) or _find_item_struct(data)

        if not item:
            return None

        stats = item.get("stats", {}) or {}

        # ✅ DIT is de debug die we nodig hebben
        print("[VIDEO_DEBUG] item id:", item.get("id"), "| stats keys:", list(stats.keys())[:40])

        # Key mapping voor varianten
        views = stats.get("playCount") or stats.get("viewCount")
        likes = stats.get("diggCount") or stats.get("likeCount")
        comments = stats.get("commentCount")
        shares = stats.get("shareCount") or stats.get("repostCount")
        saves = stats.get("collectCount") or stats.get("favoriteCount")

        return {
            "video_id": item.get("id"),
            "description": item.get("desc") or "",
            "hashtags": [h.get("hashtagName") for h in item.get("textExtra", []) if h.get("hashtagName")],
            "create_time": item.get("createTime"),
            "duration": item.get("video", {}).get("duration"),
            "stats": {
                "views": views,
                "likes": likes,
                "comments": comments,
                "shares": shares,
                "saves": saves,
                "downloads": stats.get("downloadCount"),
                "forwards": stats.get("forwardCount"),
            },
        }
    except:
        return None

# -----------------------------
# Fetch video stats (safe)
# -----------------------------
async def fetch_video_stats(context, url, fallback_id=None):
    page = await context.new_page()
    try:
        await page.goto(url, timeout=60000)
        await page.wait_for_timeout(5000)
        await page.wait_for_timeout(1500)

        # ---- DEBUG: verify what is present on the video page ----
        try:
            has_universal = await page.evaluate("() => !!window.__UNIVERSAL_DATA__")
            has_sigi = await page.evaluate("() => !!document.querySelector('#SIGI_STATE')")
            has_rehydration = await page.evaluate(
                "() => !!document.querySelector('#__UNIVERSAL_DATA_FOR_REHYDRATION__')"
            )
            print("[VIDEO_DEBUG] universal:", has_universal, "| sigi:", has_sigi, "| rehydration:", has_rehydration)
        except Exception as e:
            print("[VIDEO_DEBUG] check failed:", e)

        # universal first
        data = await page.evaluate("() => window.__UNIVERSAL_DATA__ || null")
        parsed = parse_from_universal_data(data) if data else None
        if parsed:
            return parsed

        # ---- FIX: try rehydration BEFORE sigi ----
        try:
            raw = await page.evaluate(
                "() => document.querySelector('#__UNIVERSAL_DATA_FOR_REHYDRATION__')?.textContent || null"
            )
            if raw:
                parsed_rehydration = parse_video_from_rehydration(json.loads(raw), target_id=fallback_id)
                if parsed_rehydration:
                    return parsed_rehydration
        except Exception as e:
            print("[VIDEO_DEBUG] rehydration parse failed:", e)

        # sigi after
        sigi = await page.evaluate("() => document.querySelector('#SIGI_STATE')?.innerText || null")
        if sigi:
            parsed = parse_from_sigi_state(json.loads(sigi), fallback_id)
            if parsed:
                return parsed

        return {
            "video_id": fallback_id,
            "description": "",
            "hashtags": [],
            "create_time": None,
            "duration": None,
            "stats": {}
        }

    finally:
        await page.close()


# -----------------------------
# Scroll
# -----------------------------
async def scroll_until_all_videos_loaded(page, max_videos=500):
    await page.wait_for_selector(VIDEO_LIST_SELECTOR, timeout=10000)

    last = 0
    stable = 0
    round_i = 0

    while True:
        await page.evaluate("window.scrollBy(0, window.innerHeight)")
        await page.wait_for_timeout(1500)

        round_i += 1

        if round_i % 2 == 0:
            try:
                viewport = await page.evaluate(
                    "({width: window.innerWidth, height: window.innerHeight})"
                )
                x = viewport["width"] - 5
                y = viewport["height"] - 5

                await page.mouse.move(x - 3, y - 3)
                await page.mouse.move(x, y)
                await page.mouse.click(x, y)

                print("[SCROLL] keep-alive click")
                await page.wait_for_timeout(400)

            except Exception as e:
                print("[SCROLL_WARN] click failed:", e)

        count = await page.locator(VIDEO_LIST_SELECTOR).count()
        print("[SCROLL] videos:", count)

        if count >= max_videos:
            break

        if count == last:
            stable += 1
        else:
            stable = 0

        last = count

        if stable >= 5:
            break


# -----------------------------
# Build video list
# -----------------------------
async def build_video_items_from_video_tab(page, max_videos=None):
    raw = await page.evaluate("""
    (maxCount) => {
        const cards = Array.from(document.querySelectorAll("#search_video-item-list div[id^='grid-item-container-']"));
        return cards.slice(0, maxCount || cards.length).map((c,i)=>({
            idx:i+1,
            href:c.querySelector("a[href*='/video/']")?.getAttribute("href"),
            desc:c.innerText || ""
        }));
    }
    """, max_videos)

    out = []
    seen = set()

    for it in raw:
        href = it["href"]
        if not href:
            continue
        if href.startswith("/"):
            href = "https://www.tiktok.com" + href

        vid = href.split("/video/")[1].split("?")[0]

        if vid in seen:
            continue
        seen.add(vid)

        user = href.split("/@")[1].split("/")[0]

        out.append({
            "idx": it["idx"],
            "href": href,
            "video_id": vid,
            "desc": it["desc"],
            "username": user
        })

    print("[INFO] unique videos:", len(out))
    return out


# -----------------------------
# MAIN
# -----------------------------
async def search_keyword(search_page, keyword, max_videos=None, max_profiles=None):

    context = search_page.context

    await search_page.goto(f"https://www.tiktok.com/search?q={keyword}")
    await search_page.wait_for_timeout(3000)

    await search_page.locator(VIDEOS_TAB_SELECTOR).first.click()
    await scroll_until_all_videos_loaded(search_page, max_videos or 200)

    video_items = await build_video_items_from_video_tab(search_page, max_videos)

    # ---- PATCH: remove duplicate video_ids ----
    seen_ids = set()
    unique_items = []

    for v in video_items:
        vid = v.get("video_id")
        if vid and vid not in seen_ids:
            seen_ids.add(vid)
            unique_items.append(v)

    video_items = unique_items
    print(f"[PATCH] unique video_items: {len(video_items)}")

    results = []
    profile_cache = {}

    for i, item in enumerate(video_items):

        if TEST_MAX_RESULTS and i >= TEST_MAX_RESULTS:
            break

        print("[VIDEO]", item["href"])

        video_data = await fetch_video_stats(
            context,
            item["href"],
            item["video_id"]
        )

        if not video_data:
            print("[PATCH] video_data None — using fallback")
            video_data = {
                "video_id": item["video_id"],
                "description": "",
                "hashtags": [],
                "create_time": None,
                "duration": None,
                "stats": {}
            }

        username = item["username"]

        # ---- FIX: always initialize so results.append never breaks ----
        bio_links = []
        profile_stats = {}

        if username:
            profile_page = await context.new_page()
            try:
                print(f"[PROFILE] Opening profile: {username}")

                await profile_page.goto(
                    f"https://www.tiktok.com/@{username}",
                    timeout=60000
                )

                await profile_page.wait_for_timeout(3500)

                has_universal = await profile_page.evaluate(
                    "() => !!window.__UNIVERSAL_DATA__"
                )
                print("[PROFILE_DEBUG] has window.__UNIVERSAL_DATA__:", has_universal)
                print("[PROFILE_DEBUG] URL:", profile_page.url)

                bio_links = await extract_bio_links(profile_page)

                try:
                    profile_stats = await extract_profile_stats(profile_page)
                except Exception as e:
                    print("[PATCH] profile stats failed:", e)
                    profile_stats = {}

            except Exception as e:
                print(f"[WARN] Profile scrape failed for {username}: {e}")

            finally:
                await profile_page.close()

        results.append({
            "keyword": keyword,
            "video_id": video_data.get("video_id"),
            "video_url": item["href"],
            "desc": video_data.get("description") or item["desc"],
            "views": video_data.get("stats", {}).get("views"),
            "likes": video_data.get("stats", {}).get("likes"),
            "comments": video_data.get("stats", {}).get("comments"),
            "shares": video_data.get("stats", {}).get("shares"),
            "author": username,
            "bio_links": bio_links,
            "profile_stats": profile_stats,
            "hashtags": video_data.get("hashtags"),
            "create_time": video_data.get("create_time"),
            "duration": video_data.get("duration"),
        })

    print("[DONE]", len(results))
    return results
