# scraper/user.py
import json
import asyncio
import re
import urllib.parse


# Regex for URLs inside bio text
BIO_LINK_REGEX = (
    r"(https?://[^\s]+|"          # full URLs
    r"www\.[^\s]+|"               # www. links
    r"(?:t\.me|discord\.gg|discord\.com|"
    r"snapchat\.com|linktr\.ee|beacons\.ai|"
    r"onlyfans\.com|patreon\.com|"
    r"instagram\.com|youtube\.com|twitch\.tv)"
    r"/[^\s]+)"
)


async def scrape_user(page, username: str):
    print(f"\n🔥 SCRAPING PROFILE: {username}")

    url = f"https://www.tiktok.com/@{username}"
    print(f"--- Opening profile: {url} ---")

    # Open profile page
    try:
        await page.goto(url, timeout=60000)
    except Exception:
        print("⚠ Could not open profile")
        return None, [], []

    # Try to load SIGI_STATE (user info + videos)
    state = {}
    try:
        await page.wait_for_selector("script[id='SIGI_STATE']", timeout=8000)
        data = await page.evaluate("document.querySelector('#SIGI_STATE').textContent")
        state = json.loads(data)

        print("\n--- DEBUG: SIGI_STATE UserModule ---")
        print(json.dumps(state.get("UserModule", {}), indent=2))
        print("--- END SIGI_STATE ---\n")

    except Exception:
        print("⚠ SIGI_STATE could not be loaded")

    # Extract user info
    user_info = (
        state.get("UserModule", {})
             .get("users", {})
             .get(username.lower())
    )

    # Extract videos
    videos = list(
        state.get("ItemModule", {}).values()
    ) if "ItemModule" in state else []

    # Extract bio text (DOM)
    bio_text = ""
    bio_selectors = [
        "h2[data-e2e='user-bio']",
        "span[data-e2e='user-bio']",
        "p[data-e2e='user-bio']",
        "div[data-e2e='user-bio']"
    ]

    for sel in bio_selectors:
        try:
            bio_text = await page.inner_text(sel)
            if bio_text.strip():
                print("\n--- BIO TEXT FOUND ---")
                print(bio_text)
                print("--- END BIO TEXT ---\n")
                break
        except:
            continue

    extracted_links = []

    # Extract URLs from bio text
    if bio_text:
        found_links = re.findall(BIO_LINK_REGEX, bio_text)
        for link in found_links:
            if isinstance(link, tuple):
                link = link[0]
            if link not in extracted_links:
                extracted_links.append(link)

    # Extract official TikTok bio links (e.g., t.me/rebounder77b)
    try:
        link_elements = await page.query_selector_all("a[data-e2e='user-link']")
        for el in link_elements:
            href = await el.get_attribute("href")
            text = await el.inner_text()

            real_url = None

            # TikTok wraps links like:
            # https://www.tiktok.com/link/v2?...&target=https%3A%2F%2Ft.me%2Frebounder77b
            if href and "target=" in href:
                parsed = urllib.parse.urlparse(href)
                qs = urllib.parse.parse_qs(parsed.query)
                real_url = qs.get("target", [None])[0]
            else:
                real_url = href

            if real_url and real_url not in extracted_links:
                extracted_links.append(real_url)

            if text and text not in extracted_links:
                extracted_links.append(text)

    except Exception:
        pass

    print(f"✅ Extracted links for {username}: {extracted_links}")

    return user_info, videos, extracted_links
