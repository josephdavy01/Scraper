import os
import json
import smtplib
import requests # type: ignore
from email.mime.text import MIMEText
from datetime import datetime
from common import *
from dotenv import load_dotenv # type: ignore

# Load environment variables from .env if present
load_dotenv()

# Setup paths and folders
product_folder = os.path.join(WEBSITE_NAME, "PRODUCT")
product_data_folder = os.path.join(WEBSITE_NAME, "PRODUCT_DATA")
validation_folder = os.path.join(WEBSITE_NAME, "VALIDATION")
os.makedirs(validation_folder, exist_ok=True)

# Email and Slack settings from environment variables
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

def send_email_alert(subject, body, sender, receiver, smtp_server, port, login, password):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = receiver

    with smtplib.SMTP_SSL(smtp_server, port) as server:
        server.login(login, password)
        server.sendmail(sender, receiver, msg.as_string())

def send_slack_alert(webhook_url, message):
    payload = {"text": message}
    requests.post(webhook_url, json=payload)

def load_product_count(date):
    path = os.path.join(product_folder, date, "product_url_duplicate_removed.json")
    if not os.path.exists(path):
        return 0
    with open(path) as f:
        data = json.load(f)
    return sum(entry[0].get("product_count_after_dup_remove", 0) if entry else 0 for entry in data)

def load_all_expected_urls(date):
    path = os.path.join(product_folder, date, "product_url_duplicate_removed.json")
    if not os.path.exists(path):
        return set()
    with open(path) as f:
        data = json.load(f)
    urls = set()
    for entry in data:
        urls.update(entry[0].get("url", []) if entry else [])
    return urls

def load_scraped_urls(date):
    path = os.path.join(product_data_folder, date, "product_details_data_url_completed.json")
    if not os.path.exists(path):
        return set()
    with open(path) as f:
        return set(json.load(f))

def calculate_deviation(current, previous):
    # Ensure that the values are positive and not zero
    print(f"Calculating deviation: current={current}, previous={previous}")
    if previous == 0 or current == 0:  
        return None  # Avoid invalid calculation
    return round(((current - previous) / previous) * 100, 2)

# Get all valid PRODUCT folders sorted
date_folders = sorted(d for d in os.listdir(product_folder) if os.path.isdir(os.path.join(product_folder, d)))
history = []

def start_validation():
    # Track union of all previous scraped URLs
    all_previous_scraped_urls = set()
    all_previous_product_count = 0
    for idx, date in enumerate(date_folders):
        report_path = os.path.join(validation_folder, f"{date}_validation_report.json")
        
        if os.path.exists(report_path):
            print(f"Report already exists for {date}, skipping...")
            # Update union even if skipping to keep it valid for next loop
            all_previous_scraped_urls.update(load_scraped_urls(date))
            all_previous_product_count += load_product_count(date)
            continue

        # Load today’s data
        today_product_count = load_product_count(date)
        today_scraped_urls = load_scraped_urls(date)
        expected_today_urls = load_all_expected_urls(date)

        # Calculate today's deviation
        if today_product_count == 0 or len(today_scraped_urls) == 0:
            today_deviation = None
        else:
            deviation_intermediate = (today_product_count - len(today_scraped_urls)) / today_product_count
            today_deviation = round(deviation_intermediate * 100, 2)

        
        # Compare with all previous days
        deviation_from_all = calculate_deviation(today_product_count, all_previous_product_count)
        new_urls_today = list(today_scraped_urls - all_previous_scraped_urls)
        missed_urls_today = list(expected_today_urls - today_scraped_urls)

        validation = {
            "date": date,
            "total_products_after_dup_remove": today_product_count,
            "total_scraped_urls": len(today_scraped_urls),
            "today_deviation(%)": today_deviation,
            "scraped_url_count_deviation_from_all_previous_days(%)": deviation_from_all,
            "common_scraped_urls_with_all_previous_days": len(today_scraped_urls & all_previous_scraped_urls),
            "new_product_url_count": len(new_urls_today),
            "missed_product_url_count": len(missed_urls_today),

            # Put the actual lists at the end
            "new_product_urls": new_urls_today,
            "missed_product_urls": missed_urls_today
        }

        # Save the validation report to file
        with open(report_path, "w") as f:
            json.dump(validation, f, indent=4)

        print(f"Report generated for {date} → {report_path}")

        # Log deviation if it's not zero
        if today_deviation != 0:
            log_msg = f"[{date}] Today's Deviation: {today_deviation if today_deviation is not None else 'N/A'}"
            print(log_msg)

            # Email alert
            # if EMAIL_SENDER and EMAIL_RECEIVER and EMAIL_PASSWORD:
            #     try:
            #         send_email_alert(
            #             subject=f"Scraping Deviation Alert - {date}",
            #             body=log_msg,
            #             sender=EMAIL_SENDER,
            #             receiver=EMAIL_RECEIVER,
            #             smtp_server=SMTP_SERVER,
            #             port=SMTP_PORT,
            #             login=EMAIL_SENDER,
            #             password=EMAIL_PASSWORD
            #         )
            #     except Exception as e:
            #         print(f"Failed to send email: {e}")

            # # Slack alert
            # if SLACK_WEBHOOK_URL:
            #     try:
            #         send_slack_alert(
            #             webhook_url=SLACK_WEBHOOK_URL,
            #             message=f"*Scraping Deviation Alert - {date}*\\n{log_msg}"
            #         )
            #     except Exception as e:
            #         print(f"Failed to send Slack alert: {e}")

        # Update historical data after processing
        all_previous_scraped_urls.update(today_scraped_urls)
        all_previous_product_count += today_product_count

def start_step8():
    start_validation()
    return True