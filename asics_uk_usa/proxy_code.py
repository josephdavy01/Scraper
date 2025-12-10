import logging
import time
import random
from playwright.sync_api import sync_playwright

load_more_selector = 'a[data-test="plp-load-more"]'
product_selector = '.productTile__root'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def dismiss_popups(page):
    page.wait_for_timeout(2000) 
    
    close_selector = 'button[aria-label="Close dialog"].dialog__close'
    try:
        close_btn = page.wait_for_selector(
            close_selector, 
            state='visible', 
            timeout=20000 
        )
        if close_btn:
            logging.info("Found 'Close dialog' button. Clicking it.")
            close_btn.click(timeout=5000)
            page.wait_for_timeout(1500) 
            return
    except Exception as e:
        pass

    inmoment_overlay_selector = 'section[id^="_im_iframe_overlay"]'
    try:
        popup = page.query_selector(inmoment_overlay_selector) 
        
        if popup: 
            viewport = page.viewport_size or {'width': 1920, 'height': 1080}
            x = viewport['width'] - 10
            y = viewport['height'] - 10 
            
            page.mouse.click(x, y) 
            page.wait_for_timeout(random.uniform(1500, 2500))
            return 
        else:
            pass

    except Exception as e:
        pass

    overlay_selector = '.dialog__overlay[data-state="open"]'
    try:
        overlay = page.wait_for_selector(
            overlay_selector, 
            state='visible', 
            timeout=5000
        )
        if overlay:
            logging.info("Found .dialog__overlay. Clicking it.")
            overlay.click(timeout=5000)
            page.wait_for_timeout(1500)
            return
    except Exception as e:
        pass

    pass
    popup_selectors = [
        '[role="dialog"]', '.modal', '.popup', '.overlay', 
        '#onetrust-banner-sdk'
    ]
    
    for selector in popup_selectors:
        try:
            popup = page.query_selector(selector)
            if popup and popup.is_visible():
                logging.info(f"Detected visible popup: {selector}. Clicking bottom-right corner.")
                viewport = page.viewport_size or {'width': 1920, 'height': 1080}
                x = viewport['width'] - 10
                y = viewport['height'] - 10 
                
                page.mouse.click(x, y)
                page.wait_for_timeout(random.uniform(1500, 2500))
                logging.info(f"Clicked at ({x},{y}) to dismiss {selector}")
                return
                
        except Exception as e:
            pass

def scroll_and_click_load_more(page, current_product_count):
 
    for _ in range(3): 
        dismiss_popups(page)
        load_button = page.query_selector(load_more_selector)

        if load_button and load_button.is_visible():
            try:
                class_attr = load_button.get_attribute('class') or ''
                if 'button--isLoading_false' in class_attr:
                    logging.info(f"Clicking 'Load More' button at product count: {current_product_count}")
                    load_button.click(timeout=30000)
                    logging.info(f"Waiting for product count to increase from {current_product_count}...")
                    
                    wait_expression = f"""
                        () => {{
                            const count = document.querySelectorAll('{product_selector}').length;
                            return count > {current_product_count};
                        }}
                    """
                    
                    page.wait_for_function(wait_expression, timeout=290000) 
                    
                    logging.info("Product count successfully increased.")
                    dismiss_popups(page) 
                    return True
                        
            except Exception as e:
                if "Timeout" in str(e) and "wait_for_function" in str(e):
                   
                    logging.warning("Waited 160 seconds, but no new products were loaded. Assuming end of list.")
                    return False # Signal that loading is done

                dismiss_popups(page)
                time.sleep(random.uniform(2, 3))
                
        logging.info("Scrolling to find 'Load More' button...")
        page.evaluate("window.scrollBy(0, window.innerHeight)")
        dismiss_popups(page)
        time.sleep(random.uniform(1, 2))

    logging.info("Load More button not found after multiple scrolls.")
    return False

def scroll_and_load_more(url):
    with open('proxies.txt', 'r') as f:
        proxies = [line.strip() for line in f if line.strip()]

    tried = set()

    while True:
        available = [p for p in proxies if p not in tried]
        if not available:
            logging.error("All proxies failed or blocked.")
            return None

        proxy_str = random.choice(available)
        tried.add(proxy_str)

        parts = proxy_str.split(':')
        if len(parts) != 4:
            logging.warning(f"Skipping malformed proxy: {proxy_str}")
            continue
        server, port, username, password = parts

        try:
            with sync_playwright() as p:
                logging.info(f"Launching Firefox with proxy: {server}:{port}")
                # Set proxy directly in launch context
                browser = p.firefox.launch(headless=False )
                page = browser.new_page()
                
                
                logging.info(f"Processing: {url}")

                response = page.goto(url, wait_until='domcontentloaded', timeout=60000)
                if not response or not response.ok:
                    logging.warning(f"Page load failed with status {response.status if response else 'N/A'}. Trying next proxy.")
                    browser.close()
                    continue

                page.wait_for_selector(product_selector, timeout=100000)

                try:
                    cookie_btn_selector = 'button#onetrust-accept-btn-handler'
                    page.wait_for_selector(cookie_btn_selector, state='attached', timeout=10000)
                    cookie_btn = page.query_selector(cookie_btn_selector)
                    if cookie_btn and cookie_btn.is_visible():
                        page.evaluate(f"document.querySelector('{cookie_btn_selector}').click()")
                        time.sleep(random.uniform(1, 2))
                except Exception as e:
                    logging.warning(f"Could not click cookie banner: {e}")

                previous_count = 0
                no_change_count = 0
                max_no_change = 7
                while no_change_count < max_no_change:
                    try:
                        current_products = page.query_selector_all(product_selector)
                        current_count = len(current_products)
                        print(f'Products found: {current_count}')

                        clicked_and_loaded = scroll_and_click_load_more(page, current_count)
                        
                        if not clicked_and_loaded:
                            # This now means "button not found" OR "wait timed out"
                            logging.info("No more products loaded. Assuming all content is loaded.")
                            break # Exit the while loop

                        # Re-check count after the function returns
                        new_count = len(page.query_selector_all(product_selector))
                        logging.info(f"New product count is: {new_count}")


                        if new_count == current_count:
                        
                            logging.warning("Product count did not change after successful click/wait.")
                            no_change_count += 1
                        else:
                            no_change_count = 0 
                        
                        previous_count = new_count

                        if new_count > 3000:
                            logging.info("Reached product limit (3000+).")
                            break

                    except Exception as e:
                        logging.error(f"Scroll iteration error: {e}")
                        no_change_count += 1
                        time.sleep(random.uniform(2, 4))

                logging.info("Finished scrolling.")
                page_html = page.content()
                browser.close()

                if 'access denied' in page_html.lower() and len(page_html.strip()) < 500:
                    logging.warning("Likely Access Denied or empty page. Trying next proxy.")
                    continue
                else:
                    logging.info("Scrape successful. Returning HTML.")
                    return page_html

        except Exception as e:
            logging.error(f"Error during playwright operation with proxy {proxy_str}: {e}")
            if 'browser' in locals() and browser.is_connected():
                browser.close()
