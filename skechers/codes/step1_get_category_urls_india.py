import os
import json
import time
import logging
import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

countries = {
    'India': 'https://www.skechers.in/'
}

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_links_by_gender(soup):    
    a_tags = soup.find_all("a", href=True, id=True)
    
    # Create the main dictionary with all links
    all_links = {
        a['id']: a['href']
        for a in a_tags
    }
    
    # Separate by gender
    women_links = {}
    men_links = {}
    kids_links = {}
    
    for link_id, href in all_links.items():
        # Check for Women's links
        if 'landing' in href:
            continue
        elif 'featured' in href.split('/')[-1]:
            continue
        if (link_id.endswith('_W') or 
            link_id in ['Women'] or
            'Women' in link_id):
            women_links[link_id] = href
        
        # Check for Men's links
        if 'landing' in href:
            continue
        elif 'featured' in href.split('/')[-1]:
            continue
        elif (link_id.endswith('_M') or 
              link_id in ['Men'] or 
              'Men' in link_id):
            men_links[link_id] = href
        
        # Check for Kids' links
        if 'landing' in href:
            continue
        elif 'featured' in href.split('/')[-1]:
            continue
        elif (link_id.endswith('_K') or 
              link_id in ['Kids'] or
              'Kids' in link_id):
            kids_links[link_id] = href
    
    return {
        'women': women_links,
        'men': men_links,
        'kids': kids_links
    }
    
if __name__ == "__main__":
    # Get today's date
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page() 

        for country, url in countries.items():
            logging.info(f'Processing {country} now...')
            
            # Navigate to the URL
            page.goto(url)
            time.sleep(5)  
            
            # Get the HTML content
            html_content = page.content()
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Get category data using the function
            category_links = get_links_by_gender(soup)

            if not category_links:
                logging.warning(f"No category links found for {country}")
            else:
                logging.info(f"Found categories: {list(category_links.keys())}")

            # Create country folder with full structure
            out_dir = f'{country}/Data/{today_str}/Item_urls'
            os.makedirs(out_dir, exist_ok=True)
            json_file_path = f'{out_dir}/category_urls.json'

            if category_links:
                with open(json_file_path, 'w', encoding='utf-8') as f:
                    json.dump(category_links, f, ensure_ascii=False, indent=4)

                logging.info(f'{country} category URLs saved to {json_file_path}')
            else:
                logging.warning(f'{country} category file not saved — no data.')

        browser.close()