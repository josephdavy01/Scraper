import os
import time
import json
import logging
from datetime import date
from bs4 import BeautifulSoup
from seleniumbase import Driver
from selenium.webdriver.common.by import By

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def click_continue_shopping(driver):
    try:
        # The button is a <button> element, not an <input>
        continue_button = driver.find_element(By.XPATH, "//button[@type='submit' and contains(text(), 'Continue shopping')]")
        if continue_button:
            continue_button.click()
            logging.info("Clicked on 'Continue Shopping' button.")
            time.sleep(1)  # Wait for the page to load after clicking
    except Exception as e:
        logging.error(f"Error clicking 'Continue Shopping' button: {str(e)}")

def is_validation(soup):
    validation_tag = soup.find('form', {'action': '/errors/validateCaptcha'})
    if validation_tag:
        logging.warning("Validation page detected.")
        return True
    return False

def process_url(driver, url):
    driver.uc_open_with_reconnect('https://www.amazon.in/', reconnect_time=4)
    time.sleep(1)
    # Get page source
    page_source = driver.get_page_source()
    soup = BeautifulSoup(page_source, 'html.parser')

    check_validation = is_validation(soup)
    if check_validation:
        click_continue_shopping(driver)

    categories = {}
    try:
        # Navigate to the URL
        logging.info(f"Navigating to: {url}")
        driver.uc_open_with_reconnect(url, reconnect_time=4)
        time.sleep(2)  # Wait for the page to load completely
        
        # Get page source
        page_source = driver.get_page_source()
        soup = BeautifulSoup(page_source, 'html.parser')

        ui_tag = soup.find('ul', {'class': 'Navigation__navList__HrEra'})
        if ui_tag:
            li_tags = ui_tag.find_all('a', href=True)
            for a_tag in li_tags:
                category_name = a_tag.find('span').get_text(strip=True).lower().replace(' ', '-')
                if category_name not in ['home', 'accessories', 'socks', 'masks']:
                    category_link = 'https://www.amazon.in' + a_tag['href'].split('?')[0]
                    categories[category_name] = category_link
                    logging.info(f"Category: {category_name}, Link: {category_link}")
        else:
            logging.warning("No navigation list found on the page.")
        return categories
    except Exception as e:
        logging.error(f"Error occurred while scraping: {str(e)}")
        return {}
    
if __name__ == "__main__":
    # Create output directory based on today's date
    today_str = date.today().strftime('%Y-%m-%d')
    output_path = f'Data/{today_str}/Item_urls'
    os.makedirs(output_path, exist_ok=True)

    brand = {
        'xyxx' : 'https://www.amazon.in/stores/page/FDE15BA7-8B84-49D2-B50E-B29D0B7B2F3A'
    }

    # Initialize driver with UC mode enabled (headless=False for debugging, set to True for production)
    driver = Driver(uc=True, headless=False)

    
    try:
        for brand, url in brand.items():
            output_file = f'{output_path}/amazon_{brand}_category_urls.json'
            categories = process_url(driver, url)

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(categories, f, ensure_ascii=False, indent=4)
            logging.info(f"Saved category URLs to {output_file}")
    finally:
        # Close the browser and end the session
        driver.quit()
