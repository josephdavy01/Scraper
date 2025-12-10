from data_upload import copy_mongo_collections
from datetime import date, datetime


today = date.today()
fetch_date =  today.strftime('%Y-%m-%d')
# fetch_date = '2025-06-02'

# Get current datetime and weekday name
dt = datetime.now()
day = dt.strftime('%A')
# day = 'Monday'

if day in ['Monday', 'Wednesday', 'Friday']:
    """
        Canada - crawler_sink_lululemon_canada
        USA - crawler_sink_lululemon_usa
    """
    copy_mongo_collections(
        source_collections=['tg_analytics.crawler_sink_lululemon_canada'],
        target_collection='tg_analytics.crawler_sink_lululemon_canada',
        scrape_date=fetch_date,
        dry_run=False,
        force_upload=False

    )

    copy_mongo_collections(
        source_collections=['tg_analytics.crawler_sink_lululemon_usa'],
        target_collection='tg_analytics.crawler_sink_lululemon_usa',
        scrape_date=fetch_date,
        dry_run=False,
        force_upload=False
    )