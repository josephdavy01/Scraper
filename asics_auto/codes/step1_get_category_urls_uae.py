import os
import json
from datetime import datetime
from playwright.sync_api import sync_playwright

def scrape_asics_uae(url="https://me.asics.com/en-ae/", country="UAE"):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=200)  # headless=True after debugging
        page = browser.new_page()
        page.goto(url, timeout=80000)
        page.wait_for_timeout(10000)
        popup_closed = False
        for selector in ["button.action-close", "button[aria-label='Close']", "div.modal-popup._show button"]:
            try:
                btn = page.locator(selector)
                if btn.is_visible():
                    btn.click(force=True)
                    page.wait_for_timeout(1000)
                    print(f" Closed popup using selector: {selector}")
                    popup_closed = True
                    break
            except Exception:
                continue
        if not popup_closed:
            page.evaluate("""() => {
        const modal = document.querySelector("aside.modal-popup._show");
        if (modal) modal.remove();
        const overlay = document.querySelector("div.modals-overlay.asics-newsletter-modal-backdrop");
        if (overlay) overlay.remove();
        }""")
        print("Popup and overlay forcibly removed")
        page.wait_for_selector("nav.revton-navigation")
        categories = {}
        main_categories = page.locator("ul[role='menu'] > li.revton-navigation__item")
        count = main_categories.count()
        for i in range(count):
            li = main_categories.nth(i)
            li.hover()
            page.wait_for_timeout(1000)
            main_name = li.locator("span").first.inner_text().strip()
            categories[main_name] = {}
            if li.locator("ul.revton-navigation__submenu__list.__level1").count() == 0:
                if li.locator("a").count() > 0:
                    url = li.locator("a").first.get_attribute("href")
                    categories[main_name][main_name] = url
            else:
                sub_lis = li.locator("ul.revton-navigation__submenu__list.__level1 > li")
                for j in range(sub_lis.count()):
                    sub_li = sub_lis.nth(j)
                    sub_name = sub_li.locator("span").first.inner_text().strip()
                    if "view all" in sub_name.lower():
                        continue
                    try:
                        sub_li.hover(force=True)
                        page.wait_for_timeout(600)
                    except Exception:
                        pass
                    if sub_li.locator("ul.revton-navigation__submenu__list.__level2").count() > 0:
                        sub2_lis = sub_li.locator("ul.revton-navigation__submenu__list.__level2 > li")
                        for k in range(sub2_lis.count()):
                            sub2_li = sub2_lis.nth(k)
                            sub2_name = sub2_li.locator("span").first.inner_text().strip()
                            url = sub2_li.locator("a").first.get_attribute("href")
                            if "view all" in sub2_name.lower():
                                continue
                            key = f"{sub_name}_{sub2_name}"
                            categories[main_name][key] = url
                    else:
                        if sub_li.locator("a").count() > 0:
                            url = sub_li.locator("a").first.get_attribute("href")
                            categories[main_name][sub_name] = url
        browser.close()
    today_str = datetime.today().strftime("%Y-%m-%d")
    base_path = f"{country}/Data/{today_str}/Item_urls"
    os.makedirs(base_path, exist_ok=True)
    out_file = f"{base_path}/{country}_category_urls.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(categories, f, indent=4, ensure_ascii=False)
    print(f"Categories saved to {out_file}")
    
if __name__ == "__main__":
    scrape_asics_uae()
