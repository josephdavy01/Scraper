from datetime import datetime
from step1_get_category_url_usa_uk import get_category_urls
from step2_get_product_urls_uk import get_product_urls_uk
from step3_get_product_urls_usa import get_product_urls_usa
from step4_get_unique_product_urls import unique_urls
from step5_daily_count import daily_count
from step6_url_validation import url_validation
from step7_get_product_data_uk import product_data_uk
from step7_get_product_data_usa import product_data_usa
from step8_pids_json_comparison import json_comparision
from step9_data_validation import data_validate

def main():
    TODAY = datetime.now().strftime('%A')
    
    if TODAY in ['Monday','Tuesday','Wednesday', 'Thursday','Friday', 'Saturday']:
        # get_category_urls()
        # print("!!!! category urls processed!")
        get_product_urls_uk()
        get_product_urls_usa()
        print("!!!! product urls processed!")
        unique_urls()
        print("!!!! unique urls processed!")
        # daily_count()
        # print("!!!! daily count processed!")
        # url_validation()
        # print("!!!! url validation processed!")
        product_data_uk()
        product_data_usa()
        print("!!!! product data processed!")
        json_comparision()
        print("!!!! json comparison processed!")
        data_validate()
        print("!!!! data validation processed!")
        print("Script completed successfully.")
    else:
        print(f"Today is {TODAY}. Script only runs on Tuesday, Thursday, Saturday.")

if __name__ == "__main__":
    main()
