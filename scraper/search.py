import re
import json
from logger import setup_logger
from scraper.user import scrape_user_single_tab
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

logger = setup_logger()

HASHTAG_REGEX = r"#(\w+)"

# -----------------------------
# SELECTORS
# -----------------------------
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
# Click Videos tab
# -----------------------------
async def click_videos_tab(page):
    print("[INFO] Clicking Videos tab…")
    try:
        locator = page.locator(VIDEOS_TAB_SELECTOR).first
        await locator.click(timeout=5000)
        await page.wait_for_timeout(800)
        print("[INFO] Videos tab clicked.")
    except Exception as e:
        print(f"[ERROR] Could not click Videos tab: {e}")
        raise


# -----------------------------
# Click first video
# -----------------------------
async def click_first_video(page):
    print("[INFO] Clicking first video…")
    try:
        first_video = page.locator(FIRST_VIDEO_SELECTOR).first
        await first_video.click(timeout=5000)
        await page.wait_for_timeout(2000)
        print("[INFO] First video opened.")
    except Exception as e:
        print(f"[ERROR] Could not click first video: {e}")
        raise


# -----------------------------
# REAL TikTok scroll (Videos tab)
# -----------------------------
async def scroll_until_all_videos_loaded(page, max_videos=500):
    print("[INFO] Starting window scroll for VIDEO tab…")

    # Wacht tot de lijst er is
    await page.wait_for_selector(VIDEO_LIST_SELECTOR, timeout=10000)

    last_count = 0
    stable_rounds = 0

    while True:
        # Scroll in stappen zoals een echte gebruiker
        await page.evaluate("window.scrollBy(0, window.innerHeight)")
        await page.wait_for_timeout(1800)

        cards = page.locator(VIDEO_LIST_SELECTOR)
        count = await cards.count()

        print(f"[INFO] Loaded {count} videos…")

        if count >= max_videos:
            print("[INFO] max_videos reached.")
            break

        if count == last_count:
            stable_rounds += 1
        else:
            stable_rounds = 0

        last_count = count

        if stable_rounds >= 5:
            print("[INFO] No new videos loaded — stopping scroll.")
            break

    print(f"[INFO] Final video count: {last_count}")
    return last_count


# -----------------------------
# Extract video items (Videos tab)
# -----------------------------
async def build_video_items_from_video_tab(page, max_videos=None):
    print("[INFO] Collecting video anchors from VIDEO tab…")

    cards = page.locator(VIDEO_LIST_SELECTOR)
    total = await cards.count()
    print(f"[INFO] Found {total} cards.")

    limit = total if max_videos is None else min(total, max_videos)
    video_items = []

    for i in range(limit):
        card = cards.nth(i)
        link = card.locator("a[href*='/video/']").first

        href = await link.get_attribute("href")
        if href.startswith("/"):
            href = "https://www.tiktok.com" + href

        video_id = href.split("/video/")[1].split("?")[0]

        username = ""
        if "/@" in href:
            username = href.split("/@")[1].split("/")[0]

        desc = await safe_text(card.locator("[data-e2e='search-card-video-caption'] span"))
        hashtags_search = extract_hashtags(desc)

        video_items.append({
            "idx": i + 1,
            "href": href,
            "video_id": video_id,
            "desc": desc,
            "username": username,
            "views_search": "",
            "hashtags_search": hashtags_search,
        })

    print(f"[INFO] VIDEO tab produced {len(video_items)} items.")
    return video_items


# -----------------------------
# JSON parsers
# -----------------------------
def parse_from_universal_data(data):
    try:
        scope = data.get("__DEFAULT_SCOPE__", {})
        video_detail = scope.get("webapp.video-detail", {})
        item_info = video_detail.get("itemInfo", {})
        item = item_info.get("itemStruct", {})

        if not item:
            return None

        stats = item.get("stats", {}) or {}
        author = item.get("author", {}) or {}
        music = item.get("music", {}) or {}

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
            "author_info": {
                "username": author.get("uniqueId"),
                "nickname": author.get("nickname"),
                "avatar": author.get("avatarThumb"),
                "followers": author.get("followerCount"),
                "following": author.get("followingCount"),
                "heart": author.get("heart"),
            },
            "music_info": {
                "id": music.get("id"),
                "title": music.get("title"),
                "author": music.get("authorName"),
                "play_url": music.get("playUrl"),
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
        author = item.get("author", {}) or {}
        music = item.get("music", {}) or {}

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
            "author_info": {
                "username": author.get("uniqueId"),
                "nickname": author.get("nickname"),
                "avatar": author.get("avatarThumb"),
                "followers": author.get("followerCount"),
                "following": author.get("followingCount"),
                "heart": author.get("heart"),
            },
            "music_info": {
                "id": music.get("id"),
                "title": music.get("title"),
                "author": music.get("authorName"),
                "play_url": music.get("playUrl"),
            },
        }
    except:
        return None


