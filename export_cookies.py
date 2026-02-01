from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()

    page = context.new_page()
    page.goto("https://www.tiktok.com", timeout=60000)

    print("Laat de pagina volledig laden. NIET opnieuw inloggen.")
    input("Druk op ENTER zodra je de TikTok homepage ziet...")

    context.storage_state(path="tiktok_session.json")
    print("Sessie opgeslagen in tiktok_session.json")

    browser.close()
