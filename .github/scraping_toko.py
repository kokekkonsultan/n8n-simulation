import asyncio
import os
import re
import httpx
from playwright.async_api import async_playwright

KEYWORD = os.environ.get("KEYWORD", "")
LIMIT = int(os.environ.get("LIMIT", 20))
ROW_ID = os.environ.get("ROW_ID", "")
N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL", "")

def decode_cloudflare_email(cf_hex):
    try:
        r = int(cf_hex[:2], 16)
        return ''.join([chr(int(cf_hex[i:i+2], 16) ^ r) for i in range(2, len(cf_hex), 2)])
    except Exception:
        return None

async def fetch_email_from_url_async(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    }
    ignored_keywords = [
        "example.com", "wixpress.com", "sentry.io", "mystore.com",
        "hello.com", "jdoe@gmail.com", "domain.com", "firstchapteragency.com",
        "sentry.wixpress.com", "user@domain.com"
    ]
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

    try:
        async with httpx.AsyncClient(verify=False, timeout=5.0, follow_redirects=True) as client:
            res = await client.get(url, headers=headers)
            html_text = res.text

            cf_matches = re.findall(r'data-cfemail="([a-f0-9]+)"', html_text)
            if cf_matches:
                decoded = decode_cloudflare_email(cf_matches[0])
                if decoded and not any(k in decoded.lower() for k in ignored_keywords):
                    return decoded

            emails = re.findall(email_pattern, html_text)
            valid = [
                e for e in set(emails)
                if not e.lower().endswith(('.png', '.jpg', '.jpeg', '.svg', '.webp', '.gif'))
                and not any(k in e.lower() for k in ignored_keywords)
            ]
            if valid:
                return valid[0]

            contact_paths = ['/contact', '/contact-us', '/about', '/about-us', '/kontak']
            base_url = url.rstrip('/')
            for path in contact_paths:
                try:
                    sub_res = await client.get(base_url + path, headers=headers)
                    sub_emails = re.findall(email_pattern, sub_res.text)
                    sub_valid = [
                        e for e in set(sub_emails)
                        if not e.lower().endswith(('.png', '.jpg', '.jpeg', '.svg', '.webp', '.gif'))
                        and not any(k in e.lower() for k in ignored_keywords)
                    ]
                    if sub_valid:
                        return sub_valid[0]
                except Exception:
                    continue
    except Exception:
        pass

    return "N/A"

async def process_contact_info_async(link_url: str):
    if not link_url or link_url == "N/A":
        return "N/A", "Tidak Ada"

    link_lower = link_url.lower()
    media_type = "Website Resmi"
    if "instagram.com" in link_lower:
        media_type = "Instagram"
    elif "facebook.com" in link_lower:
        media_type = "Facebook"
    elif "wa.me" in link_lower or "whatsapp" in link_lower:
        media_type = "WhatsApp Direct"
    elif "linktr.ee" in link_lower or "beacons.ai" in link_lower:
        media_type = "Linktree / Bio Link"

    if media_type in ["Instagram", "Facebook", "WhatsApp Direct"]:
        return "N/A", media_type

    email_found = await fetch_email_from_url_async(link_url)
    return email_found, media_type

async def main():
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
            locale="id-ID"
        )
        page = await context.new_page()

        print(f"Memulai scraping: '{KEYWORD}' (Limit: {LIMIT})")

        try:
            await page.goto(f"https://www.google.com/maps/search/{KEYWORD.replace(' ', '+')}", timeout=25000)
            await page.wait_for_timeout(2500)

            feed_selector = 'div[role="feed"]'
            try:
                await page.wait_for_selector(feed_selector, timeout=8000)
                for _ in range(6):
                    await page.hover(feed_selector)
                    await page.mouse.wheel(0, 3000)
                    await page.wait_for_timeout(1200)
            except Exception:
                pass

            links_elements = await page.query_selector_all('a[href*="/maps/place/"]')
            place_urls = []
            for elem in links_elements:
                url = await elem.get_attribute('href')
                if url and url not in place_urls:
                    place_urls.append(url)

            for url in place_urls[:LIMIT]:
                try:
                    await page.goto(url, timeout=8000)
                    await page.wait_for_selector('h1', timeout=4000)

                    title_elem = await page.query_selector('h1')
                    name_text = (await title_elem.inner_text()).strip() if title_elem else "N/A"
                    if not name_text or name_text.lower() == "hasil":
                        continue

                    phone_elem = await page.query_selector('button[data-item-id^="phone"]')
                    phone = (await phone_elem.get_attribute('aria-label')).replace("Telepon: ", "").strip() if phone_elem else "N/A"

                    addr_elem = await page.query_selector('button[data-item-id^="address"]')
                    address = (await addr_elem.get_attribute('aria-label')).replace("Alamat: ", "").strip() if addr_elem else "N/A"

                    web_elem = await page.query_selector('a[data-item-id="authority"]')
                    website_link = await web_elem.get_attribute('href') if web_elem else "N/A"

                    email, media_type = await process_contact_info_async(website_link)

                    results.append({
                        "nama_toko": name_text,
                        "no_telepon": phone,
                        "email_valid": email,
                        "kategori_situs": media_type,
                        "link_website": website_link,
                        "alamat_lengkap": address
                    })
                except Exception as e:
                    print(f"Skip toko: {e}")
                    continue
        finally:
            await browser.close()

    # Kirim hasil balik ke Webhook n8n
    payload = {
        "status": "success",
        "id": ROW_ID,
        "keyword": KEYWORD,
        "total_fetched": len(results),
        "results": results
    }

    if N8N_WEBHOOK_URL:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(N8N_WEBHOOK_URL, json=payload)
            print(f"Terkirim ke n8n! Status: {resp.status_code}")

if __name__ == "__main__":
    asyncio.run(main())