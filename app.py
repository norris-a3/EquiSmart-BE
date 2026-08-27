import uuid,random
import jwt
import datetime
from functools import wraps
from flask import Flask, make_response, jsonify, request
from pymongo import MongoClient
from bson.objectid import ObjectId
from bson.errors import InvalidId
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'

#connect to mongodb

client = MongoClient("mongodb://localhost:27017/")
db = client["socialMedia"]
posts_collection = db["posts"]
comments_collection = db["comments"]
users_collection = db["users"]


#DECORATOR
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorisation' in request.headers:
            token_string = request.headers['Authorisation']
            if token_string.startswith("Bearer "):
                token = token_string.split(" ")[1]
        
        if not token:
            return make_response( jsonify( {"ERROR" : "Token Is Missing"} ), 401 )
        
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = users_collection.find_one({"_id": ObjectId(data['user_id'])})
            if not current_user:
                return make_response( jsonify( {"ERROR" : "User Not Found"} ), 401 )
            
            current_user["_id"] = str(current_user["_id"])

        except jwt.ExpiredSignatureError as e:
            return make_response( jsonify( {"ERROR" : "Token Has Expired", "details": str(e)} ), 401 )
        except jwt.InvalidTokenError as e:
            return make_response( jsonify( {"ERROR" : "Token Is Invalid", "details": str(e)} ), 401 )
        
        return f(current_user, *args, **kwargs)
    return decorated

#POSTS ENDPOINTS

#GET - get all posts

@app.route("/api/v1.0/posts/", methods=["GET"])
def show_all_posts():

    #default pagination values
    page_num = int(request.args.get('pn', 1))
    page_size = int(request.args.get('ps', 10))
    skip_count = page_size * (page_num -1)
    
    #query mongodb - not hiding id field
    cursor = posts_collection.find({}).skip(skip_count).limit(page_size)
    
    #create empty list
    post_list = []

    #loop through cursor
    for post in cursor:
        post["_id"] = str(post["_id"])
        post_list.append(post)

    return make_response( jsonify ( post_list ), 200 )


#GET - get all posts created by a specific author

@app.route("/api/v1.0/users/<string:user_id>/posts", methods=["GET"])
def get_posts_by_user(user_id):
    try:
        user_obj_id = ObjectId(user_id)
    except InvalidId:
        return make_response( jsonify( {"ERROR" : "Invalid User ID Format"} ), 400 )
    
    user = users_collection.find_one({"_id": user_obj_id})

    if not user:
        return make_response( jsonify( {"ERROR" : "User Not Found"} ), 404 )
    
    cursor = posts_collection.find({"author_id": user_obj_id})

    post_list = []
    for post in cursor:
        post["_id"] = str(post["_id"])
        post["author_id"] = str(post["author_id"])
        post_list.append(post)

    return make_response( jsonify( post_list ), 200 )

#GET - get a single post by its ID

@app.route("/api/v1.0/posts/<string:post_id>", methods=["GET"])
def show_one_post(post_id):
    try:
        obj_id = ObjectId(post_id)
    except InvalidId:
        return make_response( jsonify( {"ERROR" : "Invalid Post ID Format"} ), 400 )
    
    doc = posts_collection.find_one({"_id": obj_id}, {"_id": 0})

    if doc:
        return make_response( jsonify( doc ), 200 )
    else:
        return make_response( jsonify( {"ERROR" : "Post Not Found"} ), 404 )


#POST - create a new post

@app.route("/api/v1.0/posts", methods=["POST"])
def add_post():
    data = request.get_json()

    if 'author_id' not in data or 'text' not in data:
        return make_response( jsonify( {"ERROR" : "Missing Required Field"} ), 400 )
    
    try:
        auth_obj_id = ObjectId(data['author_id'])
        if not users_collection.find_one({"_id": auth_obj_id}):
            return make_response( jsonify( {"ERROR" : "Author Not Found"} ), 404 )
    except InvalidId:
        return make_response( jsonify( {"ERROR" : "Invalid Author ID Format"} ), 400 )

    if not data:
        return make_response( jsonify( {"ERROR" : "No JSON data provided"} ), 400 )
    
    new_post = {
        "text": data["text"],
        "author_id": auth_obj_id,
        "engagement": data.get("engagement", 0),
        "like_count": data.get("like_count", 0),
        "comment_count": data.get("comment_count", 0),
        "liked_by": [],
        "reposts_count": data.get("reposts_count", 0),
        "language": data.get("language", None),
        "tags": data.get("tags", []),
    }

    try:
        result = posts_collection.insert_one(new_post)
    except Exception as e:
        return make_response( jsonify( {"ERROR" : "Database Insertion Failed", "details": str(e)} ), 500 )
    
    new_post["_id"] = str(result.inserted_id)
    new_post["author_id"] = str(new_post["author_id"])

    return make_response( jsonify( new_post ), 201 )

