"""Cari toko di Google Maps dengan Python/Playwright, lalu ambil email publik."""

import argparse
import csv
import json
import logging
from pathlib import Path
import re
import time
from urllib.parse import quote, unquote, urldefrag, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

LOGGER = logging.getLogger("scraper")
EMAIL_RE = re.compile(r"[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9](?:[A-Z0-9.-]*[A-Z0-9])?\.[A-Z]{2,63}\b", re.I)
CONTACT_RE = re.compile(r"contact|kontak|hubungi|about|tentang", re.I)
COLUMNS = ["name", "email", "website", "google_maps_url", "place_id", "email_source", "status"]


def create_session():
    session = requests.Session()
    session.headers["User-Agent"] = "StoreContactScraper/1.0"
    retry = Retry(total=2, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    return session


class MapsBlockedError(RuntimeError):
    """Google meminta verifikasi; hentikan pengambilan data."""


def check_maps_access(page):
    if (
        "/sorry/" in page.url
        or page.locator('iframe[src*="recaptcha"], form[action*="/sorry/"]').count()
        or re.search(r"unusual traffic|bukan robot|not a robot", page.locator("body").inner_text(), re.I)
    ):
        raise MapsBlockedError("Google meminta verifikasi/CAPTCHA. Pengambilan data dihentikan.")


def open_maps_page(page, url):
    page.goto(url, wait_until="domcontentloaded", timeout=45000)
    # Google dapat menampilkan dialog persetujuan cookie sebelum Maps.
    reject = page.get_by_role("button", name=re.compile(r"^(Reject all|Tolak semua)$", re.I))
    try:
        reject.first.wait_for(state="visible", timeout=2000)
        reject.first.click()
        page.wait_for_load_state("domcontentloaded")
    except PlaywrightTimeoutError:
        pass
    check_maps_access(page)


def maps_place_id(url):
    match = re.search(r"!1s([^!/?]+)", url)
    return unquote(match.group(1)) if match else ""


def parse_maps_results(html, page_url):
    """Baca tautan kartu toko tanpa bergantung pada nama class CSS Maps."""
    soup = BeautifulSoup(html, "html.parser")
    places = []
    seen = set()
    for link in soup.select('a[href*="/maps/place/"]'):
        url = urlsplit(urljoin(page_url, link["href"]))
        if url.hostname not in {"www.google.com", "google.com"}:
            continue
        canonical = urlunsplit((url.scheme, url.netloc, url.path, "", ""))
        identity = maps_place_id(canonical) or canonical
        name = (link.get("aria-label") or link.get_text(" ", strip=True)).strip()
        if name and identity not in seen:
            seen.add(identity)
            places.append({"name": name, "google_maps_url": canonical,
                           "place_id": maps_place_id(canonical), "website": ""})
    return places


def search_places(page, query, max_results):
    open_maps_page(page, "https://www.google.com/maps/search/" + quote(query, safe="") + "?hl=en")
    try:
        page.locator('div[role="feed"], h1').first.wait_for(timeout=20000)
    except PlaywrightTimeoutError as error:
        check_maps_access(page)
        raise RuntimeError("Tidak ada daftar toko. Coba kata pencarian/lokasi lain; lihat maps-debug.png.") from error
    feed = page.locator('div[role="feed"]').first
    if not feed.count():
        # Pencarian nama spesifik dapat langsung membuka satu profil toko.
        heading = page.locator("h1").first.inner_text().strip()
        if heading and "/maps/place/" in page.url:
            return [{"name": heading, "google_maps_url": page.url,
                     "place_id": maps_place_id(page.url), "website": ""}]
        raise RuntimeError("Daftar toko tidak ditemukan. Coba pencarian lebih spesifik.")
    places = {}
    unchanged = 0
    for _ in range(40):
        check_maps_access(page)
        before = len(places)
        for place in parse_maps_results(page.content(), page.url):
            places.setdefault(place["place_id"] or place["google_maps_url"], place)
        if len(places) >= max_results:
            break
        unchanged = unchanged + 1 if len(places) == before else 0
        if unchanged >= 4:
            break
        feed.hover()
        page.mouse.wheel(0, 1800)
        page.wait_for_timeout(1500)
    if not places:
        raise RuntimeError("Kartu toko tidak ditemukan. Tampilan Google Maps mungkin berubah.")
    return list(places.values())[:max_results]


def parse_maps_detail(html, place):
    soup = BeautifulSoup(html, "html.parser")
    result = dict(place)
    heading = soup.select_one("h1")
    if heading and heading.get_text(strip=True):
        result["name"] = heading.get_text(" ", strip=True)
    website = soup.select_one('a[data-item-id="authority"]')
    if website:
        href = website.get("href", "")
        if urlsplit(href).scheme in {"http", "https"}:
            result["website"] = href
    return result


def scrape_maps(query, max_results, headed=False, output_dir="scraper-output"):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        context = browser.new_context(locale="en-US", viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        page.set_default_timeout(15000)
        try:
            places = search_places(page, query, max_results)
            detail_page = context.new_page()
            detail_page.set_default_timeout(15000)
            for index, place in enumerate(places):
                try:
                    open_maps_page(detail_page, place["google_maps_url"])
                    detail_page.locator("h1").first.wait_for(timeout=15000)
                    try:
                        detail_page.locator('a[data-item-id="authority"]').first.wait_for(timeout=4000)
                    except PlaywrightTimeoutError:
                        pass  # Beberapa toko memang tidak mencantumkan website.
                    check_maps_access(detail_page)
                    places[index] = parse_maps_detail(detail_page.content(), place)
                except PlaywrightError:
                    check_maps_access(detail_page)
                    place["status"] = "maps_error"
                    LOGGER.warning("Detail Maps gagal dimuat untuk toko %d.", index + 1)
                LOGGER.info("Detail Maps %d/%d diproses.", index + 1, len(places))
                page.wait_for_timeout(1000)
            return places
        except (PlaywrightError, RuntimeError):
            debug_page = context.pages[-1]
            debug_dir = Path(output_dir)
            debug_dir.mkdir(parents=True, exist_ok=True)
            try:
                debug_page.screenshot(path=str(debug_dir / "maps-debug.png"))
                (debug_dir / "maps-debug.html").write_text(debug_page.content(), encoding="utf-8")
            except (PlaywrightError, OSError):
                LOGGER.warning("Tidak dapat menyimpan halaman debug Maps.")
            raise
        finally:
            context.close()
            browser.close()


def parse_page(html, page_url):
    """Ambil email teks/mailto dan tautan kontak pada host yang sama."""
    soup = BeautifulSoup(html, "html.parser")
    emails = set()
    contacts = []
    host = urlsplit(page_url).hostname
    for link in soup.select("a[href]"):
        href = link.get("href", "").strip()
        if href.lower().startswith("mailto:"):
            # Abaikan cc/bcc/subject agar email lain tidak dianggap kontak toko.
            address = unquote(href[7:].split("?", 1)[0])
            emails.update(match.lower() for match in EMAIL_RE.findall(address))
        elif CONTACT_RE.search(link.get_text(" ", strip=True) + " " + href):
            target = urldefrag(urljoin(page_url, href))[0]
            parsed = urlsplit(target)
            if parsed.scheme in {"http", "https"} and parsed.hostname == host and target != page_url:
                if target not in contacts:
                    contacts.append(target)
    for element in soup(["script", "style", "noscript", "template"]):
        element.decompose()
    emails.update(match.lower() for match in EMAIL_RE.findall(soup.get_text(" ", strip=True)))
    return sorted(emails), contacts


def find_emails(session, website, delay=1.0):
    if not website:
        return [], "no_website"
    if urlsplit(website).scheme not in {"http", "https"}:
        return [], "website_error"
    pending = [website]
    visited = set()
    found = {}
    failed = False
    # Homepage dan maksimal dua halaman kontak/tentang, tanpa crawl tak terbatas.
    while pending and len(visited) < 3:
        url = pending.pop(0)
        if url in visited:
            continue
        visited.add(url)
        time.sleep(delay)
        try:
            response = session.get(url, timeout=15)
            response.raise_for_status()
            if "html" not in response.headers.get("Content-Type", "").lower():
                failed = True
                continue
            emails, contacts = parse_page(response.content, response.url)
        except requests.RequestException:
            failed = True
            LOGGER.warning("Gagal mengakses halaman website toko (%s).", urlsplit(url).hostname)
            continue
        for email in emails:
            found.setdefault(email, response.url)
        if not found:
            pending.extend(contact for contact in contacts if contact not in visited)
        else:
            break
    if found:
        return sorted(found.items()), "found"
    return [], "website_error" if failed else "email_not_found"


def collect_rows(session, places, delay=1.0):
    rows = []
    for index, place in enumerate(places, start=1):
        website = place.get("website", "")
        emails, status = ([], "maps_error") if place.get("status") == "maps_error" else find_emails(session, website, delay)
        base = {
            "name": place["name"],
            "website": website,
            "google_maps_url": place["google_maps_url"],
            "place_id": place.get("place_id", ""),
            "status": status,
        }
        # Tetap simpan nama toko meskipun email tidak tersedia; jangan menebak email.
        for email, source in emails or [("", "")]:
            rows.append({**base, "email": email, "email_source": source})
        LOGGER.info("Toko %d/%d: %s", index, len(places), status)
    return rows


def write_results(rows, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "stores.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (output_dir / "stores.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        # Hindari formula aktif ketika data eksternal dibuka di Excel.
        writer.writerows({key: "'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r", "\n")) else value
                          for key, value in row.items()} for row in rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", required=True, help='Contoh: "toko komputer di Bandung"')
    parser.add_argument("--max-results", type=int, default=20, help="Jumlah toko: 1-60")
    parser.add_argument("--output-dir", default="scraper-output")
    parser.add_argument("--headed", action="store_true", help="Tampilkan Chromium saat menjalankan lokal")
    args = parser.parse_args(argv)
    if not args.query.strip():
        parser.error("Query tidak boleh kosong.")
    if not 1 <= args.max_results <= 60:
        parser.error("--max-results harus antara 1 dan 60.")
    with create_session() as session:
        try:
            places = scrape_maps(args.query.strip(), args.max_results, args.headed, args.output_dir)
            rows = collect_rows(session, places)
            write_results(rows, args.output_dir)
        except (PlaywrightError, requests.RequestException, ValueError, RuntimeError, OSError) as error:
            LOGGER.error("Scraper gagal (%s): %s", type(error).__name__, error)
            return 1
    LOGGER.info("Selesai: %d toko, %d baris email. Hasil: %s", len(places),
                sum(bool(row["email"]) for row in rows), args.output_dir)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    raise SystemExit(main())
