"""Fieldnotes API — small Flask + MongoDB backend for the editorial UI.

The static front end works without this API for a quick visual preview. Run
this server when you want published stories to come from MongoDB.
"""
import os
import re
import subprocess
import sys
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
from flask import Flask, jsonify, request, send_from_directory, Response, session
from flask_cors import CORS
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from bson import ObjectId
from gridfs import GridFS
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__, static_folder=".", static_url_path="")
UPLOAD_DIR = Path(__file__).resolve().parent / "upload"
STATIC_SITE_DIR = Path(__file__).resolve().parent / "github-pages"
UPLOAD_DIR.mkdir(exist_ok=True)
app.secret_key = os.getenv("SECRET_KEY", "fieldnotes-local-development-key")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
CORS(app, supports_credentials=True)

@app.errorhandler(PyMongoError)
def mongo_error(_error):
    return jsonify({"error": "Database unavailable. Start MongoDB or check MONGO_URI."}), 503

client = MongoClient(
    os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017"),
    serverSelectionTimeoutMS=1500,
    connectTimeoutMS=1500,
)
db = client[os.getenv("MONGO_DB", "fieldnotes")]
posts = db.posts
images = GridFS(db)
users = db.users

def make_slug(value):
    return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", str(value).lower().strip())) or "story"

@app.get("/")
def home():
    return send_from_directory(".", "index.html")

@app.get("/post/<post_key>")
def post_page(post_key):
    return send_from_directory(".", "index.html")

@app.get("/profile")
def profile_page():
    return send_from_directory(".", "index.html")

@app.get("/studio")
def studio_page():
    return send_from_directory(".", "index.html")

@app.get("/static-preview/")
def static_preview():
    if not (STATIC_SITE_DIR / "index.html").exists():
        return "Run the static export from Studio first.", 404
    return send_from_directory(STATIC_SITE_DIR, "index.html")

@app.get("/static-preview/<path:filename>")
def static_preview_file(filename):
    return send_from_directory(STATIC_SITE_DIR, filename)

@app.post("/api/static-export")
def static_export():
    blocked = require_publisher()
    if blocked:
        return blocked
    exporter = Path(__file__).resolve().parent / "export_static.py"
    try:
        result = subprocess.run(
            [sys.executable, str(exporter)],
            cwd=exporter.parent,
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Static export timed out while reading MongoDB."}), 504
    if result.returncode:
        return jsonify({"error": result.stderr.strip() or result.stdout.strip() or "Static export failed."}), 500
    return jsonify({"ok": True, "message": result.stdout.strip(), "url": "/static-preview/"})

@app.get("/upload/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)

@app.get("/api/auth/me")
def auth_me():
    return jsonify({"user": session.get("user")})

@app.post("/api/auth/register")
def register():
    data = request.get_json(force=True)
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    name = str(data.get("name", "")).strip() or email.split("@")[0]
    role = data.get("role", "reader")
    if role not in ("reader", "publisher") or len(password) < 6 or "@" not in email:
        return jsonify({"error": "use a valid email, a password of 6+ characters, and a valid role"}), 400
    if users.find_one({"email": email}):
        return jsonify({"error": "an account with this email already exists"}), 409
    user = {"name": name, "email": email, "role": role, "password": generate_password_hash(password), "created_at": datetime.now(timezone.utc)}
    result = users.insert_one(user)
    session["user"] = {"id": str(result.inserted_id), "name": name, "email": email, "role": role}
    return jsonify({"user": session["user"]}), 201

@app.post("/api/auth/login")
def login():
    data = request.get_json(force=True)
    email = str(data.get("email", "")).strip().lower()
    user = users.find_one({"email": email})
    if not user or not check_password_hash(user["password"], str(data.get("password", ""))):
        return jsonify({"error": "email or password is incorrect"}), 401
    requested_role = data.get("role", "reader")
    if requested_role == "publisher" and user.get("role") != "publisher":
        return jsonify({"error": "this account is not a publisher account"}), 403
    session["user"] = {"id": str(user["_id"]), "name": user["name"], "email": user["email"], "role": user["role"]}
    return jsonify({"user": session["user"]})

@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})

def require_publisher():
    user = session.get("user")
    if not user:
        return jsonify({"error": "publisher login required"}), 401
    if user.get("role") != "publisher":
        return jsonify({"error": "publisher permissions required"}), 403
    return None

@app.get("/api/posts")
def list_posts():
    query = {"status": "published"}
    if request.args.get("mine") == "1":
        user = session.get("user")
        if not user or user.get("role") != "publisher":
            return jsonify({"error": "publisher login required"}), 401
        query.pop("status", None)
        query["$or"] = [{"owner_email": user["email"]}, {"author": user["name"]}]
        if request.args.get("status") in ("published", "draft"):
            query["status"] = request.args["status"]
    docs = list(posts.find(query).sort("published_at", -1))
    for doc in docs:
        doc["_id"] = str(doc["_id"])
    return jsonify(docs)