#PUT - update an existing post

@app.route("/api/v1.0/posts/<string:post_id>", methods=["PUT"])
def edit_post(post_id):
    try:
        obj_id = ObjectId(post_id)
    except InvalidId:
        return make_response( jsonify( {"ERROR" : "Invalid Post ID Format"} ), 400 )
    
    data = request.get_json()
    if not data:
        return make_response( jsonify( {"ERROR" : "No JSON data provided"} ), 400 )
    
    update_data = {}
    allowed_fields = ["text", "engagement", "like_count", "comment_count", "reposts_count", "language", "tags"]

    for field in allowed_fields:
        if field in data:
            update_data[field] = data[field]

    if not update_data:
        return make_response( jsonify( {"ERROR" : "No valid fields to update"} ), 400 )
    
    try:
        result = posts_collection.update_one({"_id": obj_id}, {"$set": update_data})
    except Exception as e:
        return make_response( jsonify( {"ERROR" : "Database Update Failed", "details": str(e)} ), 500 )
    
    if result.matched_count == 0:
        return make_response( jsonify( {"ERROR" : "Post Not Found"} ), 404 )
    
    updated_doc = posts_collection.find_one({"_id": obj_id})
    updated_doc["_id"] = str(updated_doc["_id"])

    return make_response( jsonify( updated_doc ), 200 )

#DELETE - delete a post

@app.route("/api/v1.0/posts/<string:post_id>", methods=["DELETE"])
@token_required
def delete_post(current_user, post_id):
    try:
        obj_id = ObjectId(post_id)
    except InvalidId:
        return make_response( jsonify( {"ERROR" : "Invalid Post ID Format"} ), 400 )
    
    post_to_delete = posts_collection.find_one({"_id": obj_id})
    if not post_to_delete:
        return make_response( jsonify( {"ERROR" : "Post Not Found"} ), 404 )
    
    if str(post_to_delete["author_id"]) != current_user["_id"]:
        return make_response( jsonify( {"ERROR" : "You are not authorised to delete this post."} ), 403 )

    try:
        posts_collection.delete_one({"_id": obj_id})
        comments_collection.delete_many({"post_id": str(obj_id)})
    except Exception as e:
        return make_response( jsonify( {"ERROR" : "Database Deletion Failed", "details": str(e)} ), 500 )
    
    return make_response( jsonify( {"CONFIRMED" : "Post Successfully Deleted"} ), 200 )


    #COMMENTS ENDPOINTS

#GET - get all comments for a post

@app.route("/api/v1.0/posts/<string:post_id>/comments", methods=["GET"])
def get_all_comments_for_post(post_id):

    try:
        obj_id = ObjectId(post_id)
    except InvalidId:
        return make_response( jsonify( {"ERROR" : "Invalid Post ID Format"} ), 400 )
    
    post = posts_collection.find_one({"_id": obj_id})
    if not post:
        return make_response( jsonify( {"ERROR" : "Post Not Found"} ), 404 )
    
    cursor = comments_collection.find({"post_id": str(obj_id)})

    comment_list = []
    for comment in cursor:
        comment["_id"] = str(comment["_id"])
        comment["post_id"] = str(comment["post_id"])
        comment_list.append(comment)

    return make_response( jsonify( comment_list ), 200 )

#GET - get a single comment by its ID

