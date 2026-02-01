import asyncio
import re
from scraper.user import scrape_user
from scraper.browser import DESKTOP

LINK_REGEX = r"(https?://[^\s]+)"
HASHTAG_REGEX = r"#(\w+)"

async def search_keyword(search_page, keyword: str, user_page=None, hashtag_page=None):
    search_url = f"https://www.tiktok.com/search?q={keyword}"
    await search_page.goto(search_url, timeout=60000)
    await search_page.wait_for_timeout(5000)

    # Scroll to load more results
    for _ in range(3):
        await search_page.mouse.wheel(0, 2000)
        await search_page.wait_for_timeout(2000)

    cards = await search_page.query_selector_all("div[id^='grid-item-container-']")
    results = []

    for card in cards:
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

            # Extract links from description
            desc_links = re.findall(LINK_REGEX, desc)

            # Extract hashtags from description (TEXT ONLY)
            hashtags = re.findall(HASHTAG_REGEX, desc)

            # --- USER PROFILE SCRAPING ---
            bio_links = []

            if username:
                try:
                    browser = search_page.context.browser
                    new_context = await browser.new_context(**DESKTOP)
                    profile_page = await new_context.new_page()

                    # scrape_user returns: user_info, videos, extracted_links
                    user_info, _, extracted_links = await scrape_user(profile_page, username)

                    # Add extracted links from profile
                    for link in extracted_links:
                        if link not in bio_links:
                            bio_links.append(link)

                    # Add official TikTok bioLink if SIGI_STATE worked
                    if user_info:
                        bio = user_info.get("bioLink", {})
                        official_link = bio.get("link")
                        if official_link and official_link not in bio_links:
                            bio_links.append(official_link)

                    await new_context.close()

                except Exception:
                    pass

            # Append final result
            results.append({
                "keyword": keyword,
                "video_id": video_id,
                "desc": desc,
                "views": views,
                "author": username,
                "desc_links": desc_links,
                "bio_links": bio_links,
                "hashtags": hashtags   # <-- NOW JUST TEXT LIST
            })

        except Exception:
            continue

    return results
