import re
import json
import urllib.parse
from logger import setup_logger
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

logger = setup_logger()

HASHTAG_REGEX = r"#(\w+)"
TEST_MAX_RESULTS = None  # zet op None om uit te zetten

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
    return re.findall(r"#(\w+)", text or "")



# -----------------------------
# Bio links + bio text
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
    except:
        return []


async def extract_profile_bio(page):
    try:
        bio_el = page.locator("h2[data-e2e='user-bio']")
        if await bio_el.count() == 0:
            return None
        return (await bio_el.inner_text()).strip()
    except:
        return None


# -----------------------------
# Profile stats
# -----------------------------
async def extract_profile_stats(page):
    try:
        data = await page.evaluate("() => window.__UNIVERSAL_DATA__ || null")

        if not data:
            raw = await page.evaluate(
                "() => document.querySelector('#__UNIVERSAL_DATA_FOR_REHYDRATION__')?.textContent || null"
            )
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
    except:
        return {}


# -----------------------------
# Video parsing helpers
# -----------------------------


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
        if obj.get("id") == str(target_id) and "stats" in obj:
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


# -----------------------------
# Video parsers
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
                "saves": stats.get("collectCount") or stats.get("favoriteCount") or stats.get("bookmarkCount"),
            },
        }
    except:
        return None


def parse_video_from_rehydration(data, target_id=None):
    try:
        scope = data.get("__DEFAULT_SCOPE__", {})
        item = _find_item_struct_by_id(scope, target_id) or _find_item_struct(scope)

        if not item:
            return None

        stats = item.get("stats", {}) or {}

        return {
            "video_id": item.get("id"),
            "description": item.get("desc") or "",
            "hashtags": [h.get("hashtagName") for h in item.get("textExtra", []) if h.get("hashtagName")],
            "create_time": item.get("createTime"),
            "duration": item.get("video", {}).get("duration"),
            "stats": {
                "views": stats.get("playCount") or stats.get("viewCount"),
                "likes": stats.get("diggCount"),
                "comments": stats.get("commentCount"),
                "shares": stats.get("shareCount") or stats.get("repostCount"),
                "saves": stats.get("collectCount") or stats.get("favoriteCount") or stats.get("bookmarkCount"),
            },
        }
    except:
        return None

def strip_hashtags(text: str):
    if not text:
        return text
    return re.sub(r"#\w+", "", text).strip()



# -----------------------------
# DOM video description
# -----------------------------
async def extract_video_description(page):
    try:
        el = page.locator("div[data-e2e='browse-video-desc']")
        if await el.count() == 0:
            return None
        return (await el.inner_text()).strip()
    except:
        return None


# -----------------------------
# Fetch video stats
# -----------------------------
async def fetch_video_stats(context, url, fallback_id=None):
    page = await context.new_page()
    try:
        await page.goto(url, timeout=60000)
        await page.wait_for_timeout(5000)

        dom_desc = await extract_video_description(page)

        data = await page.evaluate("() => window.__UNIVERSAL_DATA__ || null")
        parsed = parse_from_universal_data(data) if data else None
        if parsed:
            parsed["description"] = parsed.get("description") or dom_desc
            return parsed

        raw = await page.evaluate(
            "() => document.querySelector('#__UNIVERSAL_DATA_FOR_REHYDRATION__')?.textContent || null"
        )
        if raw:
            parsed = parse_video_from_rehydration(json.loads(raw), fallback_id)
            if parsed:
                parsed["description"] = parsed.get("description") or dom_desc
                return parsed

        return {
            "video_id": fallback_id,
            "description": dom_desc,
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
                viewport = await page.evaluate("({width: window.innerWidth, height: window.innerHeight})")
                await page.mouse.click(viewport["width"] - 5, viewport["height"] - 5)
            except:
                pass

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

    results = []

    for i, item in enumerate(video_items):
        if TEST_MAX_RESULTS and i >= TEST_MAX_RESULTS:
            break

        video_data = await fetch_video_stats(context, item["href"], item["video_id"])

        bio_links = []
        profile_stats = {}
        profile_bio = None

        if item["username"]:
            profile_page = await context.new_page()
            try:
                await profile_page.goto(f"https://www.tiktok.com/@{item['username']}", timeout=60000)
                await profile_page.wait_for_timeout(3500)

                profile_bio = await extract_profile_bio(profile_page)
                bio_links = await extract_bio_links(profile_page)
                profile_stats = await extract_profile_stats(profile_page)
            finally:
                await profile_page.close()

            # -----------------------------
            # DESCRIPTION + HASHTAGS SPLIT
            # -----------------------------
            raw_desc = video_data.get("description") or item.get("desc") or ""

            # hashtags: eerst JSON, anders fallback regex
            json_hashtags = video_data.get("hashtags") or []
            final_hashtags = json_hashtags if json_hashtags else extract_hashtags(raw_desc)

            # description opschonen (hashtags eruit)
            clean_desc = strip_hashtags(raw_desc)

            results.append({
                "keyword": keyword,
                "video_id": video_data.get("video_id"),
                "video_url": item["href"],
                "desc": clean_desc,
                "views": video_data.get("stats", {}).get("views"),
                "likes": video_data.get("stats", {}).get("likes"),
                "comments": video_data.get("stats", {}).get("comments"),
                "shares": video_data.get("stats", {}).get("shares"),
                "saves": video_data.get("stats", {}).get("saves"),
                "author": item["username"],
                "profile_bio": profile_bio,
                "bio_links": bio_links,
                "profile_stats": profile_stats,
                "hashtags": final_hashtags,
                "create_time": video_data.get("create_time"),
                "duration": video_data.get("duration"),
            })

    print("[DONE]", len(results))
    return results
