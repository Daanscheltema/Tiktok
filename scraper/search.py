import re
import time
from scraper.user import scrape_user
from logger import setup_logger

logger = setup_logger()

HASHTAG_REGEX = r"#(\w+)"


# -----------------------------
# Scroll helper
# -----------------------------
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


# -----------------------------
# Safe text helper
# -----------------------------
async def safe_text(el):
    if not el:
        return ""
    try:
        return await el.inner_text()
    except:
        return ""


# -----------------------------
# Main search function
# -----------------------------
async def search_keyword(search_page, keyword: str, max_videos=None, max_profiles=None):

    start_time = time.time()
    logger.info(f"SEARCH_START | keyword={keyword}")

    search_url = f"https://www.tiktok.com/search?q={keyword}"

    await search_page.goto(search_url, timeout=60000)
    await search_page.wait_for_timeout(4000)

    await scroll_until_no_new_results(search_page)

    # Updated selectors (TikTok rotates DOM often)
    selectors = [
        "div[data-e2e='search-card']",
        "div[data-e2e='search-video-card']",
        "div[id^='grid-item-container-']",
        "div[data-e2e='search-item']"
    ]

    cards = []
    for sel in selectors:
        cards = await search_page.query_selector_all(sel)
        if cards:
            logger.info(f"Selector matched: {sel}")
            break

    logger.info(f"CARDS_FOUND | keyword={keyword} | count={len(cards)}")

    results = []
    profile_count = 0
    chrome_context = search_page.context

    for idx, card in enumerate(cards, start=1):

        if max_videos and idx > max_videos:
            logger.info("VIDEO LIMIT reached")
            break

        try:

            # -----------------------------
            # VIDEO LINK
            # -----------------------------
            link_el = await card.query_selector("a[href*='/video/']")
            href = await link_el.get_attribute("href") if link_el else None

            if not href:
                logger.warning(f"No video link found idx={idx}")
                continue

            if href.startswith("/"):
                href = "https://www.tiktok.com" + href

            video_id = href.split("/video/")[-1].split("?")[0]

            # -----------------------------
            # TEXT DATA
            # -----------------------------
            desc = await safe_text(
                await card.query_selector("[data-e2e='search-card-video-caption']")
            )

            if not desc:
                # fallback caption selector
                desc = await safe_text(await card.query_selector("span"))

            username = await safe_text(
                await card.query_selector("[data-e2e='search-card-user-unique-id']")
            )

            if not username:
                # fallback from href
                try:
                    username = href.split("@")[1].split("/")[0]
                except:
                    username = ""

            views = await safe_text(
                await card.query_selector("[data-e2e='video-views']")
            )

            likes = await safe_text(
                await card.query_selector("[data-e2e='like-count']")
            )

            hashtags = re.findall(HASHTAG_REGEX, desc)

            bio_links = []

            # -----------------------------
            # PROFILE SCRAPE (SAFE)
            # -----------------------------
            if username and (not max_profiles or profile_count < max_profiles):

                profile_count += 1

                try:
                    profile_page = await chrome_context.new_page()

                    user_info, _, extracted_links = await scrape_user(
                        profile_page,
                        username
                    )

                    if extracted_links:
                        bio_links.extend(list(set(extracted_links)))

                    if user_info:
                        bio = user_info.get("bioLink", {})
                        official_link = bio.get("link")
                        if official_link:
                            bio_links.append(official_link)

                    await profile_page.close()

                except Exception as e:
                    logger.warning(f"PROFILE_FAIL | {username} | {e}")

            # -----------------------------
            # SAVE RESULT
            # -----------------------------
            result = {
                "keyword": keyword,
                "video_id": video_id,
                "video_url": href,
                "desc": desc,
                "views": views,
                "likes": likes,
                "author": username,
                "bio_links": list(set(bio_links)),
                "hashtags": hashtags
            }

            results.append(result)

            logger.info(
                f"VIDEO_OK | idx={idx} | id={video_id} | user={username}"
            )

        except Exception as e:
            logger.exception(f"VIDEO_ERROR | idx={idx} | {e}")
            continue

    duration = round(time.time() - start_time, 2)

    logger.info(
        f"SEARCH_DONE | keyword={keyword} | results={len(results)} | duration={duration}s"
    )

    return results