@app.route("/api/v1.0/posts/<string:post_id>/comments/<string:comment_id>", methods=["GET"])
def get_one_comment(post_id, comment_id):

    try:
        post_obj_id = ObjectId(post_id)
    except InvalidId:
        return make_response( jsonify( {"ERROR" : "Invalid Post ID Format"} ), 400 )
    
    try:
        comment_obj_id = ObjectId(comment_id)
    except InvalidId:
        return make_response( jsonify( {"ERROR" : "Invalid Comment ID Format"} ), 400 )

    comment = comments_collection.find_one({"_id": comment_obj_id})

    if not comment:
        return make_response( jsonify( {"ERROR" : "Comment Not Found"} ), 404 )
    
    if comment["post_id"] != str(post_obj_id):
        return make_response( jsonify( {"ERROR" : "Comment not found on specified post"} ), 404 )
    
    comment["_id"] = str(comment["_id"])
    comment["post_id"] = str(comment["post_id"])

    return make_response( jsonify( comment ), 200 )

#POST - add a new comment to a post

@app.route("/api/v1.0/posts/<string:post_id>/comments", methods=["POST"])
def add_new_comment(post_id):
    try:
        obj_id = ObjectId(post_id)
    except InvalidId:
        return make_response( jsonify( {"ERROR" : "Invalid Post ID Format"} ), 400 )
    
    post = posts_collection.find_one({"_id": obj_id})
    if not post:
        return make_response( jsonify( {"ERROR" : "Post Not Found"} ), 404 )
    
    data = request.get_json()
    if not data or "text" not in data:
        return make_response( jsonify( {"ERROR" : "Missing Required Field"} ), 400 )

    new_comment = {
        "post_id": str(obj_id),
        "text": data["text"],
        "username": "guest_user",
        "created_at": datetime.datetime.now()
    }

    try:
        result = comments_collection.insert_one(new_comment)
    except Exception as e:
        return make_response( jsonify( {"ERROR" : "Database Insertion Failed", "details": str(e)} ), 500 )
    
    posts_collection.update_one({"_id": obj_id}, {"$inc": {"comment_count": 1, "engagement": 1}})

    new_comment["_id"] = str(result.inserted_id)
    new_comment["post_id"] = str(new_comment["post_id"])

    return make_response( jsonify( new_comment ), 201 )

#PUT - update an existing comment

@app.route("/api/v1.0/posts/<string:post_id>/comments/<string:comment_id>", methods=["PUT"])
def edit_comment(post_id, comment_id):
    try:
        post_obj_id = ObjectId(post_id)
    except InvalidId:
        return make_response( jsonify( {"ERROR" : "Invalid Post ID Format"} ), 400 )
    
    try:
        comment_obj_id = ObjectId(comment_id)
    except InvalidId:
        return make_response( jsonify( {"ERROR" : "Invalid Comment ID Format"} ), 400 )
    
    data = request.get_json()
    if not data or "text" not in data:
        return make_response( jsonify( {"ERROR" : "Missing Required Field"} ), 400 )
    
    comment = comments_collection.find_one({"_id": comment_obj_id})
    if not comment:
        return make_response( jsonify( {"ERROR" : "Comment Not Found"} ), 404 )
    
    if comment["post_id"] != str(post_obj_id):
        return make_response( jsonify( {"ERROR" : "Comment Not Found On Specified Post"} ), 404 )
    
    try:
        result = comments_collection.update_one({"_id": comment_obj_id}, {"$set": {"text": data["text"]}})
    except Exception as e:
        return make_response( jsonify( {"ERROR" : "Database Update Failed", "details": str(e)} ), 500 )
    
    updated_comment = comments_collection.find_one({"_id": comment_obj_id})
    updated_comment["_id"] = str(updated_comment["_id"])
    updated_comment["post_id"] = str(updated_comment["post_id"])

    return make_response( jsonify( updated_comment ), 200 )

#DELETE - delete a comment

@app.route("/api/v1.0/posts/<string:post_id>/comments/<string:comment_id>", methods=["DELETE"])
def delete_comment(post_id, comment_id):
    try:
        post_obj_id = ObjectId(post_id)
    except InvalidId:
        return make_response( jsonify( {"ERROR" : "Invalid Post ID Format"} ), 400 )
    
    try:
        comment_obj_id = ObjectId(comment_id)
    except InvalidId:
        return make_response( jsonify( {"ERROR" : "Invalid Comment ID Format"} ), 400 )
    
    try:
        result = comments_collection.delete_one({"_id": comment_obj_id, "post_id": str(post_obj_id)})
    except Exception as e:
        return make_response( jsonify( {"ERROR" : "Database Deletion Failed", "details": str(e)} ), 500 )
    
    if result.deleted_count == 0:
        return make_response( jsonify( {"ERROR" : "Comment Not Found On Specified Post"} ), 404 )

    posts_collection.update_one({"_id": post_obj_id}, {"$inc": {"comment_count": -1, "engagement": -1}})

    return make_response( jsonify( {"CONFIRMED" : "Comment Successfully Deleted"} ), 200 )


    #LIKES ENDPOINTS

