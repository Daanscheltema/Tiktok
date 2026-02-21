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


CSV_PATH = "tiktok_results_buttons.csv"

COLUMNS = [
    "keyword",
    "video_id",
    "video_url",
    "views",
    "likes",
    "comments",
    "shares",
    "saves",
    "author",
    "followers",
    "following",
    "profile_likes",
    "total_videos",
    "profile_bio",
    "video_desc",
    "hashtags",
    "bio_links",
]

def append_rows_to_csv(rows, csv_path=CSV_PATH):
    """Append rows (list[dict]) to CSV with fixed columns and ; separator."""
    if not rows:
        return

    df = pd.DataFrame(rows).reindex(columns=COLUMNS)

    file_exists = os.path.exists(csv_path)

    df.to_csv(
        csv_path,
        mode="a",
        index=False,
        header=not file_exists,
        sep=";"
    )


async def run():
    logger.info("SCRAPER_START")
    print("Starting browser...")

    playwright, browser, context, page = await get_browser(
        PROXY,
        browser_type="cdp-chrome"
    )

    ua = await page.evaluate("() => navigator.userAgent")
    print("USER_AGENT:", ua)

    cookies = await context.cookies()
    print("=== COOKIES IN CONTEXT ===")
    for c in cookies:
        print(f"{c['name']} = {c['value']}")
    print("===========================")

    logger.info("BROWSER_STARTED")
    print("Browser started.")

    keywords = [
        "Button", "Buttons"
    ]

    for kw in keywords:
        logger.info(f"KEYWORD_START | keyword={kw}")
        print(f"\n🔎 Searching for keyword: {kw}")

        start_time = time.time()

        try:
            results = await search_keyword(
                page,
                kw,
                max_videos=300,
                max_profiles=None
            )

            if not results:
                logger.warning(f"KEYWORD_EMPTY | keyword={kw}")
                print("⚠ No results returned")
                # Optioneel: niks schrijven bij empty
                continue

            logger.info(f"KEYWORD_OK | keyword={kw} | results={len(results)}")
            print(f"Total: {len(results)}")

            # --- maak rows voor CSV ---
            rows = []
            for r in results:
                profile_stats = r.get("profile_stats") or {}
                rows.append({
                    "keyword": kw,

                    "video_id": r.get("video_id"),
                    "video_url": r.get("video_url"),
                    "views": r.get("views"),
                    "likes": r.get("likes"),
                    "comments": r.get("comments"),
                    "shares": r.get("shares"),
                    "saves": r.get("saves"),

                    "author": r.get("author"),
                    "followers": profile_stats.get("followers"),
                    "following": profile_stats.get("following"),
                    "profile_likes": profile_stats.get("likes"),
                    "total_videos": profile_stats.get("videos"),
                    "profile_bio": r.get("profile_bio"),

                    "video_desc": r.get("desc"),
                    "hashtags": ",".join(r.get("hashtags") or []),
                    "bio_links": " | ".join(r.get("bio_links") or []),
                })

            # ✅ schrijf DIRECT na elk keyword (append naar dezelfde CSV)
            append_rows_to_csv(rows, CSV_PATH)
            print(f"📁 CSV bijgewerkt (append): {CSV_PATH}")

        except Exception as e:
            logger.exception(f"KEYWORD_ERROR | keyword={kw} | error={e}")

        duration = round(time.time() - start_time, 2)
        logger.info(f"KEYWORD_DONE | keyword={kw} | duration={duration}s")

    logger.info("SCRAPER_SHUTDOWN")
    await browser.close()
    await playwright.stop()


asyncio.run(run())