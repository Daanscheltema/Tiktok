import re
import json
import time
from logger import setup_logger
from scraper.user import scrape_user_single_tab

logger = setup_logger()

HASHTAG_REGEX = r"#(\w+)"


async def scroll_until_no_new_results(page, max_scrolls=30, wait=1500):
    last_height = 0
    for i in range(max_scrolls):
        await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
        await page.wait_for_timeout(wait)
        height = await page.evaluate("document.body.scrollHeight")
        if height == last_height:
            logger.info(f"🔚 No new results after {i} scrolls")
            break
        last_height = height


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

        description = item.get("desc", "") or ""
        hashtags = [
            h.get("hashtagName")
            for h in item.get("textExtra", [])
            if h.get("hashtagName")
        ]

        return {
            "video_id": item.get("id"),
            "description": description,
            "hashtags": hashtags,
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
    except Exception as e:
        logger.warning(f"UNIVERSAL_PARSE_FAIL | {e}")
        return None


def parse_from_sigi_state(data, video_id):
    try:
        item_module = data.get("ItemModule", {})
        item = item_module.get(str(video_id)) or item_module.get(video_id)
        if not item:
            return None

        stats = item.get("stats", {}) or {}
        author = item.get("author", {}) or {}
        music = item.get("music", {}) or {}

        description = item.get("desc", "") or ""
        hashtags = [
            h.get("hashtagName")
            for h in item.get("textExtra", [])
            if h.get("hashtagName")
        ]

        return {
            "video_id": item.get("id"),
            "description": description,
            "hashtags": hashtags,
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
    except Exception as e:
        logger.warning(f"SIGI_PARSE_FAIL | {e}")
        return None


# -----------------------------
# Video stats in dedicated tab
# -----------------------------
async def fetch_video_stats(context, video_url, fallback_video_id=None):
    page = await context.new_page()
    try:
        await page.goto(video_url, timeout=60000)

        await page.bring_to_front()
        await page.wait_for_timeout(500)

        await page.evaluate("window.scrollTo(0, 300)")
        await page.wait_for_timeout(500)

        await page.wait_for_timeout(4500)

        try:
            universal_data = await page.evaluate("() => window.__UNIVERSAL_DATA__ || null")
        except Exception:
            universal_data = None

        if universal_data:
            parsed = parse_from_universal_data(universal_data)
            if parsed:
                return parsed

        try:
            sigi_text = await page.evaluate(
                "() => document.querySelector('#SIGI_STATE')?.innerText || null"
            )
            if sigi_text:
                sigi_data = json.loads(sigi_text)
                parsed = parse_from_sigi_state(sigi_data, fallback_video_id)
                if parsed:
                    return parsed
        except Exception as e:
            logger.warning(f"SIGI_STATE_READ_FAIL | url={video_url} | {e}")

        stats = {}

        try:
            views_el = await page.query_selector(
                "[data-e2e='video-views'] strong, [data-e2e='video-views']"
            )
            stats["views"] = await views_el.inner_text() if views_el else None
        except Exception:
            stats["views"] = None

        try:
            likes_el = await page.query_selector(
                "strong[data-e2e='like-count'], button[data-e2e='like-icon'] strong"
            )
            stats["likes"] = await likes_el.inner_text() if likes_el else None
        except Exception:
            stats["likes"] = None

        return {
            "video_id": fallback_video_id,
            "description": "",
            "hashtags": [],
            "create_time": None,
            "duration": None,
            "stats": {
                "views": stats.get("views"),
                "likes": stats.get("likes"),
                "comments": None,
                "shares": None,
                "saves": None,
                "downloads": None,
                "forwards": None,
            },
            "author_info": {},
            "music_info": {},
        }

    finally:
        await page.close()


# -----------------------------
# Main search function
# -----------------------------
async def search_keyword(search_page, keyword: str, max_videos=None, max_profiles=None):
    start_time = time.time()
    logger.info(f"SEARCH_START | keyword={keyword}")

    context = search_page.context
    search_url = f"https://www.tiktok.com/search?q={keyword}"

    await search_page.goto(search_url, timeout=60000)
    await search_page.wait_for_timeout(4000)

    await scroll_until_no_new_results(search_page)

    selectors = [
        "div[data-e2e='search-card']",
        "div[data-e2e='search-video-card']",
        "div[id^='grid-item-container-']",
        "div[data-e2e='search-item']",
    ]

    cards = []
    for sel in selectors:
        cards = await search_page.query_selector_all(sel)
        if cards:
            logger.info(f"Selector matched: {sel}")
            break

    logger.info(f"CARDS_FOUND | keyword={keyword} | count={len(cards)}")

    video_items = []
    for idx, card in enumerate(cards, start=1):
        link_el = await card.query_selector("a[href*='/video/']")
        href = await link_el.get_attribute("href") if link_el else None
        if not href:
            continue
        if href.startswith("/"):
            href = "https://www.tiktok.com" + href

        video_id = href.split("/video/")[-1].split("?")[0]

        desc = await safe_text(
            await card.query_selector("[data-e2e='search-card-video-caption']")
        )
        if not desc:
            desc = await safe_text(await card.query_selector("span"))

        username = await safe_text(
            await card.query_selector("[data-e2e='search-card-user-unique-id']")
        )
        if not username:
            try:
                username = href.split("@")[1].split("/")[0]
            except Exception:
                username = ""

        views_search = await safe_text(
            await card.query_selector("[data-e2e='video-views']")
        )

        hashtags_search = extract_hashtags(desc)

        video_items.append(
            {
                "idx": idx,
                "href": href,
                "video_id": video_id,
                "desc": desc,
                "username": username,
                "views_search": views_search,
                "hashtags_search": hashtags_search,
            }
        )

    results = []
    profile_count = 0

    for item in video_items:
        idx = item["idx"]

        href = item["href"]
        video_id = item["video_id"]
        desc = item["desc"]
        username = item["username"]
        views_search = item["views_search"]
        hashtags_search = item["hashtags_search"]

        try:
            video_data = await fetch_video_stats(
                context,
                href,
                fallback_video_id=video_id,
            )

            stats = video_data.get("stats", {}) or {}
            author_info = video_data.get("author_info", {}) or {}
            music_info = video_data.get("music_info", {}) or {}

            final_desc = video_data.get("description") or desc
            final_hashtags = video_data.get("hashtags") or hashtags_search

            bio_links = []

            # PROFILE SCRAPE — limiter verwijderd
            if username:
                try:
                    profile_url = f"https://www.tiktok.com/@{username}"
                    profile_page = await context.new_page()
                    await profile_page.goto(profile_url, timeout=60000)
                    await profile_page.wait_for_timeout(2000)

                    extracted_links = await scrape_user_single_tab(profile_page)
                    if extracted_links:
                        bio_links.extend(list(set(extracted_links)))

                    await profile_page.close()

                except Exception as e:
                    logger.warning(f"PROFILE_FAIL | {username} | {e}")

            result = {
                "keyword": keyword,
                "video_id": video_data.get("video_id") or video_id,
                "video_url": href,
                "desc": final_desc,
                "views": stats.get("views") or views_search,
                "likes": stats.get("likes"),
                "comments": stats.get("comments"),
                "shares": stats.get("shares"),
                "saves": stats.get("saves"),
                "downloads": stats.get("downloads"),
                "forwards": stats.get("forwards"),
                "author": username or author_info.get("username"),
                "author_username": author_info.get("username"),
                "author_nickname": author_info.get("nickname"),
                "author_avatar": author_info.get("avatar"),
                "author_followers": author_info.get("followers"),
                "author_following": author_info.get("following"),
                "author_heart": author_info.get("heart"),
                "bio_links": list(set(bio_links)),
                "hashtags": final_hashtags,
                "create_time": video_data.get("create_time"),
                "duration": video_data.get("duration"),
                "music_id": music_info.get("id"),
                "music_title": music_info.get("title"),
                "music_author": music_info.get("author"),
                "music_play_url": music_info.get("playUrl")
                if "playUrl" in music_info
                else music_info.get("play_url"),
            }

            results.append(result)

            logger.info(
                f"VIDEO_OK | idx={idx} | id={result['video_id']} | user={result['author']}"
            )

        except Exception as e:
            logger.exception(f"VIDEO_ERROR | idx={idx} | {e}")
            continue

    duration = round(time.time() - start_time, 2)
    logger.info(
        f"SEARCH_DONE | keyword={keyword} | results={len(results)} | duration={duration}s"
    )

    return results