#POST - like a post

@app.route("/api/v1.0/posts/<string:post_id>/like", methods=["POST"])
def like_post(post_id):
    try:
        obj_id = ObjectId(post_id)
    except InvalidId:
        return make_response( jsonify( {"ERROR" : "Invalid Post ID Format"} ), 400 )
    
    data = request.get_json()
    if not data or 'user_id' not in data:
        return make_response( jsonify( {"ERROR" : "Missing 'user_id' in JSON body"} ), 400 )
    
    user_id = data['user_id']

    try:
        result = posts_collection.update_one(
            {"_id": obj_id,},
            {"$inc": {"like_count": 1, "engagement": 1}, "$addToSet": {"liked_by": user_id}}
        )
    except Exception as e:
        return make_response( jsonify( {"ERROR" : "Database Update Failed", "details": str(e)} ), 500 )
    
    if result.matched_count == 0:
        return make_response( jsonify( {"ERROR" : "Post Not Found"} ), 400 )
    
    updated_post = posts_collection.find_one({"_id": obj_id})
    updated_post["_id"] = str(updated_post["_id"])

    return make_response( jsonify( updated_post ), 200 )

#DELETE - unlike a post

@app.route("/api/v1.0/posts/<string:post_id>/unlike", methods=["DELETE"])
def unlike_post(post_id):
    try:
        obj_id = ObjectId(post_id)
    except InvalidId:
        return make_response( jsonify( {"ERROR" : "Invalid Post ID Format"} ), 400 )
    
    data = request.get_json()
    if not data or 'user_id' not in data:
        return make_response( jsonify( {"ERROR" : "Missing 'user_id' in JSON body"} ), 400 )
    
    user_id = data['user_id']

    try:
        result = posts_collection.update_one(
            {"_id": obj_id, "liked_by": user_id},
            {"$inc": {"like_count": -1, "engagement": -1}, "$pull": {"liked_by": user_id}}
        )
    except Exception as e:
        return make_response( jsonify( {"ERROR" : "Database Update Failed", "details": str(e)} ), 500 )
    
    if result.modified_count == 0:
        return make_response( jsonify( {"ERROR" : "Post Not Found or User Not Liked Post"} ), 400 )

    return make_response( jsonify( {"CONFIRMED": "Post Unliked Successfully"} ), 200 )

#GET - get all likes (user ID's who liked a post)

@app.route("/api/v1.0/posts/<string:post_id>/likes", methods=["GET"])
def get_all_likes(post_id):
    try:
        obj_id = ObjectId(post_id)
    except InvalidId:
        return make_response( jsonify( {"ERROR" : "Invalid Post ID Format"} ), 400 )
    
    post = posts_collection.find_one(
        {"_id": obj_id},
        {"liked_by": 1, "_id": 0})
    
    if not post:
        return make_response( jsonify( {"ERROR" : "Post Not Found"} ), 404 )
    
    liked_by = post.get("liked_by", [])

    return make_response( jsonify( {"liked_by": liked_by} ), 200 )


    #USER ENDPOINTS
#POST - sign up a new user

@app.route("/api/v1.0/users", methods=["POST"])
def create_user():
    data = request.get_json()
    if not data or 'username' not in data or 'email' not in data or 'password' not in data:
        return make_response( jsonify( {"ERROR" : "Missing Data"} ), 400 )
    
    existing_user = users_collection.find_one({"username": data['username']})
    if existing_user:
        return make_response( jsonify( {"ERROR" : "Username Already Exists"} ), 400 )
    
    hashed_password = generate_password_hash(data["password"])

    new_user = {
        "username": data["username"],
        "email": data["email"],
        "password_hash": hashed_password,
        "created_at": datetime.datetime.now()
    }

    try:
        result = users_collection.insert_one(new_user)
    except Exception as e:
        return make_response( jsonify( {"ERROR" : "Database Insertion Failed", "details": str(e)} ), 500 )
    
    response_user = {
        "_id": str(result.inserted_id),
        "username": new_user["username"],
        "email": new_user["email"],
        "created_at": new_user["created_at"]
    }

    return make_response( jsonify( response_user ), 201 )

