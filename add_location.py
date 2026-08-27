import random
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["socialMedia"]
posts_collection = db["posts"]

# Define anchor geographic bounding boxes [min_lng, min_lat, max_lng, max_lat] per language.
language_regions = {
    "English": [-0.1278, 51.5074, -0.0878, 51.5374],  # London area
    "Spanish": [-3.7038, 40.4168, -3.6738, 40.4468],  # Madrid area
    "German": [13.4050, 52.5200, 13.4450, 52.5400],   # Berlin area
    "French": [2.3522, 48.8566, 2.3922, 48.8866],    # Paris area
    "Portuguese": [-9.1393, 38.7223, -9.1093, 38.7523], # Lisbon area
    "Dutch": [4.9041, 52.3676, 4.9441, 52.3976]      # Amsterdam area
}

# Fallback default location if language doesn't match above (e.g., general coordinates).
default_box = [-0.1278, 51.5074, -0.0878, 51.5374]

# Loop through posts and assign coordinates based on language.
for post in posts_collection.find():
    lang = post.get("language", "English")
    box = language_regions.get(lang, default_box)
    
    # Randomly scatter coordinates within that language's region box.
    rand_lng = random.uniform(box[0], box[2])
    rand_lat = random.uniform(box[1], box[3])
    
    posts_collection.update_one(
        { "_id": post["_id"] },
        {
            "$set": {
                "location": {
                    "type": "Point",
                    "coordinates": [rand_lng, rand_lat]
                }
            }
        }
    )

print("Successfully added GeoJSON location coordinates based on post languages!")