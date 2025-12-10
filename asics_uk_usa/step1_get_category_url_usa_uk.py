from seleniumbase import Driver
from urllib.parse import urljoin
from datetime import datetime
from typing import Dict
import json, os, time

BASE_URL_dict = {
    "USA": "https://www.asics.com/us/en-us/",
    "UK": "https://www.asics.com/gb/en-gb/",
}

class CategoryScraper:
    def __init__(self, country: str = "USA") -> None:
        if country not in BASE_URL_dict:
            raise ValueError(f"Country {country} not supported. Available: {list(BASE_URL_dict.keys())}")
        
        self.country = country
        self.base_url = BASE_URL_dict[country]
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/118.0.0.0 Safari/537.36"
            )
        }
        print(f"Initialized scraper for {country}: {self.base_url}")

    def fetch_main_categories(self) -> Dict[str, str]:
        driver = Driver(uc=True, headless=False)
        driver.get(self.base_url)

        # Handle cookie popup
        try:
            driver.click("#onetrust-accept-btn-handler")
        except Exception:
            pass

        time.sleep(2)

        main_categories = {}

        # Get count of category buttons
        initial_buttons = driver.find_elements("css selector", 'button[data-test="mega-menu-first-level-desktop"]')
        total = len(initial_buttons)
        print(f"Found {total} main category buttons\n")

        # Iterate by index, re-fetching each time
        for i in range(total):
            try:
                category_buttons = driver.find_elements("css selector", 'button[data-test="mega-menu-first-level-desktop"]')
                if i >= len(category_buttons):
                    break
                button = category_buttons[i]

                category_name = button.text.strip().lower()
                print(f"Processing main category: {category_name}")

                button.click()
                time.sleep(1.5)

                current_url = driver.current_url
                clean_url = current_url.split("?")[0]

                main_categories[category_name] = clean_url
                print(f"  ✓ Main URL: {clean_url}")

                # Go back to homepage
                driver.get(self.base_url)
                time.sleep(1)

                try:
                    driver.click("#onetrust-accept-btn-handler")
                except Exception:
                    pass

            except Exception as e:
                print(f"  ✗ Error processing category {i}: {e}")
                try:
                    driver.get(self.base_url)
                    time.sleep(1)
                except:
                    pass
                continue

        # Also check for direct links
        try:
            direct_links = driver.find_elements("css selector", 'nav a[href*="/c/"]')
            for link in direct_links:
                try:
                    link_text = link.text.strip().lower()
                    href = link.get_attribute("href")

                    if href and link_text and link_text not in main_categories:
                        full_url = urljoin(self.base_url, href)
                        clean_url = full_url.split("?")[0]
                        main_categories[link_text] = clean_url
                        print(f"Found direct link: {link_text} -> {clean_url}")
                except:
                    continue
        except Exception as e:
            print(f"Error finding direct links: {e}")

        print(f"\n{'='*50}")
        print(f"Total main categories: {len(main_categories)}")
        print(f"{'='*50}")

        driver.quit()
        return main_categories

    def _dump_json(self, data: Dict[str, str]) -> None:
        today = datetime.today().strftime("%Y-%m-%d")
        path = os.path.join(self.country, "Data", today, "Item_urls")
        os.makedirs(path, exist_ok=True)

        out_file = os.path.join(path, f"{self.country}_category_urls.json")
        with open(out_file, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=4, ensure_ascii=False)

        print(f"Saved to {out_file}")


def get_category_urls():
    countries_to_process = list(BASE_URL_dict.keys())

    for country in countries_to_process:
        print(f"\n{'='*50}")
        print(f"Processing {country}")
        print(f"{'='*50}\n")

        try:
            scraper = CategoryScraper(country)
            categories = scraper.fetch_main_categories()
            scraper._dump_json(categories)
            print(f"\n✓ {country} completed successfully!\n")

        except Exception as e:
            print(f"\n✗ {country} failed: {e}\n")
            continue

    print(f"\n{'='*50}")
    print("✓ All selected countries processed!")
    print(f"{'='*50}")


if __name__ == "__main__":
    get_category_urls()