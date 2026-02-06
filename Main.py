import asyncio
import time
import os
from scraper.browser import get_browser
from scraper.search import search_keyword
from config import PROXY
from logger import setup_logger

print("cwd", os.getcwd())

logger = setup_logger()


async def run():
    logger.info("SCRAPER_START")
    print("Starting browser...")

    playwright, browser, context, search_page = await get_browser(
        PROXY,
        browser_type="cdp-chrome"
    )

    logger.info("BROWSER_STARTED")
    print("Browser started.")

    keywords = [
        "Buttons"
    ]

    for kw in keywords:
        logger.info(f"KEYWORD_START | keyword={kw}")
        print(f"\n🔎 Searching for keyword: {kw}")

        start_time = time.time()

        try:
            results = await search_keyword(
                search_page,
                kw,
                max_videos=30,
                max_profiles=30
            )

            if not results:
                logger.warning(f"KEYWORD_EMPTY | keyword={kw}")
                print("⚠ No results returned")
                continue

            logger.info(
                f"KEYWORD_OK | keyword={kw} | results={len(results)}"
            )

            print("\n========== RESULTS ==========")
            print(f"Total: {len(results)}\n")

            for r in results:
                print(
                    f"- Video {r.get('video_id')} | "
                    f"Views: {r.get('views')} | "
                    f"Likes: {r.get('likes')} | "
                    f"User: {r.get('author')} | "
                    f"Bio links: {r.get('bio_links')} | "
                    f"Hashtags: {r.get('hashtags')}"
                )

        except Exception as e:
            logger.exception(f"KEYWORD_ERROR | keyword={kw} | error={e}")

        duration = round(time.time() - start_time, 2)
        logger.info(
            f"KEYWORD_DONE | keyword={kw} | duration={duration}s"
        )

    logger.info("SCRAPER_SHUTDOWN")

    await browser.close()
    await playwright.stop()


asyncio.run(run())
