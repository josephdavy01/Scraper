# 🕷️ Scraper — Multi-Brand E-Commerce Product Scraper

A comprehensive Python-based web scraping framework for extracting product data from **5+ global fashion and sportswear brands** across multiple regions. The scraped data is processed, validated, stored in MongoDB, and uploaded to the Melody analytics platform.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Supported Brands](#supported-brands)
- [Architecture](#architecture)
- [Pipeline Workflow](#pipeline-workflow)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup & Installation](#setup--installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Contributing](#contributing)

---

## 🔍 Overview

This project automates the end-to-end process of scraping product information from major e-commerce websites. Each brand has its own dedicated scraper module that follows a standardized multi-step pipeline — from discovering category URLs to uploading cleaned data to a centralized database.

**Key Features:**
- 🌍 Multi-region support (India, UK, USA, UAE, Saudi Arabia, Australia, Canada, Spain, Turkey, etc.)
- 🔄 Day-of-week scheduling for region rotation
- 📊 Daily product count tracking and validation
- 🧹 Data deduplication and format verification
- 🗄️ MongoDB integration (local + remote server)
- 📤 Automated upload to Melody analytics platform
- 📝 Comprehensive logging with daily log files

---

## 🏷️ Supported Brands

| Category | Brands |
|---|---|
| **Fast Fashion** | Primark|
| **Sportswear** | Oofos, Gymshark |
| **Premium/Casual** |  Paige |
| **Indian Brands** | Snitch, Comet , enmour

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        MASTER.PY                             │
│              (Orchestrator - runs all steps)                 │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Step 1: Get Category URLs                                   │
│     ↓                                                        │
│  Step 2: Get Product URLs                                    │
│     ↓                                                        │
│  Step 3: Deduplicate Product URLs                            │
│     ↓                                                        │
│  Step 4: Daily Count Tracking                                │
│     ↓                                                        │
│  Step 5: URL Validation                                      │
│     ↓                                                        │
│  Step 6: Get Product Data (JSON)                             │
│     ↓                                                        │
│  Step 7: URL/JSON Comparison                                 │
│     ↓                                                        │
│  Step 8: Data Validation                                     │
│     ↓                                                        │
│  Step 9: Process & Transform Data                            │
│     ↓                                                        │
│  Step 10: Load to MongoDB                                    │
│     ↓                                                        │
│  Step 11: Remove Duplicate SKUs                              │
│     ↓                                                        │
│  Step 12: Check Data Format                                  │
│     ↓                                                        │
│  Step 13: Upload to Melody                                   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

> **Note:** The number of steps may vary per brand (typically 8–14 steps), but the general flow remains consistent.

---

## ⚙️ Pipeline Workflow

### 1. Category URL Discovery
Navigates the brand's website to extract all category and subcategory URLs (Men, Women, Kids, etc.).

### 2. Product URL Extraction
Crawls each category page to collect individual product page URLs.

### 3. URL Deduplication
Removes duplicate product URLs across categories to avoid redundant scraping.

### 4. Daily Count Tracking
Logs daily product counts per category for monitoring and trend analysis.

### 5. URL Validation
Verifies that collected URLs are accessible and valid.

### 6. Product Data Scraping
Fetches detailed product information (name, price, sizes, colors, images, composition, etc.) and saves as JSON files.

### 7. URL/JSON Comparison
Cross-references scraped data with URL lists to identify missing products.

### 8. Data Validation
Validates scraped data against expected schemas and formats.

### 9. Data Processing
Transforms raw JSON into structured format, maps PIDs/CIDs, and handles region-specific data.

### 10. Database Loading
Loads processed data into local MongoDB collections, organized by brand and region.

### 11. Duplicate SKU Removal
Identifies and removes duplicate SKU entries from the database.

### 12. Data Format Check
Final validation to ensure data integrity before upload.

### 13. Upload to Melody
Pushes validated data from local MongoDB to the remote Melody analytics server.

---

## 🛠️ Tech Stack

| Technology | Purpose |
|---|---|
| **Python 3.x** | Core programming language |
| **Playwright** | Browser automation for dynamic page scraping |
| **asyncio** | Asynchronous execution for concurrent scraping |
| **MongoDB / PyMongo** | Local and remote data storage |
| **tqdm** | Progress bars for scraping jobs |
| **Requests** | HTTP requests for API-based scraping |
| **Logging** | Structured logging with daily log rotation |

---

## 📁 Project Structure

```
scraper/
├── .gitignore
├── README.md
│
├── gymshark/                          # Example brand module
│   ├── master.py                  # Orchestrator — runs all steps in order
│   ├── step1_get_category_urls.py
│   ├── step2_get_product_urls.py
│   ├── step3_get_unique_product_urls.py
│   ├── step4_daily_count.py
│   ├── step5_url_validation.py
│   ├── step6_get_product_data.py
│   ├── step7_urls_json_comparison.py
│   ├── step8_data_validation.py
│   ├── step9_get_unique_pids.py
│   ├── step10_get_product_composition.py
│   ├── step11_load_to_db.py
│   ├── step12_remove_duplicate_skus.py
│   ├── step13_check_data_format.py
│   ├── step14_upload_to_melody.py
│   └── codes/                     # Region-specific variants
│       ├── step10_load_to_db_india.py
│       ├── step10_load_to_db_uk.py
│       ├── step10_load_to_db_usa.py
│       └── ...
│


---

## 🚀 Setup & Installation

### Prerequisites

- Python 3.8+
- MongoDB (local instance running on `localhost:27017`)
- Google Chrome / Chromium browser

### Installation

```bash
# Clone the repository
git clone https://github.com/josephdavy01/Scraper.git
cd Scraper

# Create a virtual environment
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# Install dependencies
pip install playwright pymongo tqdm requests

# Install Playwright browsers
playwright install chromium
```

### Environment Setup

Create a `.env` file in the project root with your MongoDB connection strings:

```env
SERVER_MONGO_URI=your_remote_mongo_uri
LOCAL_MONGO_URI=mongodb://localhost:27017
```

---

## ▶️ Usage

### Run a Full Brand Pipeline

```bash
# Navigate to the brand folder and run the master script
cd zara
python master.py
```

### Run Individual Steps

```bash
# Run a specific step for a brand
cd zara
python step1_get_category_urls.py
python step6_get_product_data.py
```

### Region Scheduling

Many brands use **day-of-week scheduling** to rotate between regions:

| Day | Regions |
|---|---|
| Monday, Wednesday, Friday | Australia, Canada, India, Saudi Arabia, Spain |
| Tuesday, Thursday, Saturday | Turkey, UAE, UK, USA |

This is handled automatically in each brand's scripts.

---

## ⚙️ Configuration

Key configuration options are typically found at the top of each script:

| Parameter | Description | Default |
|---|---|---|
| `headless` | Run browser in headless mode | `False` |
| `THRESHOLD_PERCENT` | Max count deviation for upload approval | `100` |
| `CHUNK_SIZE` | Documents per MongoDB insert batch | `5000` |
| `ALLOW_REUPLOAD` | Allow re-uploading data for the same day | `False` |

---

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/new-brand`)
3. Commit your changes (`git commit -m 'Add scraper for new brand'`)
4. Push to the branch (`git push origin feature/new-brand`)
5. Open a Pull Request

---

## 📄 License

This project is proprietary. All rights reserved.

---

<p align="center">
  Built with ❤️ for automated e-commerce data collection
</p>
