import asyncio
import time
import os
import pandas as pd

from scraper.browser import get_browser
from scraper.search import search_keyword
from config import PROXY
from logger import setup_logger

print("cwd", os.getcwd())
logger = setup_logger()


async def run():
    logger.info("SCRAPER_START")
    print("Starting browser...")

    playwright, browser, context, page = await get_browser(
        PROXY,
        browser_type="cdp-chrome"
    )

    # -----------------------------
    # DEBUG: USER AGENT
    # -----------------------------
    ua = await page.evaluate("() => navigator.userAgent")
    print("USER_AGENT:", ua)

    # -----------------------------
    # DEBUG: COOKIES
    # -----------------------------
    cookies = await context.cookies()
    print("=== COOKIES IN CONTEXT ===")
    for c in cookies:
        print(f"{c['name']} = {c['value']}")
    print("===========================")

    logger.info("BROWSER_STARTED")
    print("Browser started.")

    keywords = ["Buttons"]
    csv_path = "tiktok_results_testmeerkaarten.csv"

    for kw in keywords:
        logger.info(f"KEYWORD_START | keyword={kw}")
        print(f"\n🔎 Searching for keyword: {kw}")

        start_time = time.time()

        try:
            results = await search_keyword(
                page,
                kw,
                max_videos=200,
                max_profiles=None
            )

            if not results:
                logger.warning(f"KEYWORD_EMPTY | keyword={kw}")
                print("⚠ No results returned")
                continue

            logger.info(f"KEYWORD_OK | keyword={kw} | results={len(results)}")

            print("\n========== RESULTS ==========")
            print(f"Total: {len(results)}\n")

            # -----------------------------
            # CONSOLE OUTPUT (VOLLEDIG)
            # -----------------------------
            for r in results:
                profile_stats = r.get("profile_stats") or {}

                print(
                    f"- Video {r.get('video_id')}\n"
                    f"  Views: {r.get('views')} | "
                    f"Likes: {r.get('likes')} | "
                    f"Comments: {r.get('comments')} | "
                    f"Shares: {r.get('shares')} | "
                    f"Saves: {r.get('saves')}\n"
                    f"  User: {r.get('author')} | "
                    f"Followers: {profile_stats.get('followers')} | "
                    f"Following: {profile_stats.get('following')} | "
                    f"Profile Likes: {profile_stats.get('likes')} | "
                    f"Videos: {profile_stats.get('videos')}\n"
                    f"  Profile bio: {r.get('profile_bio')}\n"
                    f"  Video desc: {r.get('desc')}\n"
                    f"  Bio links: {r.get('bio_links')}\n"
                )

            # -----------------------------
            # CSV EXPORT
            # -----------------------------
            df = pd.DataFrame(results)
            df["keyword"] = kw

            if os.path.exists(csv_path):
                df.to_csv(csv_path, mode="a", index=False, header=False)
            else:
                df.to_csv(csv_path, index=False)

            print(f"📁 CSV bijgewerkt: {csv_path}")

        except Exception as e:
            logger.exception(f"KEYWORD_ERROR | keyword={kw} | error={e}")

        duration = round(time.time() - start_time, 2)
        logger.info(f"KEYWORD_DONE | keyword={kw} | duration={duration}s")

    logger.info("SCRAPER_SHUTDOWN")
    await browser.close()
    await playwright.stop()


asyncio.run(run())
