import asyncio
from playwright.async_api import async_playwright

async def login_persistent_webkit():
    async with async_playwright() as p:
        # Persistent context werkt in WebKit
        context = await p.webkit.launch_persistent_context(
            user_data_dir="tiktok_session_webkit",
            headless=False,
            viewport={"width": 1400, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/17.0 Safari/605.1.15"
            )
        )

        page = await context.new_page()
        await page.goto("https://www.tiktok.com/login", timeout=60000)

        print("\n👉 Log handmatig in.")
        print("👉 Als je de TikTok feed ziet, sluit dan de browser.\n")

        # Browser blijft open tot jij hem sluit
        await page.wait_for_timeout(999999999)

asyncio.run(login_persistent_webkit())