@app.get("/api/posts/<post_id>")
def get_post(post_id):
    try:
        identifier = {"_id": ObjectId(post_id)} if ObjectId.is_valid(post_id) else {"slug": post_id}
        doc = posts.find_one({**identifier, "status": "published"})
    except Exception:
        doc = None
    if not doc:
        return jsonify({"error": "published post not found"}), 404
    doc["_id"] = str(doc["_id"])
    return jsonify(doc)

@app.post("/api/posts")
def create_post():
    blocked = require_publisher()
    if blocked:
        return blocked
    data = request.get_json(force=True)
    required = ("title", "overview", "category")
    if any(not data.get(field) for field in required):
        return jsonify({"error": "title, overview and category are required"}), 400
    user = session["user"]
    status = data.get("status", "published")
    if status not in ("published", "draft"):
        return jsonify({"error": "status must be published or draft"}), 400
    created_at = datetime.now(timezone.utc)
    data.update(slug=make_slug(data.get("slug") or data["title"]), status=status, created_at=created_at, published_at=created_at if status == "published" else None, author=user["name"], owner_email=user["email"])
    result = posts.insert_one(data)
    return jsonify({"id": str(result.inserted_id), **data}), 201

@app.put("/api/posts/<post_id>")
def update_post(post_id):
    blocked = require_publisher()
    if blocked:
        return blocked
    data = request.get_json(force=True)
    data.pop("_id", None)
    data["slug"] = make_slug(data.get("slug") or data.get("title", "story"))
    data["updated_at"] = datetime.now(timezone.utc)
    if data.get("status") not in ("published", "draft"):
        return jsonify({"error": "status must be published or draft"}), 400
    if data["status"] == "published" and not data.get("published_at"):
        data["published_at"] = datetime.now(timezone.utc)
    user = session["user"]
    result = posts.update_one({"_id": ObjectId(post_id), "$or": [{"owner_email": user["email"]}, {"author": user["name"]}]}, {"$set": data})
    if not result.matched_count:
        return jsonify({"error": "post not found"}), 404
    return jsonify({"id": post_id, **data})

@app.get("/api/stats")
def stats():
    blocked = require_publisher()
    if blocked:
        return blocked
    user = session["user"]
    owner_query = {"$or": [{"owner_email": user["email"]}, {"author": user["name"]}]}
    docs = list(posts.find(owner_query, {"slug": 1, "title": 1, "status": 1}))
    unique = set()
    published = drafts = 0
    for doc in docs:
        status = doc.get("status", "published")
        key = (make_slug(doc.get("slug") or doc.get("title", "untitled")), status)
        if key in unique:
            continue
        unique.add(key)
        if status == "draft":
            drafts += 1
        else:
            published += 1
    return jsonify({"published": published, "drafts": drafts, "readers": users.count_documents({"role": "reader"})})

@app.delete("/api/posts/<post_id>")
def delete_post(post_id):
    blocked = require_publisher()
    if blocked:
        return blocked
    user = session["user"]
    result = posts.delete_one({"_id": ObjectId(post_id), "$or": [{"owner_email": user["email"]}, {"author": user["name"]}]})
    if not result.deleted_count:
        return jsonify({"error": "post not found"}), 404
    return jsonify({"ok": True, "id": post_id})

@app.post("/api/uploads")
def upload_image():
    blocked = require_publisher()
    if blocked:
        return blocked
    image = request.files.get("image")
    if not image or not image.filename:
        return jsonify({"error": "choose an image file"}), 400
    if not image.mimetype.startswith("image/"):
        return jsonify({"error": "only image files are supported"}), 415
    original_name = secure_filename(image.filename) or "image"
    stored_name = f"{uuid4().hex[:12]}-{original_name}"
    payload = image.read()
    (UPLOAD_DIR / stored_name).write_bytes(payload)
    try:
        file_id = images.put(payload, filename=original_name, contentType=image.mimetype)
        gridfs_id = str(file_id)
    except PyMongoError:
        gridfs_id = None
    return jsonify({"id": gridfs_id, "url": f"/upload/{stored_name}", "filename": original_name, "storage": "mongodb+local" if gridfs_id else "local"}), 201

@app.get("/api/images/<file_id>")
def get_image(file_id):
    try:
        stored = images.get(ObjectId(file_id))
    except Exception:
        return jsonify({"error": "image not found"}), 404
    return Response(stored.read(), mimetype=stored.content_type)

@app.get("/api/health")
def health():
    try:
        client.admin.command("ping")
        return jsonify({"status": "ok", "database": db.name})
    except Exception:
        return jsonify({"status": "degraded", "database": db.name, "error": "MongoDB is not running"}), 503

if __name__ == "__main__":
    app.run(
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
        use_reloader=False,
        port=int(os.getenv("PORT", 5000)),
    )
