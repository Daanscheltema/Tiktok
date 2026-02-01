import asyncio
from scraper.browser import get_browser
from scraper.search import search_keyword
from config import PROXY

async def run():
    print("Starting browser...")

    playwright, browser, context, search_page = await get_browser(
        PROXY,
        browser_type="chromium"
    )

    print("Browser started.")

    # Extra pages voor user-profielen en hashtags
    user_page = await context.new_page()
    hashtag_page = await context.new_page()

    keywords = [
        "Bastion"
    ]

    for kw in keywords:
        print(f"\n🔎 Searching for keyword: {kw}")
        results = await search_keyword(
            search_page,
            kw,
            user_page,
            hashtag_page
        )

        if not results:
            print("No results returned.")
            continue

        for r in results:
            print(
                f"- Video {r['video_id']} | Views: {r['views']} | User: {r['author']} | "
                f"Desc links: {r['desc_links']} | Bio links: {r['bio_links']} | Hashtags: {r['hashtags']}"
            )

    await browser.close()
    await playwright.stop()

asyncio.run(run())

