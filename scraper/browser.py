from playwright.async_api import async_playwright

DESKTOP = {
    "viewport": {"width": 1280, "height": 800},
    "device_scale_factor": 1,
    "is_mobile": False,
    "has_touch": False,
    "user_agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

CHROME_CDP_URL = "http://localhost:9222"


async def get_browser(proxy: str | None = None, browser_type: str = "chromium"):
    playwright = await async_playwright().start()

    if browser_type == "cdp-chrome":
        print("Connecting to existing Chrome via CDP...")
        browser = await playwright.chromium.connect_over_cdp(CHROME_CDP_URL)

        if not browser.contexts:
            raise Exception("❌ No Chrome contexts found.")

        context = browser.contexts[0]

        # Pick TikTok tab
        tiktok_pages = [p for p in context.pages if "tiktok.com" in p.url.lower()]
        if tiktok_pages:
            page = tiktok_pages[-1]
            print(f"✔ Using TikTok tab: {page.url}")
        else:
            page = await context.new_page()
            print("⚠ No TikTok tab found, opened a new one.")

        # ---------------------------------------------------------
        # Inject X-Bogus generator into ALL future navigations
        # ---------------------------------------------------------
        await context.add_init_script("""
            Object.defineProperty(window, 'generateXbogus', {
                value: async function(url) {
                    try {
                        let retries = 0;
                        while (!window.byted_acrawler && retries < 50) {
                            await new Promise(r => setTimeout(r, 100));
                            retries++;
                        }
                        if (!window.byted_acrawler || !window.byted_acrawler.sign) {
                            return null;
                        }
                        const signed = window.byted_acrawler.sign({ url });
                        return signed?.xbogus || null;
                    } catch {
                        return null;
                    }
                },
                writable: false
            });
        """)

        # ---------------------------------------------------------
        # ENSURE SIGNER EXISTS — bootstrap by visiting a real video
        # ---------------------------------------------------------
        print("Checking if byted_acrawler.sign exists...")

        has_signer = await page.evaluate(
            "() => !!(window.byted_acrawler && window.byted_acrawler.sign)"
        )

        if not has_signer:
            print("⚠ Signer not loaded — navigating to bootstrap video...")
            await page.goto("https://www.tiktok.com/@tiktok/video/7000000000000000000")
            await page.wait_for_timeout(3000)

            has_signer = await page.evaluate(
                "() => !!(window.byted_acrawler && window.byted_acrawler.sign)"
            )
            print("Signer after bootstrap:", has_signer)

        # ---------------------------------------------------------
        # Inject into existing page (NOW signer exists)
        # ---------------------------------------------------------
        await page.evaluate("""
            if (!window.generateXbogus) {
                Object.defineProperty(window, 'generateXbogus', {
                    value: async function(url) {
                        try {
                            let retries = 0;
                            while (!window.byted_acrawler && retries < 50) {
                                await new Promise(r => setTimeout(r, 100));
                                retries++;
                            }
                            if (!window.byted_acrawler || !window.byted_acrawler.sign) {
                                return null;
                            }
                            const signed = window.byted_acrawler.sign({ url });
                            return signed?.xbogus || null;
                        } catch {
                            return null;
                        }
                    },
                    writable: false
                });
            }
        """)

        print("✔ X-Bogus generator injected and signer is ready.")

        return playwright, browser, context, page

    # Normal Playwright launch
    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context(**DESKTOP)
    page = await context.new_page()
    return playwright, browser, context, page
