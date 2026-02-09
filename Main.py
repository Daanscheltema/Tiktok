import asyncio
import time
import os
import pandas as pd

from scraper.browser import get_browser
from scraper.search import search_keyword   # <-- DIT IS DE JUISTE FUNCTIE
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

    logger.info("BROWSER_STARTED")
    print("Browser started.")

    # Voeg hier meerdere keywords toe
    keywords = ["Glock switch"]

    # CSV-bestand waar alles in komt
    csv_path = "tiktok_results_testmeerkaarten.csv"

    for kw in keywords:
        logger.info(f"KEYWORD_START | keyword={kw}")
        print(f"\n🔎 Searching for keyword: {kw}")

        start_time = time.time()

        try:
            # -----------------------------
            # JUISTE SCRAPER CALL
            # -----------------------------
            results = await search_keyword(
                page,
                kw,
                max_videos=200,   # <-- pas aan wat je wilt
                max_profiles=None
            )

            if not results:
                logger.warning(f"KEYWORD_EMPTY | keyword={kw}")
                print("⚠ No results returned")
                continue

            logger.info(f"KEYWORD_OK | keyword={kw} | results={len(results)}")

            print("\n========== RESULTS ==========")
            print(f"Total: {len(results)}\n")

            # Print resultaten in console
            for r in results:
                print(
                    f"- Video {r.get('video_id')} | "
                    f"Views: {r.get('views')} | "
                    f"User: {r.get('author')} | "
                    f"Bio links: {r.get('bio_links')}"
                )

            # -----------------------------
            # CSV EXPORT
            # -----------------------------
            df = pd.DataFrame(results)

            # Zorg dat keyword altijd in de CSV staat
            df["keyword"] = kw

            # Als CSV al bestaat → append zonder header
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