import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests

import scraper


def response(data=None, html=None, url="https://toko.test/"):
    result = Mock()
    result.ok = True
    result.json.return_value = data
    result.url = url
    result.content = (html or "").encode()
    result.headers = {"Content-Type": "text/html; charset=utf-8"}
    return result


class ScraperTests(unittest.TestCase):
    def test_email_extraction_and_contact_scope(self):
        html = '''<a href="mailto:SALES%40toko.id?cc=other@outside.id">Email</a>
            <p>sales@toko.id dan info@toko.id</p><script>fake@script.id</script>
            <a href="/kontak#form">Hubungi</a>
            <a href="https://outside.id/contact">Contact</a>'''
        emails, links = scraper.parse_page(html, "https://toko.id/")
        self.assertEqual(emails, ["info@toko.id", "sales@toko.id"])
        self.assertEqual(links, ["https://toko.id/kontak"])

    def test_maps_cards_deduplication(self):
        html = '''<a aria-label="Toko Satu" href="https://www.google.com/maps/place/Satu/data=!1sone?hl=en"></a>
            <a aria-label="Toko Satu" href="https://www.google.com/maps/place/Satu/data=!1sone?entry=ttu"></a>
            <a aria-label="Toko Dua" href="/maps/place/Dua/data=!1stwo"></a>
            <a aria-label="Iklan" href="https://outside.id/maps/place/Iklan"></a>'''
        places = scraper.parse_maps_results(html, "https://www.google.com/maps/search/toko")
        self.assertEqual([place["place_id"] for place in places], ["one", "two"])
        self.assertEqual([place["name"] for place in places], ["Toko Satu", "Toko Dua"])
        self.assertNotIn("?", places[0]["google_maps_url"])

    def test_maps_detail_uses_official_website_link(self):
        html = '''<h1>Toko Satu</h1><a href="https://advertiser.id/">Iklan</a>
            <a data-item-id="authority" href="https://toko.id/">Website</a>'''
        result = scraper.parse_maps_detail(html, {"name": "Nama kartu", "place_id": "one", "website": ""})
        self.assertEqual(result["name"], "Toko Satu")
        self.assertEqual(result["website"], "https://toko.id/")

    def test_captcha_stops_scraping(self):
        page = Mock(url="https://www.google.com/sorry/index")
        with self.assertRaises(scraper.MapsBlockedError):
            scraper.check_maps_access(page)

    @patch("scraper.open_maps_page")
    @patch("scraper.check_maps_access")
    def test_maps_scrolls_and_limits_results(self, check, open_page):
        page = Mock(url="https://www.google.com/maps/search/toko")
        page.content.side_effect = [
            '<a aria-label="Satu" href="/maps/place/Satu/data=!1sone"></a>',
            '<a aria-label="Dua" href="/maps/place/Dua/data=!1stwo"></a>'
            '<a aria-label="Tiga" href="/maps/place/Tiga/data=!1sthree"></a>',
        ]
        result = scraper.search_places(page, "toko di Bandung", 2)
        self.assertEqual([place["place_id"] for place in result], ["one", "two"])
        page.mouse.wheel.assert_called_once()
        self.assertIn("toko%20di%20Bandung", open_page.call_args.args[1])

    @patch("scraper.open_maps_page")
    @patch("scraper.check_maps_access")
    def test_maps_scroll_stops_when_results_do_not_grow(self, check, open_page):
        page = Mock(url="https://www.google.com/maps/search/toko")
        page.content.return_value = '<a aria-label="Satu" href="/maps/place/Satu/data=!1sone"></a>'
        result = scraper.search_places(page, "toko", 20)
        self.assertEqual(len(result), 1)
        self.assertLessEqual(page.mouse.wheel.call_count, 5)

    def test_email_from_contact_page_keeps_source(self):
        session = Mock()
        session.get.side_effect = [
            response(html='<a href="/contact">Contact</a>'),
            response(html="Email: info@toko.id", url="https://toko.test/contact"),
        ]
        emails, status = scraper.find_emails(session, "https://toko.test/", delay=0)
        self.assertEqual(status, "found")
        self.assertEqual(emails, [("info@toko.id", "https://toko.test/contact")])

    def test_website_failure_keeps_store_name(self):
        session = Mock()
        session.get.side_effect = requests.Timeout()
        places = [{"place_id": "one", "name": "Toko Satu", "website": "https://toko.test/", "google_maps_url": ""},
                  {"place_id": "two", "name": "Toko Dua", "google_maps_url": ""}]
        rows = scraper.collect_rows(session, places, delay=0)
        self.assertEqual([row["name"] for row in rows], ["Toko Satu", "Toko Dua"])
        self.assertEqual([row["status"] for row in rows], ["website_error", "no_website"])
        self.assertTrue(all(row["email"] == "" for row in rows))

    def test_limits_website_fetches(self):
        session = Mock()
        session.get.return_value = response(html=''.join(
            f'<a href="/contact/{index}">Contact</a>' for index in range(10)))
        self.assertEqual(scraper.find_emails(session, "https://toko.test/", delay=0),
                         ([], "email_not_found"))
        self.assertEqual(session.get.call_count, 3)

    @patch("scraper.scrape_maps")
    @patch("scraper.time.sleep")
    @patch("scraper.create_session")
    def test_main_writes_csv_and_json(self, create_session, sleep, scrape_maps):
        session = create_session.return_value.__enter__.return_value
        scrape_maps.return_value = [{
            "place_id": "one", "name": "=Toko Café",
            "website": "https://toko.test/", "google_maps_url": "https://maps.google.com/?cid=1",
        }]
        session.get.return_value = response(html='<a href="mailto:info@toko.id">Email</a>')
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(scraper.main(["--query", "toko di Bandung", "--output-dir", directory]), 0)
            records = json.loads((Path(directory) / "stores.json").read_text(encoding="utf-8"))
            self.assertEqual(records[0]["name"], "=Toko Café")
            with (Path(directory) / "stores.csv").open(encoding="utf-8-sig", newline="") as handle:
                records = list(csv.DictReader(handle))
            self.assertEqual(records[0]["email"], "info@toko.id")
            self.assertEqual(records[0]["name"], "'=Toko Café")
        session.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
