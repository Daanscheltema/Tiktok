import re
import json
import urllib.parse
from logger import setup_logger
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

logger = setup_logger()

HASHTAG_REGEX = r"#(\w+)"

# -----------------------------
# TEMP TEST LIMIT (REMOVE AFTER TEST)
# -----------------------------
TEST_MAX_RESULTS = 3  # zet op None om uit te zetten

# -----------------------------
# SELECTORS (leave as-is to avoid changing working flow)
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
# NEW: Extract ONLY bio links
# -----------------------------
async def extract_bio_links(page):
    links = []

    try:
        container = page.locator("div.css-8ak5ua-7937d88b--DivShareLinks")

        if await container.count() == 0:
            return []

        anchors = container.locator("a[data-e2e='user-link']")
        count = await anchors.count()

        for i in range(count):
            a = anchors.nth(i)

            href = await a.get_attribute("href")
            real_url = href

            if "target=" in href:
                try:
                    parsed = urllib.parse.urlparse(href)
                    qs = urllib.parse.parse_qs(parsed.query)
                    target = qs.get("target", [None])[0]
                    if target:
                        real_url = urllib.parse.unquote(target)
                except:
                    pass

            links.append(real_url)

        return list(set(links))

    except Exception as e:
        print(f"[ERROR] extract_bio_links failed: {e}")
        return []


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
# Click first video (kept minimal)
# -----------------------------
async def click_first_video(page):
    print("[INFO] Clicking first video…")
    try:
        first_video = page.locator(FIRST_VIDEO_SELECTOR).first
        await first_video.scroll_into_view_if_needed()
        await first_video.wait_for(state="visible", timeout=5000)
        await first_video.click(timeout=5000, force=True)
        await page.wait_for_timeout(2000)
        print("[INFO] First video opened.")
    except Exception as e:
        print(f"[ERROR] Could not click first video: {e}")
        raise


