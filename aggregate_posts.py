from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["socialMedia"]
posts_collection = db["posts"]

# Define the aggregation pipeline.
pipeline = [
    # Stage 1: Filter posts written in English.
    { "$match": { "language": "English" } },
    
    # Stage 2: Sort by engagement in descending order (-1 means highest first).
    { "$sort": { "engagement": -1 } },
    
    # Stage 3: Select which fields to show (1 to show, 0 to hide _id if desired).
    { "$project": { "_id": 0, "text": 1, "engagement": 1, "language": 1 } }
]

# Run the aggregation and print results.
results = posts_collection.aggregate(pipeline)

print("Top English Social Media Posts by Engagement:")
for post in results:
    print(f"Engagement: {post['engagement']} | Text: {post['text']}")