#GET - get all users

@app.route("/api/v1.0/users", methods=["GET"])
def get_all_users():
    try:
        cursor = users_collection.find({}, {"password_hash": 0})
    except Exception as e:
        return make_response( jsonify( {"ERROR" : "Database Query Failed", "details": str(e)} ), 500 )
    
    user_list = []
    for user in cursor:
        user["_id"] = str(user["_id"])
        user_list.append(user)

    return make_response( jsonify( user_list ), 200 )

#GET - get single user

@app.route("/api/v1.0/users/<string:user_id>", methods=["GET"])
def get_one_user(user_id):
    try:
        obj_id = ObjectId(user_id)
    except InvalidId:
        return make_response( jsonify( {"ERROR" : "Invalid User ID Format"} ), 400 )
    
    user = users_collection.find_one(
        {"_id": obj_id},
        {"password_hash": 0}
    )

    if not user:
        return make_response( jsonify( {"ERROR" : "User Not Found"} ), 404 )
    
    user["_id"] = str(user["_id"])

    return make_response( jsonify( user ), 200 )

#PUT - update user info

@app.route("/api/v1.0/users/<string:user_id>", methods=["PUT"])
def update_user(user_id):
    try:
        obj_id = ObjectId(user_id)
    except InvalidId:
        return make_response( jsonify( {"ERROR" : "Invalid User ID Format"} ), 400 )
    
    data = request.get_json()
    if not data:
        return make_response( jsonify( {"ERROR" : "No JSON data provided"} ), 400 )
    
    update_data = {}
    if 'email' in data:
        update_data['email'] = data['email']
    if 'password' in data:
        update_data['password_hash'] = generate_password_hash(data['password'])

    if not update_data:
        return make_response( jsonify( {"ERROR" : "No valid fields to update"} ), 400 )
    
    try:
        result = users_collection.update_one({"_id": obj_id}, {"$set": update_data})
    except Exception as e:
        return make_response( jsonify( {"ERROR" : "Database Update Failed", "details": str(e)} ), 500 )
    
    if result.matched_count == 0:
        return make_response( jsonify( {"ERROR" : "User Not Found"} ), 404 )
    
    updated_user = users_collection.find_one({"_id": obj_id}, {"password_hash": 0})
    updated_user["_id"] = str(updated_user["_id"])

    return make_response( jsonify( updated_user ), 200 )

#DELETE - delete a user

@app.route("/api/v1.0/users/<string:user_id>", methods=["DELETE"])
def delete_user(user_id):
    try:
        obj_id = ObjectId(user_id)
    except InvalidId:
        return make_response( jsonify( {"ERROR" : "Invalid User ID Format"} ), 400 )
    
    try:
        result = users_collection.delete_one({"_id": obj_id})
    except Exception as e:
        return make_response( jsonify( {"ERROR" : "Database Deletion Failed", "details": str(e)} ), 500 )
    
    if result.deleted_count == 0:
        return make_response( jsonify( {"ERROR" : "User Not Found"} ), 404 )

    return make_response( jsonify( {"CONFIRMED" : "User Successfully Deleted"} ), 200 )

#User Login

@app.route("/api/v1.0/login", methods=["POST"])
def login_user():
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return make_response( jsonify( {"ERROR" : "Missing Username or Password"} ), 400 )
    
    user = users_collection.find_one({"username": data['username']})
    if not user:
        return make_response( jsonify( {"ERROR" : "Invalid Username or Password"} ), 401 )
    
    if check_password_hash(user['password_hash'], data['password']):
        token = jwt.encode(
            {
                'user_id': str(user['_id']),
                'exp': datetime.datetime.now() + datetime.timedelta(hours=24)
            },
            app.config['SECRET_KEY'],
            algorithm='HS256'
        )
        return make_response( jsonify( {"token": token} ), 200 )
    else:
        return make_response( jsonify( {"ERROR": "Invalid Username or Password"} ), 401 )

if __name__ == "__main__":
    app.run(debug=True, port=4999)
