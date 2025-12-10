import pymongo
import json
from datetime import datetime
from collections import defaultdict, Counter
import re
 
class DataValidationReport:
    def __init__(self, connection_string="mongodb://localhost:27017", db_name='tg_analytics'):
        self.client = pymongo.MongoClient(connection_string)
        self.db = self.client[db_name]
        self.report = {}
       
    def validate_database(self, brand='uniqlo', countries=['usa', 'uk', 'australia', 'spain', 'canada'], product_types=['apparel']):
        """Main validation function - validates all collections for a brand"""
        print(f"🔍 Starting validation for {brand.upper()} brand...")
        print("=" * 70)
       
        for country in countries:
            for product_type in product_types:
                if product_type == 'apparel':
                    collection_name = f'crawler_sink_{brand}_{country}'
                else:
                    collection_name = f'crawler_sink_{brand}_{country}_{product_type}'
               
                print(f"\n📊 Validating {country.upper()} {product_type.upper()}...")
                print("-" * 50)
               
                collection = self.db[collection_name]
                self.validate_collection(collection, country, product_type, brand)
       
        self.generate_summary_report(brand)
        return self.report
 
    def validate_collection(self, collection, country, product_type, brand):
        """Validate a single collection"""
        try:
            total_docs = collection.count_documents({})
            if total_docs == 0:
                print(f"⚠️  WARNING: No documents found in {country} {product_type}")
                return
               
            print(f"📈 Total Records: {total_docs:,}")
           
            # Initialize report for this collection
            key = f"{country}_{product_type}"
            self.report[key] = {
                'total_records': total_docs,
                'validation_results': {},
                'data_quality': {},
                'business_metrics': {}
            }
           
            # Run all validations
            self.validate_required_fields(collection, key)
            self.validate_data_types(collection, key)
            self.validate_business_logic(collection, key, product_type)
            self.validate_data_consistency(collection, key)
            self.validate_pricing(collection, key)
            self.validate_urls_and_references(collection, key, brand)
            self.calculate_business_metrics(collection, key)
           
        except Exception as e:
            print(f"❌ Error validating {country} {product_type}: {e}")
 
    def validate_required_fields(self, collection, key):
        """Check for missing required fields"""
        print("🔍 Checking required fields...")
       
        required_fields = [
            'product_id', 'sku', 'title', 'price', 'launch_price',
            'gender', 'size_name', 'availability', 'product_ref_code'
        ]
       
        missing_fields = {}
        for field in required_fields:
            missing_count = collection.count_documents({field: {"$exists": False}})
            null_count = collection.count_documents({field: None})
            empty_count = collection.count_documents({field: ""})
           
            total_missing = missing_count + null_count + empty_count
            if total_missing > 0:
                missing_fields[field] = {
                    'missing': missing_count,
                    'null': null_count,
                    'empty': empty_count,
                    'total': total_missing
                }
       
        self.report[key]['validation_results']['missing_fields'] = missing_fields
       
        if missing_fields:
            print(f"⚠️  Found missing required fields:")
            for field, counts in missing_fields.items():
                print(f"   • {field}: {counts['total']} records")
        else:
            print("✅ All required fields present")
 
    def validate_data_types(self, collection, key):
        """Validate data types"""
        print("🔍 Checking data types...")
       
        type_issues = {}
       
        # Check price fields are numeric
        invalid_prices = collection.count_documents({
            "$or": [
                {"price": {"$type": "string"}},
                {"launch_price": {"$type": "string"}}
            ]
        })
       
        if invalid_prices > 0:
            type_issues['price_not_numeric'] = invalid_prices
           
        # Check arrays are actually arrays
        invalid_arrays = collection.count_documents({
            "$or": [
                {"age_group": {"$not": {"$type": "array"}}},
                {"age_range": {"$not": {"$type": "array"}}},
                {"images": {"$not": {"$type": "array"}}}
            ]
        })
       
        if invalid_arrays > 0:
            type_issues['invalid_arrays'] = invalid_arrays
           
        self.report[key]['validation_results']['type_issues'] = type_issues
       
        if type_issues:
            print(f"⚠️  Data type issues found:")
            for issue, count in type_issues.items():
                print(f"   • {issue}: {count} records")
        else:
            print("✅ Data types are correct")
 
    def validate_business_logic(self, collection, key, product_type):
        """Validate business logic rules"""
        print("🔍 Checking business logic...")
       
        business_issues = {}
       
        # Price validation
        negative_prices = collection.count_documents({"price": {"$lt": 0}})
        zero_prices = collection.count_documents({"price": 0})
        invalid_launch_price = collection.count_documents({
            "$expr": {"$lt": ["$launch_price", "$price"]}
        })
       
        if negative_prices > 0:
            business_issues['negative_prices'] = negative_prices
        if zero_prices > 0:
            business_issues['zero_prices'] = zero_prices
        if invalid_launch_price > 0:
            business_issues['launch_price_less_than_price'] = invalid_launch_price
           
        # Gender validation
        valid_genders = ['male', 'female', 'kids', 'unisex']
        invalid_gender = collection.count_documents({
            "gender": {"$nin": valid_genders}
        })
        if invalid_gender > 0:
            business_issues['invalid_gender'] = invalid_gender
           
        # Product-specific validations
        if product_type == 'footwear':
            # Check footwear-specific fields
            missing_materials = collection.count_documents({
                "$and": [
                    {"sole_material": None},
                    {"upper_material": None}
                ]
            })
            if missing_materials > 0:
                business_issues['missing_materials'] = missing_materials
               
        self.report[key]['validation_results']['business_issues'] = business_issues
       
        if business_issues:
            print(f"⚠️  Business logic issues:")
            for issue, count in business_issues.items():
                print(f"   • {issue}: {count} records")
        else:
            print("✅ Business logic validation passed")
 
    def validate_data_consistency(self, collection, key):
        """Check data consistency"""
        print("🔍 Checking data consistency...")
       
        consistency_issues = {}
       
        # Check for duplicate SKUs
        pipeline = [
            {"$group": {"_id": "$sku", "count": {"$sum": 1}}},
            {"$match": {"count": {"$gt": 1}}},
            {"$count": "duplicate_skus"}
        ]
        duplicate_result = list(collection.aggregate(pipeline))
        duplicate_skus = duplicate_result[0]['duplicate_skus'] if duplicate_result else 0
       
        if duplicate_skus > 0:
            consistency_issues['duplicate_skus'] = duplicate_skus
           
        # Check product_id format
        invalid_product_ids = collection.count_documents({
            "product_id": {"$not": {"$regex": r"^uni\d+$"}}
        })
        if invalid_product_ids > 0:
            consistency_issues['invalid_product_id_format'] = invalid_product_ids
           
        self.report[key]['validation_results']['consistency_issues'] = consistency_issues
       
        if consistency_issues:
            print(f"⚠️  Consistency issues:")
            for issue, count in consistency_issues.items():
                print(f"   • {issue}: {count} records")
        else:
            print("✅ Data consistency validated")
 
    def validate_pricing(self, collection, key):
        """Validate pricing patterns"""
        print("🔍 Analyzing pricing...")
       
        pricing_stats = {}
       
        # Price statistics
        price_pipeline = [
            {"$group": {
                "_id": None,
                "avg_price": {"$avg": "$price"},
                "min_price": {"$min": "$price"},
                "max_price": {"$max": "$price"},
                "avg_launch_price": {"$avg": "$launch_price"}
            }}
        ]
       
        price_result = list(collection.aggregate(price_pipeline))
        if price_result:
            stats = price_result[0]
            pricing_stats = {
                'avg_price': round(stats['avg_price'], 2),
                'min_price': stats['min_price'],
                'max_price': stats['max_price'],
                'avg_launch_price': round(stats['avg_launch_price'], 2)
            }
           
        # Discount analysis
        discount_pipeline = [
            {"$addFields": {
                "discount_percentage": {
                    "$multiply": [
                        {"$divide": [
                            {"$subtract": ["$launch_price", "$price"]},
                            "$launch_price"
                        ]}, 100
                    ]
                }
            }},
            {"$match": {"discount_percentage": {"$gt": 0}}},
            {"$group": {
                "_id": None,
                "avg_discount": {"$avg": "$discount_percentage"},
                "max_discount": {"$max": "$discount_percentage"},
                "discounted_items": {"$sum": 1}
            }}
        ]
       
        discount_result = list(collection.aggregate(discount_pipeline))
        if discount_result:
            discount_stats = discount_result[0]
            pricing_stats.update({
                'avg_discount_percentage': round(discount_stats['avg_discount'], 2),
                'max_discount_percentage': round(discount_stats['max_discount'], 2),
                'discounted_items_count': discount_stats['discounted_items']
            })
           
        self.report[key]['data_quality']['pricing'] = pricing_stats
        print(f"💰 Price range: ${pricing_stats.get('min_price', 0)} - ${pricing_stats.get('max_price', 0)}")
        print(f"💰 Average price: ${pricing_stats.get('avg_price', 0)}")
 
    def validate_urls_and_references(self, collection, key, brand):
        """Validate URLs and reference codes"""
        print("🔍 Checking URLs and references...")
       
        url_issues = {}
       
        # Check URL format
        invalid_urls = collection.count_documents({
            "url": {"$not": {"$regex": f"https://.*.{brand}.com/.*"}}
        })
        if invalid_urls > 0:
            url_issues['invalid_url_format'] = invalid_urls
           
        # Check image URLs
        no_images = collection.count_documents({
            "$or": [
                {"images": {"$size": 0}},
                {"images": None}
            ]
        })
        if no_images > 0:
            url_issues['no_images'] = no_images
           
        self.report[key]['validation_results']['url_issues'] = url_issues
       
        if url_issues:
            print(f"⚠️  URL issues:")
            for issue, count in url_issues.items():
                print(f"   • {issue}: {count} records")
        else:
            print("✅ URLs and references validated")
 
    def calculate_business_metrics(self, collection, key):
        """Calculate business metrics"""
        print("📊 Calculating business metrics...")
       
        metrics = {}
       
        # Gender distribution
        gender_pipeline = [
            {"$group": {"_id": "$gender", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        gender_dist = {doc['_id']: doc['count'] for doc in collection.aggregate(gender_pipeline)}
       
        # Size distribution
        size_pipeline = [
            {"$group": {"_id": "$size_name", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        size_dist = {doc['_id']: doc['count'] for doc in collection.aggregate(size_pipeline)}
       
        # Product count (unique products)
        unique_products = len(collection.distinct("product_id"))
        unique_colors = len(collection.distinct("color_id"))
       
        metrics = {
            'unique_products': unique_products,
            'unique_colors': unique_colors,
            'gender_distribution': gender_dist,
            'top_sizes': size_dist,
            'total_skus': collection.count_documents({})
        }
       
        self.report[key]['business_metrics'] = metrics
       
        print(f"🎯 Unique products: {unique_products}")
        print(f"🎯 Unique colors: {unique_colors}")
        print(f"🎯 Gender distribution: {gender_dist}")
 
    def generate_summary_report(self, brand):
        """Generate final summary report"""
        print("\n" + "=" * 70)
        print(f"📋 VALIDATION SUMMARY REPORT - {brand.upper()}")
        print("=" * 70)
       
        total_records = sum([data['total_records'] for data in self.report.values()])
        print(f"📊 Total Records Processed: {total_records:,}")
       
        # Summary of issues
        all_issues = defaultdict(int)
        for collection_data in self.report.values():
            validation_results = collection_data.get('validation_results', {})
            for category, issues in validation_results.items():
                if isinstance(issues, dict):
                    for issue, count in issues.items():
                        all_issues[issue] += count
                       
        if all_issues:
            print(f"\n⚠️  ISSUES FOUND:")
            for issue, count in sorted(all_issues.items(), key=lambda x: x[1], reverse=True):
                print(f"   • {issue}: {count} records")
        else:
            print(f"\n✅ NO CRITICAL ISSUES FOUND!")
           
        # Business insights
        print(f"\n📈 BUSINESS INSIGHTS:")
        total_products = sum([data['business_metrics'].get('unique_products', 0) for data in self.report.values()])
        total_colors = sum([data['business_metrics'].get('unique_colors', 0) for data in self.report.values()])
       
        print(f"   • Total Unique Products: {total_products}")
        print(f"   • Total Color Variations: {total_colors}")
       
        # Collection breakdown
        print(f"\n📊 COLLECTION BREAKDOWN:")
        for key, data in self.report.items():
            print(f"   • {key}: {data['total_records']:,} records")
           
        print(f"\n✅ VALIDATION COMPLETED!")
        print("=" * 70)
 
    def export_report(self, filename=None):
        """Export detailed report to JSON"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"validation_report_{timestamp}.json"
           
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.report, f, indent=2, default=str)
           
        print(f"📄 Detailed report exported to: {filename}")
       
    def close(self):
        """Close database connection"""
        self.client.close()
 
# Usage example
if __name__ == "__main__":
    # Initialize validator
    validator = DataValidationReport()
   
    # Run validation for PUMA across all countries and product types
    report = validator.validate_database(
        brand='uniqlo',
        countries=['usa', 'uk', 'australia', 'spain', 'canada', 'india'],  
        product_types=['apparel']
    )
   
    # Export detailed report
    validator.export_report()
   
    # Close connection
    validator.close()