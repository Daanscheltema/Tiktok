import re
import time
from scraper.user import scrape_user
from logger import setup_logger

logger = setup_logger()

LINK_REGEX = r"(https?://[^\s]+)"
HASHTAG_REGEX = r"#(\w+)"


# -----------------------------
# Dynamisch scrollen (CDP‑Chrome compatible)
# -----------------------------
async def scroll_until_no_new_results(page, max_scrolls=30, wait=1500):
    last_height = 0

    for i in range(max_scrolls):
        # Echte scroll in Chrome
        await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
        await page.wait_for_timeout(wait)

        height = await page.evaluate("document.body.scrollHeight")

        if height == last_height:
            print(f"🔚 Geen nieuwe resultaten na {i} scrolls.")
            break

        last_height = height


# -----------------------------
# Hoofd scraping functie
# -----------------------------
async def search_keyword(search_page, keyword: str, max_videos=None, max_profiles=None):
    start_time = time.time()
    logger.info(f"SEARCH_START | keyword={keyword}")

    search_url = f"https://www.tiktok.com/search?q={keyword}"
    await search_page.goto(search_url, timeout=60000)
    await search_page.wait_for_timeout(3000)

    # Scroll tot er geen nieuwe resultaten meer zijn
    await scroll_until_no_new_results(search_page)

    # Fallback selectors voor TikTok DOM varianten
    selectors = [
        "div[id^='grid-item-container-']",
        "div[data-e2e='search-card']",
        "div[data-e2e='search-item']",
        "div[data-e2e='search-video-card']"
    ]

    cards = []
    for sel in selectors:
        cards = await search_page.query_selector_all(sel)
        if cards:
            break

    logger.info(f"CARDS_FOUND | keyword={keyword} | count={len(cards)}")

    results = []
    profile_count = 0

    # Echte Chrome context
    chrome_context = search_page.context

    for idx, card in enumerate(cards, start=1):

        # Video limiet
        if max_videos and idx > max_videos:
            print("⛔ Video limiet bereikt.")
            break

        try:
            # Video link
            link_el = await card.query_selector("a[href*='/video/']")
            href = await link_el.get_attribute("href") if link_el else None
            video_id = href.split("/")[-1] if href else None

            # Description
            desc_el = await card.query_selector("div[data-e2e='search-card-video-caption']")
            desc = await desc_el.inner_text() if desc_el else ""

            # Username
            user_el = await card.query_selector("p[data-e2e='search-card-user-unique-id']")
            username = await user_el.inner_text() if user_el else ""

            # Views
            views_el = await card.query_selector("strong[data-e2e='video-views']")
            views = await views_el.inner_text() if views_el else "0"

            desc_links = re.findall(LINK_REGEX, desc)
            hashtags = re.findall(HASHTAG_REGEX, desc)

            bio_links = []

            # -----------------------------
            # Profielbezoek bij elke video
            # -----------------------------
            if username:

                # Profiel limiet
                if max_profiles and profile_count >= max_profiles:
                    print("⛔ Profiel limiet bereikt.")
                else:
                    profile_count += 1

                    try:
                        # NIEUW: open tabblad in echte Chrome context
                        profile_page = await chrome_context.new_page()

                        user_info, _, extracted_links = await scrape_user(
                            profile_page,
                            username
                        )

                        for link in extracted_links:
                            if link not in bio_links:
                                bio_links.append(link)

                        if user_info:
                            bio = user_info.get("bioLink", {})
                            official_link = bio.get("link")
                            if official_link and official_link not in bio_links:
                                bio_links.append(official_link)

                        await profile_page.close()

                    except Exception as e:
                        logger.warning(
                            f"PROFILE_FAIL | user={username} | error={e}"
                        )

            # -----------------------------
            # Resultaat opslaan
            # -----------------------------
            results.append({
                "keyword": keyword,
                "video_id": video_id,
                "desc": desc,
                "views": views,
                "author": username,
                "desc_links": desc_links,
                "bio_links": bio_links,
                "hashtags": hashtags
            })

            logger.info(
                f"VIDEO_OK | kw={keyword} | "
                f"idx={idx} | id={video_id} | user={username} | views={views}"
            )

        except Exception as e:
            logger.exception(
                f"VIDEO_ERROR | kw={keyword} | idx={idx} | error={e}"
            )
            continue

    duration = round(time.time() - start_time, 2)
    logger.info(
        f"SEARCH_DONE | keyword={keyword} | "
        f"results={len(results)} | duration={duration}s"
    )

    return results