# -----------------------------
# REAL TikTok scroll
# -----------------------------
async def scroll_until_all_videos_loaded(page, max_videos=500):
    print("[INFO] Starting window scroll for VIDEO tab…")

    await page.wait_for_selector(VIDEO_LIST_SELECTOR, timeout=10000)

    last_count = 0
    stable_rounds = 0
    scroll_round = 0

    while True:
        await page.evaluate("window.scrollBy(0, window.innerHeight)")
        await page.wait_for_timeout(1800)

        scroll_round += 1

        if scroll_round % 2 == 0:
            try:
                viewport = await page.evaluate(
                    "({width: window.innerWidth, height: window.innerHeight})"
                )
                click_x = viewport["width"] - 5
                click_y = viewport["height"] - 5

                await page.mouse.move(click_x - 3, click_y - 3)
                await page.mouse.move(click_x, click_y)
                await page.mouse.click(click_x, click_y)

                print(f"[INFO] Keep-alive click at ({click_x}, {click_y})")
                await page.wait_for_timeout(500)
            except Exception as e:
                print(f"[WARN] Click failed: {e}")

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
# Extract video items
# -----------------------------
async def build_video_items_from_video_tab(page, max_videos=None):
    print("[INFO] Collecting video anchors from VIDEO tab…")

    js = """
    (maxCount) => {
        const cards = Array.from(document.querySelectorAll("#search_video-item-list div[id^='grid-item-container-'], div[data-e2e='search_video-item'], div[data-e2e='search-card']"));
        const out = [];
        for (let i = 0; i < cards.length && (maxCount === null || i < maxCount); i++) {
            try {
                const card = cards[i];
                const a = card.querySelector("a[href*='/video/']");
                const descEl = card.querySelector("[data-e2e='search-card-video-caption'] span");
                const href = a ? a.getAttribute("href") : null;
                const desc = descEl ? descEl.innerText : "";
                out.push({
                    idx: i + 1,
                    href: href,
                    desc: desc
                });
            } catch (e) {}
        }
        return out;
    }
    """

    try:
        max_count_arg = None if max_videos is None else int(max_videos)
        raw_items = await page.evaluate(js, max_count_arg)
    except Exception as e:
        print(f"[ERROR] JS extraction failed: {e}")
        return []

    video_items = []
    for i, it in enumerate(raw_items):
        href = it.get("href")
        if not href:
            print(f"[WARN] extracted card {i} has no href — skipping")
            continue

        if href.startswith("/"):
            href = "https://www.tiktok.com" + href

        try:
            video_id = href.split("/video/")[1].split("?")[0]
        except Exception:
            video_id = None

        username = ""
        if "/@" in href:
            try:
                username = href.split("/@")[1].split("/")[0]
            except:
                username = ""

        desc = it.get("desc") or ""
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
        item = video_detail.get("itemInfo", {}).get("itemStruct", {})

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
            data = await page.evaluate("() => window.__UNIVERSAL_DATA__ || null")
            parsed = parse_from_universal_data(data) if data else None
            if parsed:
                return parsed
        except:
            pass

        try:
            sigi_text = await page.evaluate(
                "() => document.querySelector('#SIGI_STATE')?.innerText || null"
            )
            if sigi_text:
                parsed = parse_from_sigi_state(json.loads(sigi_text), fallback_video_id)
                if parsed:
                    return parsed
        except:
            pass

        return {"video_id": fallback_video_id, "stats": {}}

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

    await click_videos_tab(search_page)
    await scroll_until_all_videos_loaded(search_page, max_videos or 200)

    # Debug info
    try:
        current_url = await search_page.url
    except Exception:
        current_url = "ERROR_READING_URL"
    print(f"[DEBUG] After scroll, page.url = {current_url}")

    try:
        cards = search_page.locator(VIDEO_LIST_SELECTOR)
        card_count = await cards.count()
    except Exception as e:
        card_count = -1
        print(f"[ERROR] Could not count cards: {e}")

    print(f"[DEBUG] cards.count() = {card_count}")

    for i in range(min(10, max(0, card_count))):
        try:
            href = await cards.nth(i).locator("a[href*='/video/']").first.get_attribute("href")
        except Exception as e:
            href = f"ERROR: {e}"
        print(f"[DEBUG] card {i} href = {href}")

    try:
        overlays = await search_page.locator("div[role='dialog'], div[class*='overlay'], div[class*='modal']").count()
    except Exception:
        overlays = 0
    print(f"[DEBUG] overlays/modals found = {overlays}")

    if overlays > 0:
        try:
            o = search_page.locator("div[role='dialog'], div[class*='overlay'], div[class*='modal']").first
            snippet = (await o.inner_html())[:1000]
            print("[DEBUG] overlay outerHTML snippet:", snippet)
        except Exception:
            pass

    # Build items
    video_items = await build_video_items_from_video_tab(search_page, max_videos)

    # Test stats on first item
    if video_items:
        test_href = video_items[0].get("href")
        print("[DEBUG] Testing fetch_video_stats on first collected href:", test_href)
        try:
            td = await fetch_video_stats(context, test_href, video_items[0].get("video_id"))
            print("[DEBUG] fetch_video_stats returned keys:", list(td.keys()))
        except Exception as e:
            print("[ERROR] fetch_video_stats test failed:", e)
    else:
        print("[DEBUG] No video_items collected to test fetch_video_stats.")

    # -----------------------------
    # WARM-UP CLICK REMOVED HERE
    # -----------------------------

    results = []

    for i, item in enumerate(video_items):

        if TEST_MAX_RESULTS is not None and i >= TEST_MAX_RESULTS:
            print(f"[TEST] Max test results reached ({TEST_MAX_RESULTS}) — stopping early.")
            break

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

                bio_links = await extract_bio_links(profile_page)

                await profile_page.close()
            except Exception as e:
                print(f"[WARN] Failed to extract bio links for {username}: {e}")
                pass

        results.append({
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
        })

        print(f"[OK] VIDEO_OK | idx={idx}")

    print(f"[SEARCH_DONE] keyword={keyword} | results={len(results)}")
    return results