# -----------------------------
# Fetch video stats
# -----------------------------
async def fetch_video_stats(context, video_url, fallback_video_id=None):
    page = await context.new_page()
    try:
        print(f"[INFO] Fetching stats for video: {video_url}")
        await page.goto(video_url, timeout=60000)
        await page.wait_for_timeout(3000)

        try:
            universal_data = await page.evaluate("() => window.__UNIVERSAL_DATA__ || null")
            if universal_data:
                parsed = parse_from_universal_data(universal_data)
                if parsed:
                    return parsed
        except:
            pass

        try:
            sigi_text = await page.evaluate("() => document.querySelector('#SIGI_STATE')?.innerText || null")
            if sigi_text:
                parsed = parse_from_sigi_state(json.loads(sigi_text), fallback_video_id)
                if parsed:
                    return parsed
        except:
            pass

        return {
            "video_id": fallback_video_id,
            "description": "",
            "hashtags": [],
            "create_time": None,
            "duration": None,
            "stats": {},
            "author_info": {},
            "music_info": {},
        }

    finally:
        await page.close()


# -----------------------------
# MAIN SEARCH FUNCTION
# -----------------------------
async def search_keyword(search_page, keyword: str, max_videos=None, max_profiles=None):
    print(f"\n[SEARCH] Starting search for keyword: {keyword}")

    context = search_page.context
    await search_page.goto(f"https://www.tiktok.com/search?q={keyword}", timeout=60000)
    await search_page.wait_for_timeout(3000)

    # 1) Klik Video’s tab
    await click_videos_tab(search_page)

    # 2) Scroll eerst ALLE video’s in
    await scroll_until_all_videos_loaded(search_page, max_videos or 200)

    # 3) Extract video items
    video_items = await build_video_items_from_video_tab(search_page, max_videos)

    print(f"[INFO] Total video items to deep-scrape: {len(video_items)}")

    # 4) Klik eerste video (variant C)
    await click_first_video(search_page)
    await search_page.go_back()
    await search_page.wait_for_timeout(1500)

    results = []

    # 5) Deep scrape
    for item in video_items:
        idx = item["idx"]
        href = item["href"]
        username = item["username"]

        print(f"[VIDEO] Processing {idx}/{len(video_items)} | url={href}")

        video_data = await fetch_video_stats(context, href, item["video_id"])

        bio_links = []
        if username:
            try:
                profile_page = await context.new_page()
                await profile_page.goto(f"https://www.tiktok.com/@{username}", timeout=60000)
                await profile_page.wait_for_timeout(2000)
                extracted = await scrape_user_single_tab(profile_page)
                if extracted:
                    bio_links = list(set(extracted))
                await profile_page.close()
            except:
                pass

        result = {
            "keyword": keyword,
            "video_id": video_data.get("video_id"),
            "video_url": href,
            "desc": video_data.get("description") or item["desc"],
            "views": video_data.get("stats", {}).get("views"),
            "likes": video_data.get("stats", {}).get("likes"),
            "comments": video_data.get("stats", {}).get("comments"),
            "shares": video_data.get("stats", {}).get("shares"),
            "saves": video_data.get("stats", {}).get("saves"),
            "downloads": video_data.get("stats", {}).get("downloads"),
            "forwards": video_data.get("stats", {}).get("forwards"),
            "author": username,
            "bio_links": bio_links,
            "hashtags": video_data.get("hashtags"),
            "create_time": video_data.get("create_time"),
            "duration": video_data.get("duration"),
        }

        results.append(result)
        print(f"[OK] VIDEO_OK | idx={idx} | id={result['video_id']}")

    print(f"[SEARCH_DONE] keyword={keyword} | results={len(results)}")
    return results
