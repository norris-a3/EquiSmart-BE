import random
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["socialMedia"]
posts_collection = db["posts"]

# Loop through all existing posts in collection.
result = posts_collection.update_many(
    {},
    {
        "$set": {    
            # Add random metrics to make social feed look active.
            "views_count": random.randint(1, 5000),
            "shares_count": random.randint(1, 5000),
            # Add nested mock analytics array.
            "weekly_impressions": [
                { "week": "Week 1", "impressions": random.randint(5000, 8000) },
                { "week": "Week 2", "impressions": random.randint(5000, 8000) },
                { "week": "Week 3", "impressions": random.randint(5000, 8000) },
            ]
        }
    }
)

print(f"Posts dataset successfully enhanced with mock metrics.")