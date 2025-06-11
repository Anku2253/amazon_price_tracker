import requests
from bs4 import BeautifulSoup
import time
import random

class AmazonScraper:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
            "Accept-Language": "en-US,en;q=0.9"
        }

    def scrape_product(self, url, max_retries=3):
        """Scrapes product title and price from an Amazon product URL with retry and CAPTCHA detection."""
        delay = 2
        for attempt in range(1, max_retries + 1):
            try:
                print(f"🌀 Attempt {attempt} to scrape: {url}")
                response = requests.get(url, headers=self.headers, timeout=10)

                if self.is_captcha_page(response):
                    print("⚠️ CAPTCHA or blocked request detected. Retrying...")
                    self.save_debug_html(response.text, f"captcha_attempt_{attempt}.html")
                    time.sleep(delay)
                    delay *= 2  # exponential backoff
                    continue

                soup = BeautifulSoup(response.content, "html.parser")

                # Extract product title
                title_tag = soup.find("span", id="productTitle")
                title = title_tag.get_text(strip=True) if title_tag else None

                # Extract product price
                price = None
                price_selectors = [
                    ("span", {"id": "priceblock_dealprice"}),
                    ("span", {"id": "priceblock_ourprice"}),
                    ("span", {"id": "price_inside_buybox"}),
                    ("span", {"class": "a-price-whole"}),
                    ("span", {"class": "a-offscreen"})
                ]

                for tag, attrs in price_selectors:
                    price_tag = soup.find(tag, attrs=attrs)
                    if price_tag:
                        price_str = price_tag.get_text(strip=True).replace(",", "").replace("₹", "").replace("$", "")
                        try:
                            price = float(price_str.split()[0])
                            break
                        except:
                            continue

                if not title or price is None:
                    print("❌ Could not extract title or price.")
                    return None

                return {
                    "title": title,
                    "price": price
                }

            except Exception as e:
                print(f"🔥 Error on attempt {attempt}: {e}")
                time.sleep(delay)
                delay *= 2

        print("🛑 Max retries reached. Failed to scrape.")
        return None

    def is_captcha_page(self, response):
        """Check if response is likely a CAPTCHA or bot block page."""
        if response.status_code != 200:
            return True
        lower = response.text.lower()
        return "captcha" in lower or "enter the characters you see below" in lower or "/errors/validatecaptcha" in response.url

    def save_debug_html(self, html_text, filename="captcha_debug.html"):
        """Saves the HTML response for inspection."""
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html_text)
