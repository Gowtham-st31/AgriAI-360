# app.py
# app.py
import re
import os
import requests
import io
import json
import smtplib
import random
from email.mime.text import MIMEText
import time
import tensorflow as tf
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory, session, redirect, make_response, has_request_context
from flask_cors import CORS
from functools import wraps  # 🔥 FIXED
import socket                # 🔥 moved here
import inspect
import hashlib
from bs4 import BeautifulSoup
from apscheduler.schedulers.background import BackgroundScheduler

# ============================
# 🔥 MODEL DOWNLOAD + LOAD
# ============================
MODEL_URL = "https://drive.google.com/uc?export=download&id=1nn-JVOCSpMqYSNE6Vy0TQ9nq251M94BI"
MODEL_PATH = "model.keras"

if not os.path.exists(MODEL_PATH):
    print("\n📥 Downloading model from Google Drive...\n")
    r = requests.get(MODEL_URL, allow_redirects=True)
    with open(MODEL_PATH, "wb") as f:
        f.write(r.content)
    print("\n✅ Model downloaded successfully.\n")

model = tf.keras.models.load_model(MODEL_PATH)
print("\n🚀 Model loaded successfully & ready!\n")


# Load .env if available (python-dotenv optional)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


# Optional MongoDB support (pymongo)
try:
    from pymongo import MongoClient
except Exception:
    MongoClient = None

try:
    import tensorflow as tf
except Exception:
    tf = None
    print("Warning: tensorflow not installed; model features disabled.")
try:
    import numpy as np
except Exception:
    np = None
    print("Warning: numpy not installed; prediction features disabled.")
try:
    from PIL import Image
except Exception:
    Image = None
    print("Warning: PIL (Pillow) not installed; image preprocessing disabled.")


# -----------------------------------------------------
#   FLASK CONFIG
# -----------------------------------------------------
app = Flask(__name__, static_folder="static")
# Allow cross-origin requests with credentials (session cookies)
CORS(app, supports_credentials=True)
# Secret can be provided via FLASK_SECRET in the environment or .env; fallback preserved
app.secret_key = os.environ.get("FLASK_SECRET", "my_admin_secret_key_123")
USERS_FILE = "data/users.json"

# ------------------
# MongoDB (Atlas) init
# ------------------
mongo_client = None
mongo_db = None
MONGODB_URI = os.environ.get('MONGODB_URI')
if MONGODB_URI and MongoClient is not None:
    try:
        mongo_client = MongoClient(MONGODB_URI)
        # Determine DB name: prefer explicit env var, else driver default, else 'agri'
        mongo_dbname = os.environ.get('MONGODB_DB')
        if not mongo_dbname:
            try:
                mongo_dbname = mongo_client.get_default_database().name
            except Exception:
                mongo_dbname = None
        if not mongo_dbname:
            mongo_dbname = 'agri'
        mongo_db = mongo_client[mongo_dbname]
        print(f"MongoDB connected, using database: {mongo_db.name}")
    except Exception as e:
        print('MongoDB init failed:', e)
        mongo_client = None
        mongo_db = None
else:
    if MONGODB_URI and MongoClient is None:
        print('MONGODB_URI provided but pymongo not installed; install pymongo in requirements')

# -----------------------------------------------------
#   DISEASE CLASS LIST (38 CLASSES)
# -----------------------------------------------------
DISEASE_CLASSES = [
    'Apple___Apple_scab', 'Apple___Black_rot', 'Apple___Cedar_apple_rust',
    'Apple___healthy', 'Blueberry___healthy', 'Cherry_(including_sour)___Powdery_mildew',
    'Cherry_(including_sour)___healthy', 'Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot',
    'Corn_(maize)___Common_rust_', 'Corn_(maize)___Northern_Leaf_Blight', 'Corn_(maize)___healthy',
    'Grape___Black_rot', 'Grape___Esca_(Black_Measles)', 'Grape___Leaf_blight_(Isariopsis_Leaf_Spot)',
    'Grape___healthy', 'Orange___Haunglongbing_(Citrus_greening)', 'Peach___Bacterial_spot',
    'Peach___healthy', 'Pepper,_bell___Bacterial_spot', 'Pepper,_bell___healthy',
    'Potato___Early_blight', 'Potato___Late_blight', 'Potato___healthy',
    'Raspberry___healthy', 'Soybean___healthy', 'Squash___Powdery_mildew',
    'Strawberry___Leaf_scorch', 'Strawberry___healthy', 'Tomato___Bacterial_spot',
    'Tomato___Early_blight', 'Tomato___Late_blight', 'Tomato___Leaf_Mold',
    'Tomato___Septoria_leaf_spot', 'Tomato___Spider_mites Two-spotted_spider_mite',
    'Tomato___Target_Spot', 'Tomato___Tomato_Yellow_Leaf_Curl_Virus',
    'Tomato___Tomato_mosaic_virus', 'Tomato___healthy'
]

# -----------------------------------------------------
#   DISEASE REMEDIES (38 keys + helpful variants)
#   Keys are normalized: lowercase + non-alphanum removed
# -----------------------------------------------------
DISEASE_REMEDIES = {
    # Apple group
    "applescab": {
        "description": "Fungal disease producing dark scabby lesions on apple leaves and fruit.",
        "remedies": [
            "Spray with captan or sulfur fungicide per label instructions.",
            "Collect and destroy fallen infected leaves and fruit.",
            "Prune to increase airflow and reduce humidity."
        ],
        "prevention": [
            "Plant resistant cultivars where available.",
            "Avoid overhead irrigation; irrigate at base.",
            "Maintain orchard sanitation."
        ],
        "daily_care": [
            "Inspect trees weekly for early lesions.",
            "Remove fresh infected debris promptly."
        ]
    },
    "blackrot": {
        "description": "Fungal black rot causing leaf spots and fruit decay.",
        "remedies": [
            "Remove and destroy infected fruit and cankers.",
            "Apply copper fungicide or recommended product."
        ],
        "prevention": [
            "Avoid overcrowding, remove inoculum (mummies).",
            "Use disease-free planting material."
        ],
        "daily_care": ["Inspect fruits regularly; remove infected parts."]
    },
    "cedarapplerust": {
        "description": "Rust disease transferred from junipers causing orange spots on leaves.",
        "remedies": [
            "Remove nearby juniper hosts if feasible.",
            "Apply a registered fungicide during high-risk periods."
        ],
        "prevention": ["Plant resistant apple varieties", "Prune for good air flow"],
        "daily_care": ["Monitor for orange lesions during season."]
    },
    "applehealthy": {
        "description": "Apple leaf and plant appear healthy.",
        "remedies": ["No treatment required."],
        "prevention": ["Balanced nutrition, good drainage."],
        "daily_care": ["Routine inspection and proper watering."]
    },

    # Blueberry
    "blueberryhealthy": {
        "description": "Blueberry plant healthy.",
        "remedies": ["No action required."],
        "prevention": ["Maintain acidic soil (pH 4.5–5.5) and mulch."],
        "daily_care": ["Keep soil moisture consistent."]
    },

    # Cherry (including sour)
    "powderymildew": {
        "description": "Powdery mildew: white powdery fungal growth on leaves and shoots.",
        "remedies": ["Spray neem oil or sulfur fungicide; remove heavily infected tissue."],
        "prevention": ["Improve airflow, avoid overhead irrigation."],
        "daily_care": ["Remove infected leaves and reduce humidity."]
    },
    "healthy": {
        "description": "Plant appears healthy; no disease detected.",
        "remedies": ["No treatment required."],
        "prevention": ["Routine good practices (watering, nutrition, sanitation)."],
        "daily_care": ["Inspect regularly for early signs of issues."]
    },

    # Corn (maize)
    "cercosporaleafspotgrayleafspot": {
        "description": "Cercospora / Gray leaf spot: elongated brown-gray lesions reducing photosynthesis.",
        "remedies": [
            "Use fungicides like mancozeb or chlorothalonil when threshold reached.",
            "Remove infected crop residue to reduce inoculum."
        ],
        "prevention": [
            "Rotate crops.",
            "Plant resistant hybrids and avoid continuous maize."
        ],
        "daily_care": ["Inspect fields frequently and maintain spacing for airflow."]
    },
    "commonrust": {
        "description": "Common rust: orange-brown pustules on leaves caused by fungus.",
        "remedies": ["Apply appropriate fungicide if severe."],
        "prevention": ["Grow resistant hybrids."],
        "daily_care": ["Monitor and remove volunteers and weeds."]
    },
    "northernleafblight": {
        "description": "Northern leaf blight: long cigar-shaped lesions on maize leaves.",
        "remedies": ["Use azoxystrobin or labelled fungicides when needed."],
        "prevention": ["Use certified seed and rotate crops."],
        "daily_care": ["Regular inspection during humid conditions."]
    },
    "cornmaizehealthy": {
        "description": "Maize plant healthy.",
        "remedies": ["No action required."],
        "prevention": ["Balanced fertilizer and good drainage."],
        "daily_care": ["Routine field checks."]
    },

    # Grape
    "blackrot": {
        "description": "Black rot in grape causing black lesions and rot of clusters.",
        "remedies": ["Apply copper fungicide; remove infected clusters and leaves."],
        "prevention": ["Sanitation and increased airflow in canopy."],
        "daily_care": ["Inspect clusters frequently; prune to improve ventilation."]
    },
    "escablackmeasles": {
        "description": "Esca (Black measles): trunk and wood disease reducing vigor and causing leaf symptoms.",
        "remedies": ["Prune and remove affected wood; apply recommended systemic products if available."],
        "prevention": ["Use healthy rootstock and avoid over-irrigation."],
        "daily_care": ["Monitor trunk and canopy health."]
    },
    "leafblightisariopsisleafspot": {
        "description": "Leaf blight / Isariopsis leaf spot causing defoliation.",
        "remedies": ["Spray recommended fungicides and remove infected leaves."],
        "prevention": ["Improve canopy ventilation and avoid dense plantings."],
        "daily_care": ["Inspect leaves regularly and remove diseased tissue."]
    },
    "grapehealthy": {
        "description": "Grape vine healthy.",
        "remedies": ["No action required."],
        "prevention": ["Proper irrigation and pruning."],
        "daily_care": ["Routine inspection."]
    },

    # Orange / Citrus
    "haunglongbingcitrusgreening": {
        "description": "Huanglongbing (citrus greening): bacterial disease spread by psyllids causing yellow shoots and poor fruit.",
        "remedies": ["Remove heavily infected trees; control psyllid vector with insecticide."],
        "prevention": ["Use certified disease-free plant material and manage vectors."],
        "daily_care": ["Inspect for psyllids daily; apply nutrition supplements."]
    },

    # Peach
    "bacterialspot": {
        "description": "Bacterial spot: water-soaked lesions on leaves and fruits.",
        "remedies": ["Spray copper-based bactericide; remove infected tissue."],
        "prevention": ["Avoid wetting foliage; use clean planting material."],
        "daily_care": ["Monitor especially during wet weather."]
    },
    "peachhealthy": {
        "description": "Peach plant healthy.",
        "remedies": ["No action required."],
        "prevention": ["Balanced nutrition and pruning."],
        "daily_care": ["Routine inspection."]
    },

    # Pepper (bell)
    "pepperbellbacterialspot": {
        "description": "Bacterial spot on bell pepper leaves and fruit.",
        "remedies": ["Apply copper sprays and remove infected leaves."],
        "prevention": ["Avoid overhead irrigation and use disease-free transplants."],
        "daily_care": ["Inspect plants regularly."]
    },
    "pepperbellhealthy": {
        "description": "Bell pepper plant healthy.",
        "remedies": ["No action required."],
        "prevention": ["Balanced feed and soil moisture."],
        "daily_care": ["Inspect weekly."]
    },

    # Potato
    "potatoearlyblight": {
        "description": "Early blight: concentric rings on leaves due to fungal infection.",
        "remedies": ["Use copper or recommended fungicide; remove infected leaves."],
        "prevention": ["Rotate crops and avoid overhead watering."],
        "daily_care": ["Inspect lower leaves daily during season."]
    },
    "potatolateblight": {
        "description": "Late blight: rapid leaf collapse and tuber rot; can be devastating.",
        "remedies": ["Apply systemic fungicides like metalaxyl; destroy badly infected plants."],
        "prevention": ["Use resistant varieties and avoid wet foliage."],
        "daily_care": ["Monitor in cool, wet weather and act early."]
    },
    "potatohealthy": {
        "description": "Potato plant healthy.",
        "remedies": ["No action required."],
        "prevention": ["Good drainage and fertility management."],
        "daily_care": ["Routine monitoring for pests/disease."]
    },

    # Strawberry
    "leafscorch": {
        "description": "Leaf scorch causes browning and necrosis of leaf tissue.",
        "remedies": ["Remove scorched tissues; apply fungicide if fungal cause suspected."],
        "prevention": ["Avoid overcrowding; improve drainage."],
        "daily_care": ["Water at base and inspect frequently."]
    },
    "strawberryhealthy": {
        "description": "Strawberry plant healthy.",
        "remedies": ["No action required."],
        "prevention": ["Maintain soil moisture and fertility."],
        "daily_care": ["Fertilize lightly and inspect weekly."]
    },

    # Squash
    "powderymildew": {
        "description": "Powdery mildew: white powder on upper leaf surfaces.",
        "remedies": ["Spray neem oil or potassium bicarbonate; remove infected leaves."],
        "prevention": ["Keep spacing to allow airflow; avoid humid microclimates."],
        "daily_care": ["Inspect underside of leaves regularly."]
    },

    # Tomato group
    "tomatobacterialspot": {
        "description": "Bacterial spot on tomato leaves and fruit.",
        "remedies": ["Use copper sprays and remove infected foliage."],
        "prevention": ["Avoid overhead irrigation and use disease-free seed."],
        "daily_care": ["Inspect plants daily for new lesions."]
    },
    "tomatoearlyblight": {
        "description": "Early blight: brown spots with concentric rings on tomato leaves.",
        "remedies": ["Apply mancozeb or copper-based sprays as labelled."],
        "prevention": ["Rotate crops and mulch to reduce soil splash."],
        "daily_care": ["Remove lower leaves and check frequently."]
    },
    "tomatolateblight": {
        "description": "Late blight: quickly spreading blight causing foliar and fruit rot.",
        "remedies": ["Use systemic fungicides and remove infected plants."],
        "prevention": ["Avoid overhead watering; use tolerant varieties if available."],
        "daily_care": ["Monitor plants daily in wet conditions."]
    },
    "tomatoleafmold": {
        "description": "Leaf mold: fuzzy/gray mold beneath leaves causing yellowing above.",
        "remedies": ["Improve ventilation; apply fungicides if necessary."],
        "prevention": ["Avoid overcrowding and wet foliage."],
        "daily_care": ["Inspect undersides of leaves regularly."]
    },
    "septorialeafspot": {
        "description": "Septoria leaf spot: small tan to dark spots on lower leaves.",
        "remedies": ["Remove lower leaves; apply fungicides."],
        "prevention": ["Water soil only, not foliage."],
        "daily_care": ["Inspect closely and remove affected leaves."]
    },
    "spidermitestwospottedspidermite": {
        "description": "Two-spotted spider mites cause stippling, yellowing and webbing.",
        "remedies": ["Spray miticide or neem oil; increase humidity to reduce mites."],
        "prevention": ["Avoid drought stress and keep plants healthy."],
        "daily_care": ["Check lower leaf surfaces daily."]
    },
    "targetspot": {
        "description": "Target spot: circular lesions on foliage and fruit.",
        "remedies": ["Use chlorothalonil or recommended fungicides; remove affected tissue."],
        "prevention": ["Proper spacing and sanitation."],
        "daily_care": ["Inspect canopy daily for new lesions."]
    },
    "tomatoyellowleafcurlvirus": {
        "description": "Tomato yellow leaf curl virus (TYLCV): whitefly-transmitted virus causing leaf curl and stunting.",
        "remedies": ["Remove infected plants; control whitefly vector."],
        "prevention": ["Use insect nets and resistant varieties where available."],
        "daily_care": ["Monitor for whiteflies and use yellow sticky traps."]
    },
    "tomatomosaicvirus": {
        "description": "Tomato mosaic virus: mosaic/chlorotic patterns on leaves, reduced vigor.",
        "remedies": ["Remove infected plants and disinfect tools."],
        "prevention": ["Use virus-free seed and resistant varieties."],
        "daily_care": ["Inspect weekly and disinfect tools after use."]
    },
    "tomatohealthy": {
        "description": "Tomato plant healthy.",
        "remedies": ["No treatment required."],
        "prevention": ["Balanced watering and fertilization."],
        "daily_care": ["Routine inspection for pests/disease."]
    }
}

# default fallback
DEFAULT_INFO = {
    "description": "No remedy information found.",
    "remedies": ["No remedies available."],
    "prevention": ["No prevention steps available."],
    "daily_care": []
}

# -----------------------------------------------------
#   MODEL LOADING
# -----------------------------------------------------
MODEL_PATH = "model.keras"
model = None
if tf is not None:
    try:
        model = tf.keras.models.load_model(MODEL_PATH)
        print("Model loaded from", MODEL_PATH)
    except Exception as e:
        print("Warning: failed to load model:", e)
        model = None

# -----------------------------------------------------
#   helper utilities
# -----------------------------------------------------
def load_users():
    # If Mongo is available, read users from the users collection
    try:
        if mongo_db is not None:
            coll = mongo_db.get_collection('users')
            docs = list(coll.find({}, {'_id': 0}))
            return {'users': docs}
    except Exception:
        pass

    if not os.path.exists(USERS_FILE):
        return {"users": []}
    return json.load(open(USERS_FILE, "r"))

def save_users(data):
    # If Mongo is available, replace the users collection contents
    try:
        if mongo_db is not None:
            coll = mongo_db.get_collection('users')
            coll.delete_many({})
            if data.get('users'):
                # strip any _id if present
                docs = [{k: v for k, v in u.items() if k != '_id'} for u in data.get('users')]
                coll.insert_many(docs)
            return
    except Exception as e:
        print('save_users -> mongo error:', e)

    json.dump(data, open(USERS_FILE, "w"), indent=2)

def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()

def find_user(email: str):
    # Prefer Mongo lookup when available
    try:
        if mongo_db is not None:
            coll = mongo_db.get_collection('users')
            doc = coll.find_one({'email': email}, {'_id': 0})
            if doc:
                return doc
    except Exception as e:
        print('find_user -> mongo error:', e)

    users = load_users().get("users", [])
    for u in users:
        if u.get("email") == email:
            return u
    return None


# -------------------------
# Orders / persistence helpers
# -------------------------
def get_orders_collection():
    return mongo_db.get_collection('orders') if mongo_db is not None else None

def read_orders():
    # Return list of orders from Mongo or fallback file
    try:
        coll = get_orders_collection()
        if coll is not None:
            docs = list(coll.find({}, {'_id': 0}))
            return docs
    except Exception as e:
        print('read_orders -> mongo error:', e)

    orders_file = os.path.join(os.path.dirname(__file__), 'data', 'orders.json')
    try:
        with open(orders_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def read_today_deals():
    """Read admin-marked today's deals IDs from data/today_deals.json (list of ids).
       Returns list of ints.
    """
    fn = os.path.join(os.path.dirname(__file__), 'data', 'today_deals.json')
    try:
        with open(fn, 'r', encoding='utf-8') as f:
            arr = json.load(f)
            if isinstance(arr, list):
                return [int(x) for x in arr]
    except Exception:
        return []
    return []


def save_today_deals(id_list):
    fn = os.path.join(os.path.dirname(__file__), 'data', 'today_deals.json')
    try:
        with open(fn, 'w', encoding='utf-8') as f:
            json.dump([int(x) for x in id_list], f, indent=2)
        return True
    except Exception as e:
        print('save_today_deals error:', e)
        return False

def append_order(order):
    try:
        coll = get_orders_collection()
        if coll is not None:
            res = coll.insert_one(order)
            # Return the stored document without Mongo's internal _id
            try:
                stored = coll.find_one({'_id': res.inserted_id}, {'_id': 0})
                return stored
            except Exception:
                # fallback: return the original order
                return order
    except Exception as e:
        print('append_order -> mongo error:', e)

    orders_file = os.path.join(os.path.dirname(__file__), 'data', 'orders.json')
    try:
        with open(orders_file, 'r', encoding='utf-8') as f:
            orders = json.load(f)
    except Exception:
        orders = []
    orders.append(order)
    with open(orders_file, 'w', encoding='utf-8') as f:
        json.dump(orders, f, indent=2)
    return order


def adjust_product_quantity(product_name, amount):
    """Decrease product stock by `amount` (amount is numeric, positive means reduce).
    This updates Mongo `products` collection when available, else updates `data/products.json`.
    If the product record does not have a numeric quantity/stock field, the function will skip updating
    (to avoid creating incorrect negative stocks).
    Returns the updated product dict on success, or None if not updated/found.
    """
    try:
        amt = float(amount)
    except Exception:
        return None

    # Normalize lookup name
    pname = (product_name or '').strip()
    if not pname:
        return None

    # Try Mongo first
    try:
        if mongo_db is not None:
            coll = mongo_db.get_collection('products')
            # find by name case-insensitive
            doc = coll.find_one({ 'name': { '$regex': f'^{re.escape(pname)}$', '$options': 'i' } })
            if not doc:
                return None
            # pick existing numeric field to update
            for field in ('quantity', 'stock', 'qty'):
                if field in doc and isinstance(doc.get(field), (int, float)):
                    # decrement by amt
                    coll.update_one({'_id': doc.get('_id')}, {'$inc': {field: -amt}})
                    updated = coll.find_one({'_id': doc.get('_id')}, {'_id': 0})
                    return updated
            # No numeric field to update
            return None
    except Exception as e:
        print('adjust_product_quantity -> mongo error:', e)

    # Fallback: file-based products
    products_file = os.path.join(os.path.dirname(__file__), 'data', 'products.json')
    try:
        with open(products_file, 'r', encoding='utf-8') as f:
            pdata = json.load(f)
    except Exception:
        pdata = { 'products': [] }

    changed = False
    for p in pdata.get('products', []):
        name = (p.get('name') or p.get('product') or '').strip()
        if name and name.lower() == pname.lower():
            # find numeric field
            for field in ('quantity', 'stock', 'qty'):
                if field in p and isinstance(p.get(field), (int, float)):
                    p[field] = max(0, float(p.get(field)) - amt)
                    changed = True
                    break
            # if no numeric field exists, skip modification
            break

    if changed:
        # write back using centralized writer but allow force (internal action)
        try:
            write_products(pdata, force=True)
        except Exception as e:
            print('adjust_product_quantity -> write_products error:', e)
        # return the updated product
        for p in pdata.get('products', []):
            name = (p.get('name') or p.get('product') or '').strip()
            if name and name.lower() == pname.lower():
                return p

    return None

def delete_order_by_id(order_id):
    try:
        coll = get_orders_collection()
        if coll is not None:
            coll.delete_one({'id': order_id})
            return True
    except Exception as e:
        print('delete_order_by_id -> mongo error:', e)

    orders_file = os.path.join(os.path.dirname(__file__), 'data', 'orders.json')
    try:
        with open(orders_file, 'r', encoding='utf-8') as f:
            orders = json.load(f)
    except Exception:
        orders = []
    new_orders = [o for o in orders if int(o.get('id', 0)) != int(order_id)]
    with open(orders_file, 'w', encoding='utf-8') as f:
        json.dump(new_orders, f, indent=2)
    return True

def update_order_by_id(order_id, updates: dict):
    try:
        coll = get_orders_collection()
        if coll is not None:
            # only set provided fields
            set_doc = {k: v for k, v in updates.items()}
            res = coll.update_one({'id': order_id}, {'$set': set_doc})
            return res.modified_count > 0
    except Exception as e:
        print('update_order_by_id -> mongo error:', e)

    orders_file = os.path.join(os.path.dirname(__file__), 'data', 'orders.json')
    try:
        with open(orders_file, 'r', encoding='utf-8') as f:
            orders = json.load(f)
    except Exception:
        orders = []
    changed = False
    for o in orders:
        if int(o.get('id', 0)) == int(order_id):
            for k, v in updates.items():
                o[k] = v
            changed = True
            break
    if changed:
        with open(orders_file, 'w', encoding='utf-8') as f:
            json.dump(orders, f, indent=2)
    return changed

def send_otp_email(email, otp):
    sendgrid_key = os.environ.get("SENDGRID_API_KEY")
    sender = os.environ.get("SENDGRID_FROM")

    if not sendgrid_key or not sender:
        print(f"[DEV MODE] No SendGrid configured. OTP for {email}: {otp}")
        return

    try:
        payload = {
            "personalizations": [{
                "to": [{"email": email}],
                "subject": "Your OTP Verification"
            }],
            "from": {"email": sender},
            "content": [{
                "type": "text/html",
                "value": f"<h2>Your OTP is: <b>{otp}</b></h2>"
            }]
        }

        headers = {
            "Authorization": f"Bearer {sendgrid_key}",
            "Content-Type": "application/json"
        }

        r = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            json=payload,
            headers=headers,
            timeout=10
        )

        if 200 <= r.status_code < 300:
            print(f"[SendGrid] OTP email sent to {email}")
        else:
            print(f"[SendGrid ERROR] {r.status_code}: {r.text}")

    except Exception as e:
        print("[SendGrid Exception]", e)

@app.route("/auth/request_otp", methods=["POST"])
def request_otp():
    data = request.json
    email = data.get("email")

    if not email:
        return {"success": False, "message": "Email required"}

    otp = random.randint(100000, 999999)

    session["otp"] = otp
    session["email"] = email

    try:
        send_otp_email(email, otp)
        return {"success": True, "message": "OTP sent successfully"}
    except Exception as e:
        # Do NOT delete the session OTP; keep it so the user can still verify
        # while we troubleshoot email delivery. Log the error and the OTP to
        # the server console for debugging. Return success to the client but
        # include the send error for visibility.
        print("send_otp_email error:", e)
        print(f"[WARN] OTP for {email}: {otp}")
        return {"success": True, "message": f"OTP generated but sending failed: {str(e)}. Check server logs for OTP."}
@app.route("/auth/verify_otp", methods=["POST"])
def verify_otp():
    data = request.json
    user_otp = data.get("otp")

    if "otp" not in session:
        return {"success": False, "message": "OTP not generated"}

    if int(user_otp) != session["otp"]:
        return {"success": False, "message": "Invalid OTP"}

    email = session.get("email")
    users = load_users()

    # admin login
    if email and email.lower() in ADMIN_EMAILS:
        session["admin"] = True
        # also set a user identity for admin pages
        session["user"] = "admin"
        return {"success": True, "role": "admin", "redirect": "/admin/dashboard"}

    # If this was a registration flow with password pending, create the user with password
    if session.get("register_email") and session.get("register_password_hash"):
        reg_email = session.pop("register_email")
        reg_hash = session.pop("register_password_hash")
        users = load_users()
        exists = any(u.get("email") == reg_email for u in users.get("users", []))
        if not exists:
            users.setdefault("users", []).append({"email": reg_email, "password": reg_hash})
            save_users(users)
        session["user"] = reg_email
        return {"success": True, "role": "user"}

    # otherwise normal OTP login/2FA
    exists = any(u.get("email") == email for u in users.get("users", []))

    if not exists:
        # create new user without password
        users.setdefault("users", []).append({"email": email})
        save_users(users)

    session["user"] = email
    return {"success": True, "role": "user", "redirect": "/home"}
@app.route("/login")
def login_page():
    # If already authenticated, send the user to their dashboard instead
    if session.get('admin'):
        return redirect('/admin/dashboard')
    if session.get('user'):
        return redirect('/home')
    return send_from_directory("static", "login.html")


@app.route("/admin/test_smtp", methods=["POST"])
def admin_test_smtp():
    """Send a short test email to the provided address and return success/error.

    POST JSON: { "email": "you@example.com" }
    """
    data = request.json or {}
    email = data.get("email")
    if not email:
        return {"success": False, "message": "email required"}, 400

    test_otp = random.randint(100000, 999999)
    try:
        send_otp_email(email, test_otp)
        return {"success": True, "message": f"Test email sent to {email}"}
    except Exception as e:
        return {"success": False, "message": str(e)}, 500


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.json or {}
    email = data.get("email")
    password = data.get("password")
    if not email or not password:
        return {"success": False, "message": "email and password required"}, 400

    u = find_user(email)
    if u:
        return {"success": False, "message": "User already exists"}, 400

    # store password hash temporarily in session until OTP verification completes

    # Hide 'buy' orders from the public marketplace; buy requests should
    # only be visible to admins via the admin orders endpoint.
    p_hash = hash_password(password)
    session["register_email"] = email
    session["register_password_hash"] = p_hash

    otp = random.randint(100000, 999999)
    session["otp"] = otp
    session["email"] = email

    try:
        send_otp_email(email, otp)
        return {"success": True, "message": "OTP sent for registration"}
    except Exception as e:
        print("send_otp_email error (register):", e)
        print(f"[WARN] OTP for {email}: {otp}")
        return {"success": True, "message": f"OTP generated but sending failed: {str(e)}. Check server logs for OTP."}


@app.route("/auth/login_password", methods=["POST"])
def login_password():
    data = request.json or {}
    email = data.get("email")
    password = data.get("password")
    if not email or not password:
        return {"success": False, "message": "email and password required"}, 400

    u = find_user(email)
    if not u or not u.get("password"):
        return {"success": False, "message": "Invalid credentials"}, 401

    if u.get("password") != hash_password(password):
        return {"success": False, "message": "Invalid credentials"}, 401

    # Password OK — start OTP 2FA
    otp = random.randint(100000, 999999)
    session["otp"] = otp
    session["email"] = email
    session["login_via_password"] = True

    try:
        send_otp_email(email, otp)
        return {"success": True, "message": "OTP sent for login"}
    except Exception as e:
        print("send_otp_email error (login_password):", e)
        print(f"[WARN] OTP for {email}: {otp}")
        return {"success": True, "message": f"OTP generated but sending failed: {str(e)}. Check server logs for OTP."}


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user") and not session.get("admin"):
            return jsonify({"success": False, "message": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated


@app.route('/api/order', methods=['POST'])
@login_required
def place_order():
    data = request.get_json() or {}
    required = ['type', 'product', 'quantity', 'price']
    if not all(k in data for k in required):
        return jsonify({'success': False, 'message': 'Missing fields'}), 400

    order = {
        'id': int(time.time() * 1000),
        'user': session.get('user'),
        'type': data['type'],  # 'buy' or 'sell'
        'product': data['product'],
        'quantity': data['quantity'],
        'price': data['price'],
        'timestamp': time.time()
    }

    # Persist order (Mongo or file fallback) and return the saved record.
    try:
        saved = append_order(order)

        # If this is a buy order and a specific listing_id was provided by the client,
        # decrement the corresponding sell listing's quantity so marketplace listings reflect the sale.
        try:
            if (order.get('type') or '').lower() == 'buy':
                # parse numeric quantity
                qty = order.get('quantity')
                try:
                    qnum = float(qty)
                except Exception:
                    qnum = None

                listing_id = request.get_json(silent=True) and request.get_json().get('listing_id')
                if listing_id is None:
                    # also try form data fallback
                    try:
                        listing_id = request.form.get('listing_id')
                    except Exception:
                        listing_id = None

                if listing_id and qnum:
                    try:
                        # Find the sell listing and decrement its quantity (orders collection/file)
                        orders = read_orders()
                        # find by id (ids are stored as ints)
                        target = None
                        for o in orders:
                            try:
                                if int(o.get('id')) == int(listing_id) and (o.get('type') or 'sell').lower() == 'sell':
                                    target = o
                                    break
                            except Exception:
                                continue

                        if target:
                            # determine existing qty
                            existing = target.get('quantity')
                            try:
                                existing_num = float(existing)
                            except Exception:
                                existing_num = None

                            if existing_num is not None:
                                new_qty = max(0, existing_num - qnum)
                                # if zero, remove the listing; otherwise update quantity
                                if new_qty <= 0:
                                    delete_order_by_id(target.get('id'))
                                    print(f"[MARKET] Listing {target.get('id')} sold out and removed (bought {qnum})")
                                else:
                                    update_order_by_id(target.get('id'), {'quantity': new_qty})
                                    print(f"[MARKET] Listing {target.get('id')} quantity reduced by {qnum} -> {new_qty}")
                    except Exception as e:
                        print('place_order -> decrement listing error:', e)

                # If no listing_id available, fall back to product-level adjustment
                elif qnum and order.get('product'):
                    try:
                        adj = adjust_product_quantity(order.get('product'), qnum)
                        if adj is not None:
                            print(f"[STOCK] Adjusted product '{order.get('product')}' by -{qnum}")
                    except Exception as e:
                        print('place_order -> adjust_product_quantity error:', e)
        except Exception as e:
            print('place_order -> post-save adjustment error:', e)

        if saved:
            return jsonify({'success': True, 'order': saved})
    except Exception as e:
        print('place_order -> append_order error:', e)

    # Fallback: return the original order (should be JSON-serializable)
    return jsonify({'success': True, 'order': order})


@app.route('/api/orders', methods=['GET'])
@login_required
def list_orders():
    orders = read_orders()
    user = session.get('user')
    user_orders = [o for o in orders if o.get('user') == user]
    # For non-admin users, hide 'buy' orders from their personal orders view
    # so purchases are only visible to admins. Admins still see everything.
    if session.get('admin'):
        user_orders = [o for o in orders if o.get('user') == user]
    else:
        user_orders = [o for o in orders if o.get('user') == user and (o.get('type') or 'sell').lower() != 'buy']
    return jsonify({'success': True, 'orders': user_orders})


@app.route('/api/marketplace', methods=['GET','POST'])
def marketplace():
    """Public marketplace endpoint.
    GET: returns all orders/listings. Optional query `q` filters product substring (case-insensitive).
    POST: create a new listing. Accepts JSON with keys: product, quantity, price, location, notes, contact (optional).
    """
    orders_file = os.path.join(os.path.dirname(__file__), 'data', 'orders.json')

    # POST -> create new listing
    if request.method == 'POST':
        # Support both JSON and multipart/form-data (file upload from seller page).
        image_filename = None
        if request.files and 'image' in request.files:
            form = request.form
            product = (form.get('product') or '').strip()
            quantity = form.get('quantity')
            price = form.get('price')
            location = form.get('location')
            notes = form.get('notes')
            contact = form.get('contact') or form.get('seller')

            image_file = request.files.get('image')
            # Save uploaded image to static/icons using the same slug rule the frontend uses:
            # js: (product||'market').toLowerCase().replace(/\s+/g,'-') + '.png'
            try:
                slug = re.sub(r"\s+", "-", (product or 'market').strip().lower())
                # Prevent directory traversal
                slug = slug.replace('/', '').replace('\\', '')
                fname = f"{slug}.png"
                icons_dir = os.path.join(os.path.dirname(__file__), 'static', 'icons')
                os.makedirs(icons_dir, exist_ok=True)
                save_path = os.path.join(icons_dir, fname)
                image_file.save(save_path)
                image_filename = fname
                print(f"Saved uploaded image for product='{product}' -> /icons/{fname}")
            except Exception as e:
                print('Failed to save uploaded image:', e)

        else:
            data = request.get_json() or {}
            product = (data.get('product') or '').strip()
            quantity = data.get('quantity')
            price = data.get('price')
            location = data.get('location')
            notes = data.get('notes')
            contact = data.get('contact') or data.get('seller')

        if not product or not quantity or not price:
            return jsonify({'success': False, 'message': 'product, quantity and price required'}), 400

        # load existing orders/listings
        try:
            with open(orders_file, 'r', encoding='utf-8') as f:
                orders = json.load(f)
        except Exception:
            orders = []

        new_id = int(time.time() * 1000)
        user_email = session.get('user')
        seller = user_email or contact or (data.get('seller') if 'data' in locals() else None) or 'anon'

        listing = {
            'id': new_id,
            'user': seller,
            'type': 'sell',
            'product': product,
            'quantity': quantity,
            'price': price,
            'location': location,
            'notes': notes,
            'timestamp': time.time()
        }

        # If we saved an image, include the icon path so clients can reference it explicitly
        if image_filename:
            listing['icon'] = f"/icons/{image_filename}"

        # Persist listing
        try:
            saved = append_order(listing)
        except Exception as e:
            print('Failed to save listing:', e)
            return jsonify({'success': False, 'message': 'Server error saving listing'}), 500

        # Prefer the saved record returned by append_order (it will not include Mongo's _id)
        item = saved if saved else listing
        # Defensive: remove any _id field if present to avoid ObjectId serialization errors
        try:
            if isinstance(item, dict) and '_id' in item:
                item = {k: v for k, v in item.items() if k != '_id'}
        except Exception:
            pass

        return jsonify({'success': True, 'item': item})

    # GET -> list
    q = (request.args.get('q') or '').strip().lower()
    orders = read_orders()

    if q:
        filtered = [o for o in orders if q in (o.get('product') or '').lower()]
    else:
        filtered = orders

    # Special-case: treat a query of 'deals' or a `today=true` flag as
    # request for today's deals only (listings placed on the current date).
    today_flag = str(request.args.get('today') or '').lower() in ('1', 'true', 'yes')
    try:
        if q == 'deals' or today_flag:
            # Use server local date (fromtimestamp) so 'today' aligns with the host timezone.
            today = datetime.fromtimestamp(time.time()).date()
            todays = []
            # debug flag: env or query param
            debug_flag = os.environ.get('MARKET_DEBUG', '0') in ('1', 'true', 'True') or str(request.args.get('debug') or '').lower() in ('1', 'true', 'yes')
            if debug_flag:
                print(f"[MARKET DEBUG] today={today.isoformat()} q={q} pre_filter_count={len(filtered)} orders_count={len(orders)}")

            # Use the full orders list as source so admin-marked ids are always considered
            marked_ids = set(read_today_deals())
            seen = set()
            for o in orders:
                try:
                    # Accept several possible timestamp fields and normalize
                    raw_ts = o.get('timestamp') or o.get('ts') or o.get('created_at') or o.get('id')
                    if raw_ts is None:
                        if debug_flag:
                            print(f"[MARKET DEBUG] skipping id={o.get('id')} product={o.get('product')} reason=no-timestamp")
                        continue
                    norm_ts = float(raw_ts)
                    # Some records store milliseconds (ms) instead of seconds — detect and convert
                    if norm_ts > 1e12:
                        norm_ts = norm_ts / 1000.0
                    elif norm_ts > 1e10:
                        norm_ts = norm_ts / 1000.0
                    dt = datetime.fromtimestamp(norm_ts).date()
                    include = (dt == today) or (int(o.get('id')) in marked_ids if o.get('id') is not None else False)
                    if debug_flag:
                        # Round normalized timestamp to integer seconds and format human readable time
                        try:
                            norm_ts_rounded = int(round(norm_ts))
                            human_ts = datetime.fromtimestamp(norm_ts_rounded).strftime('%Y-%m-%d %H:%M:%S')
                        except Exception:
                            norm_ts_rounded = int(norm_ts)
                            human_ts = str(dt)
                        print(f"[MARKET DEBUG] id={o.get('id')} product={o.get('product')} raw_ts={raw_ts} norm_ts={norm_ts_rounded} ({human_ts}) date={dt} include={include}")
                    if include and int(o.get('id')) not in seen:
                        todays.append(o)
                        seen.add(int(o.get('id')))
                except Exception as e:
                    if debug_flag:
                        print(f"[MARKET DEBUG] id={o.get('id')} parse-error: {str(e)}")
                    # skip entries with unparseable timestamps
                    continue
            filtered = todays
    except Exception:
        # If any error occurs, fall back to the unfiltered list
        pass

    # For public marketplace, do not include 'buy' orders — purchases
    # should not show up in user-facing product lists or recommendations.
    try:
        filtered = [o for o in filtered if (o.get('type') or 'sell').lower() != 'buy']
    except Exception:
        # If any order lacks expected fields, fallback to original filtered list
        pass

    # Return limited public view (do not expose raw user email fully)
    out = []
    for o in filtered:
        display_user = o.get('user')
        if display_user and isinstance(display_user, str) and '@' in display_user:
            display_user = display_user.split('@')[0] + '@…'
        out.append({
            'id': o.get('id'),
            'type': o.get('type'),
            'product': o.get('product'),
            'quantity': o.get('quantity'),
            'price': o.get('price'),
            'timestamp': o.get('timestamp'),
            'seller': display_user,
            'icon': o.get('icon')
        })

    return jsonify({'success': True, 'items': out})


@app.route('/admin/api/today_deals', methods=['GET','POST','DELETE'])
@login_required
def admin_today_deals():
    # Only admin may manage today's deals
    if not session.get('admin'):
        return jsonify({'success': False, 'message': 'admin required'}), 403

    # GET -> list current marked deals with minimal listing info
    if request.method == 'GET':
        ids = read_today_deals()
        orders = read_orders()
        items = []
        for o in orders:
            try:
                if int(o.get('id')) in ids:
                    items.append({
                        'id': o.get('id'), 'product': o.get('product'), 'quantity': o.get('quantity'),
                        'price': o.get('price'), 'timestamp': o.get('timestamp'), 'type': o.get('type')
                    })
            except Exception:
                continue
        return jsonify({'success': True, 'ids': ids, 'items': items})

    data = request.get_json() or {}
    action = data.get('action')
    lid = data.get('id')
    try:
        lid = int(lid)
    except Exception:
        lid = None

    if request.method == 'POST':
        if action != 'add' or not lid:
            return jsonify({'success': False, 'message': 'id and action=add required'}), 400
        ids = read_today_deals()
        if lid in ids:
            return jsonify({'success': True, 'message': 'already exists', 'ids': ids})
        ids.append(lid)
        save_today_deals(ids)
        return jsonify({'success': True, 'ids': ids})

    if request.method == 'DELETE':
        if action != 'remove' or not lid:
            return jsonify({'success': False, 'message': 'id and action=remove required'}), 400
        ids = read_today_deals()
        ids = [x for x in ids if int(x) != lid]
        save_today_deals(ids)
        return jsonify({'success': True, 'ids': ids})

def clean_label(label):

    """Make readable label: 'Apple___Apple_scab' -> 'Apple → Apple scab'"""
    return label.replace("___", " → ").replace("_", " ")

def normalize_key_from_label(readable_label):
    """Take readable label (after clean_label) and create lookup key:
       returns lowercased string with non-alphanumeric removed
    """
    raw = readable_label.split(" → ")[-1]
    key = re.sub(r"[^a-zA-Z0-9]", "", raw).lower()
    return key

def find_remedy(key, readable_label):
    """
    Flexible lookup for DISEASE_REMEDIES.
    Order:
      1) exact key
      2) crop-prefixed key (crop normalized + key)
      3) substring matching (key in k or k in key)
      4) fallback DEFAULT_INFO
    """
    # 1) exact
    if key in DISEASE_REMEDIES:
        return DISEASE_REMEDIES[key]

    # 2) try crop prefix
    crop = readable_label.split(" → ")[0] if " → " in readable_label else ""
    crop_key = re.sub(r"[^a-zA-Z0-9]", "", crop).lower()
    if crop_key:
        pref = crop_key + key
        if pref in DISEASE_REMEDIES:
            return DISEASE_REMEDIES[pref]

    # 3) substring heuristics
    for k in DISEASE_REMEDIES.keys():
        if key in k or k in key:
            return DISEASE_REMEDIES[k]

    # 4) fallback
    return DEFAULT_INFO

def preprocess_image(img_bytes, target_size=(224,224)):
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    img = img.resize(target_size)
    arr = np.array(img, dtype=np.float32) / 255.0
    arr = np.expand_dims(arr, axis=0)
    return arr

# -----------------------------------------------------
#   PREDICT ROUTE
# -----------------------------------------------------
@app.route("/predict", methods=["POST"])
def predict():
    if model is None:
        # Friendly fallback when model isn't available: return unknown disease
        info = DEFAULT_INFO
        return jsonify({
            "index": None,
            "raw_label": None,
            "disease": "Unknown",
            "confidence": 0.0,
            "description": info.get("description"),
            "remedies": info.get("remedies"),
            "prevention": info.get("prevention"),
            "daily_care": info.get("daily_care")
        })

    if "image" not in request.files:
        return jsonify({"error": "Missing image"}), 400

    try:
        img_bytes = request.files["image"].read()
        x = preprocess_image(img_bytes)
        preds = model.predict(x)[0]
    except Exception as e:
        return jsonify({"error": f"Failed to process image/model predict: {str(e)}"}), 500

    idx = int(np.argmax(preds))
    confidence = float(preds[idx])
    raw_label = DISEASE_CLASSES[idx]
    readable_label = clean_label(raw_label)
    key = normalize_key_from_label(readable_label)

    print("Prediction index:", idx, "label:", raw_label, "key:", key, "conf:", confidence)

    info = find_remedy(key, readable_label)

    return jsonify({
        "index": idx,
        "raw_label": raw_label,
        "disease": readable_label,
        "confidence": round(confidence, 4),
        "description": info.get("description"),
        "remedies": info.get("remedies"),
        "prevention": info.get("prevention"),
        "daily_care": info.get("daily_care")
    })

# -----------------------------------------------------
#   AGMARKNET SCRAPER + CACHE SETUP
# -----------------------------------------------------
CACHE_DIR = "data"
CACHE_FILE = os.path.join(CACHE_DIR, "prices.json")
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR, exist_ok=True)

def load_cache():
    # Prefer Mongo-stored cache when available
    try:
        if mongo_db is not None:
            coll = mongo_db.get_collection('prices')
            doc = coll.find_one({}, {'_id': 0})
            if doc and 'cache' in doc:
                return doc['cache']
    except Exception as e:
        print('load_cache -> mongo error:', e)

    if os.path.exists(CACHE_FILE):
        try:
            return json.load(open(CACHE_FILE, "r", encoding="utf-8"))
        except Exception as e:
            print("Warning: failed to read cache:", e)
            return {"last_updated": None, "commodities": {}}
    return {"last_updated": None, "commodities": {}}

def save_cache(cache):
    # Prefer storing cache to Mongo when available
    try:
        if mongo_db is not None:
            coll = mongo_db.get_collection('prices')
            coll.delete_many({})
            coll.insert_one({'cache': cache})
            return
    except Exception as e:
        print('save_cache -> mongo error:', e)

    try:
        json.dump(cache, open(CACHE_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    except Exception as e:
        print("Warning: failed to write cache:", e)

def norm(c: str):
    return c.strip().lower()

# AGMARKNET / datagov urls & headers
AGMARKNET_SEARCH_URL = "https://agmarknet.gov.in/SearchCmmMkt.aspx?CommName={commodity}"
AGMARKNET_COMMODITY_URL = "https://agmarknet.gov.in/PriceAndArrivals/CommodityWisePrices.aspx?CommName={commodity}"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FarmerAssistant/1.0; +http://localhost/)"}

def parse_price_table_from_soup(soup):
    table = None
    for tid in ["DataGrid1", "gvPrices", "ctl00_ContentPlaceHolder1_gvPrice"]:
        table = soup.find("table", id=tid)
        if table:
            break
    if not table:
        for t in soup.find_all("table"):
            ths = [th.get_text(strip=True).lower() for th in t.find_all("th")]
            if any(x in ths for x in ("market", "state", "district", "arrival")):
                table = t
                break
    if not table:
        return []

    headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
    rows_out = []
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        texts = [td.get_text(strip=True) for td in tds]
        n = len(texts)
        rec = {}
        if n >= 6:
            if "market" in headers:
                for i, h in enumerate(headers[:n]):
                    key = h.replace(" ", "_")
                    rec[key] = texts[i]
            else:
                rec["market"] = texts[0]
                if n >= 7:
                    rec["district"] = texts[1]
                    rec["state"] = texts[2]
                    rec["min_price"] = texts[-4]
                    rec["max_price"] = texts[-3]
                    rec["modal_price"] = texts[-2]
                    rec["arrival_date"] = texts[-1]
                else:
                    rec["min_price"] = texts[-3]
                    rec["max_price"] = texts[-2]
                    rec["modal_price"] = texts[-1]
        else:
            continue

        for k in ("min_price", "max_price", "modal_price"):
            if k in rec:
                try:
                    rec[k] = int("".join([ch for ch in rec[k] if ch.isdigit()]))
                except:
                    try:
                        rec[k] = float(rec[k].replace(",", "").split()[0])
                    except:
                        rec[k] = None

        rec.setdefault("variety", None)
        rec.setdefault("grade", None)
        rec.setdefault("district", rec.get("district", ""))
        rec.setdefault("state", rec.get("state", ""))
        rec.setdefault("arrival_date", rec.get("arrival_date", ""))

        rows_out.append(rec)
    return rows_out

def fetch_from_agmarknet(commodity):
    c = commodity.strip()
    try_urls = [
        AGMARKNET_COMMODITY_URL.format(commodity=c),
        AGMARKNET_SEARCH_URL.format(commodity=c)
    ]
    for url in try_urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=12)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "lxml")
            recs = parse_price_table_from_soup(soup)
            if recs:
                for rec in recs:
                    rec["commodity"] = commodity
                return recs
        except Exception as e:
            print("agmarknet fetch error for", url, ":", e)
            continue
    return []

# fallback: data.gov.in dataset
DATA_GOV_URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
DATA_GOV_KEY = "579b464db66ec23bdd0000019f3a4436fd4c478c533152e915ffe027"

def fetch_from_datagov(commodity, limit=40):
    params = {
        "api-key": DATA_GOV_KEY,
        "format": "json",
        "limit": limit,
        "filters[commodity]": commodity
    }
    try:
        r = requests.get(DATA_GOV_URL, params=params, timeout=10)
        if r.status_code != 200:
            return []
        j = r.json()
        recs = j.get("records", [])
        out = []
        for d in recs:
            rec = {
                "market": d.get("market", ""),
                "district": d.get("district", ""),
                "state": d.get("state", ""),
                "variety": d.get("variety", None),
                "grade": d.get("grade", None),
                "min_price": int(d.get("min_price")) if d.get("min_price") and str(d.get("min_price")).isdigit() else None,
                "max_price": int(d.get("max_price")) if d.get("max_price") and str(d.get("max_price")).isdigit() else None,
                "modal_price": int(d.get("modal_price")) if d.get("modal_price") and str(d.get("modal_price")).isdigit() else None,
                "arrival_date": d.get("arrival_date") or d.get("date")
            }
            out.append(rec)
        return out
    except Exception as e:
        print("fetch_from_datagov error:", e)
        return []

def update_prices_for_commodity(commodity, force=False):
    cache = load_cache()
    key = norm(commodity)
    now = datetime.utcnow().isoformat()
    existing = cache.get("commodities", {}).get(key)
    if existing and not force:
        last = cache.get("last_updated")
        if last:
            try:
                last_dt = datetime.fromisoformat(last)
                if datetime.utcnow() - last_dt < timedelta(hours=12):
                    print("Using recent cache for", key)
                    return cache
            except Exception:
                pass

    recs = fetch_from_agmarknet(commodity)
    if not recs:
        recs = fetch_from_datagov(commodity)

    cache.setdefault("commodities", {})[key] = {
        "fetched_at": now,
        "items": recs
    }
    cache["last_updated"] = now
    save_cache(cache)
    return cache

# -----------------------------------------------------
#   Scheduler: daily refresh
# -----------------------------------------------------
scheduler = BackgroundScheduler()
def scheduled_daily_refresh():
    cache = load_cache()
    commodities = list(cache.get("commodities", {}).keys())
    if not commodities:
        for c in ["tomato", "banana", "onion", "potato"]:
            print("Initial scheduled fetch:", c)
            update_prices_for_commodity(c)
    else:
        for c in commodities:
            print("Scheduled refresh:", c)
            update_prices_for_commodity(c)

scheduler.add_job(scheduled_daily_refresh, 'interval', hours=24, next_run_time=datetime.utcnow())
try:
    scheduler.start()
except Exception as e:
    print("Scheduler start error:", e)

# -----------------------------------------------------
#   PRICE ENDPOINTS (use cache, add admin refresh)
# -----------------------------------------------------
@app.route("/price")
def price():
    commodity = request.args.get("commodity")
    if not commodity:
        return jsonify({"success": False, "msg": "Commodity required"}), 400
    key = norm(commodity)
    cache = load_cache()
    data = cache.get("commodities", {}).get(key, {})
    items = data.get("items", [])

    if not items:
        try:
            update_prices_for_commodity(commodity, force=True)
            cache = load_cache()
            items = cache.get("commodities", {}).get(key, {}).get("items", [])
        except Exception as e:
            return jsonify({"success": False, "msg": f"Fetch failed: {str(e)}"}), 500

    return jsonify({"success": True, "data": items})

# Admin refresh endpoint
ADMIN_USER = "admin"
ADMIN_PASS = "1234"
# Admin emails (comma-separated) that should be treated as admin when they verify via OTP.
# You can set environment variable ADMIN_EMAILS="admin@gmail.com,gowthamst98438@gmail.com,agriai360@gmail.com"
# Default list includes the main admin addresses; environment variable can override this.
ADMIN_EMAILS = [e.strip().lower() for e in os.environ.get('ADMIN_EMAILS', 'admin@gmail.com,gowthamst98438@gmail.com,agriai360@gmail.com').split(',') if e.strip()]

@app.route("/admin/refresh_price")
def admin_refresh_price():
    if not session.get("admin"):
        return jsonify({"success": False, "msg": "Not authorized"}), 403
    commodity = request.args.get("commodity")
    if not commodity:
        return jsonify({"success": False, "msg": "commodity param required"}), 400
    update_prices_for_commodity(commodity, force=True)
    return jsonify({"success": True, "msg": f"Refreshed {commodity}"})

# -----------------------------------------------------
#   ADMIN PAGES / LOGIN
# -----------------------------------------------------
@app.route("/admin/login")
def admin_login_page():
    return send_from_directory("static", "admin_login.html")

@app.route("/admin/login", methods=["POST"])
def admin_login():
    data = request.json
    if not data:
        return {"success": False, "message": "Missing JSON"}
    if data.get("username") == ADMIN_USER and data.get("password") == ADMIN_PASS:
        session["admin"] = True
        session["user"] = "admin"
        return {"success": True, "redirect": "/admin/dashboard"}
    return {"success": False, "message": "Invalid login"}

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect("/admin/login")

def require_admin():
    if not session.get("admin"):
        return redirect("/admin/login")
    return None

@app.route("/admin")
def admin_root():
    return redirect("/admin/dashboard")

@app.route("/admin/dashboard")
def admin_dashboard():
    x = require_admin()
    if x:
        return x
    return send_from_directory("static", "admin_dashboard.html")

@app.route("/admin/commodities")
def admin_com():
    x = require_admin()
    if x:
        return x
    return send_from_directory("static", "admin_commodities.html")

@app.route("/admin/diseases")
def admin_dis():
    x = require_admin()
    if x:
        return x
    return send_from_directory("static", "admin_diseases.html")

@app.route("/admin/analytics")
def admin_an():
    x = require_admin()
    if x:
        return x
    return send_from_directory("static", "admin_analytics.html")

@app.route("/admin/data")
def admin_data():
    x = require_admin()
    if x:
        return x
    return load_cache()


@app.route('/admin/orders')
def admin_orders_page():
    x = require_admin()
    if x:
        return x
    return send_from_directory('static', 'admin_orders.html')


@app.route('/admin/products')
def admin_products_page():
    x = require_admin()
    if x:
        return x
    return send_from_directory('static', 'admin_products.html')


@app.route('/admin/api/products', methods=['GET','POST'])
def admin_api_products():
    x = require_admin()
    if x:
        return x
    # Prefer Mongo products collection when available
    try:
        if mongo_db is not None:
            coll = mongo_db.get_collection('products')
            prods = list(coll.find({}, {'_id': 0}))
            if request.method == 'GET':
                return jsonify({'success': True, 'products': prods})
    except Exception as e:
        print('admin_api_products -> mongo error:', e)

    products_file = os.path.join(os.path.dirname(__file__), 'data', 'products.json')
    # read
    try:
        with open(products_file, 'r', encoding='utf-8') as f:
            pdata = json.load(f)
    except Exception:
        pdata = {"products": []}

    if request.method == 'GET':
        return jsonify({'success': True, 'products': pdata.get('products', [])})


@app.route('/api/products', methods=['GET'])
def public_products():
    """Public endpoint returning available products for marketplace and buy/sell pages."""
    try:
        if mongo_db is not None:
            coll = mongo_db.get_collection('products')
            prods = list(coll.find({'available': True}, {'_id': 0}))
            return jsonify({'success': True, 'products': prods})
    except Exception as e:
        print('public_products -> mongo error:', e)

    products_file = os.path.join(os.path.dirname(__file__), 'data', 'products.json')
    try:
        with open(products_file, 'r', encoding='utf-8') as f:
            pdata = json.load(f)
    except Exception:
        pdata = {"products": []}

    available = [p for p in pdata.get('products', []) if p.get('available', False)]
    return jsonify({'success': True, 'products': available})


def write_products(pdata, force=False):
    """Write products to Mongo (preferred) or to `data/products.json` with logging.
    This centralizes product writes and logs the caller so accidental writers can be traced.
    """
    caller = None
    try:
        # get the immediate caller function name for logging
        caller = inspect.stack()[1].function
    except Exception:
        caller = '<unknown>'

    # Prevent product writes originating from non-admin HTTP requests.
    try:
        # Allow internal callers to force writes by passing force=True.
        if has_request_context() and not session.get('admin') and not force:
            print(f"[PRODUCTS] Write blocked (caller={caller}) - non-admin request")
            return
    except Exception:
        # If session access fails, continue (non-request contexts like scripts should be allowed)
        pass

    try:
        if mongo_db is not None:
            coll = mongo_db.get_collection('products')
            # Replace collection contents with provided list (clear then insert)
            coll.delete_many({})
            if pdata.get('products'):
                # ensure each product is a plain dict without _id
                docs = [p.copy() for p in pdata.get('products')]
                coll.insert_many(docs)
            print(f"[PRODUCTS] Updated Mongo 'products' collection (caller={caller})")
            return
    except Exception as e:
        print('write_products -> mongo error:', e)

    products_file = os.path.join(os.path.dirname(__file__), 'data', 'products.json')
    try:
        with open(products_file, 'w', encoding='utf-8') as f:
            json.dump(pdata, f, indent=2)
        print(f"[PRODUCTS] Wrote products.json (caller={caller})")
    except Exception as e:
        print('write_products -> file error:', e)


@app.route('/model/status')
def model_status():
    """Return whether ML model is loaded and any diagnostics message."""
    try:
        loaded = model is not None
        msg = 'Model loaded' if loaded else 'Model not loaded'
    except Exception as e:
        loaded = False
        msg = f'Error checking model: {e}'
    return jsonify({'loaded': loaded, 'message': msg})


# --------------------
# Weather Advice Page + API proxy
# --------------------
@app.route('/weather')
def weather_page():
    """Serve the weather advice static page."""
    try:
        return send_from_directory('static', 'weather.html')
    except Exception:
        return "Weather page not available", 404


@app.route('/api/weather')
def api_weather():
    """Proxy endpoint to fetch weather forecast and produce simple advice.
    Accepts query parameters: lat, lon OR q (city name). Requires env var WEATHER_API_KEY.
    Returns the upstream forecast JSON under `forecast` and an `advice` array.
    """
    key = os.environ.get('WEATHER_API_KEY')
    if not key:
        hint = 'Set WEATHER_API_KEY in the environment or in a .env file. See .env.example for format.'
        example = 'WEATHER_API_KEY=your_openweather_api_key_here'
        return jsonify({'error': 'WEATHER_API_KEY not configured on server', 'hint': hint, 'example_env': example}), 400

    lat = request.args.get('lat')
    lon = request.args.get('lon')
    q = request.args.get('q')
    try:
        # If no coordinates provided but a query (city) is given, geocode first
        if (not lat or not lon) and q:
            geo_url = 'http://api.openweathermap.org/geo/1.0/direct'
            gr = requests.get(geo_url, params={'q': q, 'limit': 1, 'appid': key}, timeout=10)
            if gr.status_code != 200:
                return jsonify({'error': 'Geocoding failed', 'details': gr.text}), 502
            gdata = gr.json()
            if not gdata:
                return jsonify({'error': 'Could not resolve location name'}), 400
            lat = gdata[0].get('lat')
            lon = gdata[0].get('lon')

        if not lat or not lon:
            return jsonify({'error': 'Provide lat & lon or q (city name) as query parameters.'}), 400

        # One Call API for forecast (exclude minutely & alerts to reduce payload)
        owm = 'https://api.openweathermap.org/data/2.5/onecall'
        resp = requests.get(owm, params={'lat': lat, 'lon': lon, 'exclude': 'minutely,alerts', 'units': 'metric', 'appid': key}, timeout=12)
        if resp.status_code != 200:
            # log provider failure and attempt a fallback to 3-hour forecast endpoint
            try:
                print('[WEATHER] OneCall failed:', resp.status_code, resp.text[:500])
            except Exception:
                pass
            # fallback to 3-hour forecast which is commonly available on free tier
            try:
                fb = requests.get('https://api.openweathermap.org/data/2.5/forecast', params={'lat': lat, 'lon': lon, 'units': 'metric', 'appid': key}, timeout=12)
                if fb.status_code == 200:
                    fbp = fb.json()
                    payload = {'fallback_forecast': fbp}
                else:
                    # return both error snippets for diagnosis
                    return jsonify({'error': 'Weather provider error', 'onecall_status': resp.status_code, 'onecall_body': resp.text, 'fallback_status': fb.status_code, 'fallback_body': fb.text}), 502
            except Exception as e:
                print('[WEATHER] Fallback fetch exception', e)
                return jsonify({'error': 'Weather provider error', 'details': str(e), 'onecall_status': resp.status_code, 'onecall_body': resp.text}), 502
        else:
            payload = resp.json()

        # Build a short human-friendly summary for frontends.
        summary = ''
        try:
            # If we have One Call daily data, summarize highs/lows and precipitation chance
            if payload.get('daily'):
                ds = payload.get('daily', [])[:3]
                highs = [d.get('temp', {}).get('max') for d in ds if d.get('temp')]
                lows = [d.get('temp', {}).get('min') for d in ds if d.get('temp')]
                pops = [d.get('pop', 0) for d in ds]
                max_high = max([h for h in highs if h is not None], default=None)
                min_low = min([l for l in lows if l is not None], default=None)
                avg_pop = round((sum(pops)/len(pops))*100) if pops else 0
                parts = []
                if max_high is not None and min_low is not None:
                    parts.append(f"Next 3 days temps {min_low:.0f}°C–{max_high:.0f}°C")
                if avg_pop:
                    parts.append(f"Chance of precipitation ~{avg_pop}%")
                summary = ' — '.join(parts)
            elif payload.get('fallback_forecast'):
                # The fallback provides 3-hour 'list' entries. Summarize next 24-48h.
                fl = payload.get('fallback_forecast', {})
                entries = fl.get('list', [])[:8]  # next 24h (8 * 3h)
                temps = [e.get('main', {}).get('temp') for e in entries if e.get('main')]
                pops = []
                will_rain = False
                wind_speeds = []
                for e in entries:
                    if e.get('pop') is not None:
                        pops.append(e.get('pop'))
                    # providers sometimes include rain object
                    if e.get('weather') and isinstance(e.get('weather'), list):
                        wid = (e.get('weather')[0].get('id') or 0)
                        if 500 <= wid < 700:
                            will_rain = True
                    if e.get('wind') and e.get('wind').get('speed') is not None:
                        wind_speeds.append(e.get('wind').get('speed'))
                max_t = max([t for t in temps if t is not None], default=None)
                min_t = min([t for t in temps if t is not None], default=None)
                avg_pop = round((sum(pops)/len(pops))*100) if pops else 0
                parts = []
                if min_t is not None and max_t is not None:
                    parts.append(f"Next 24h temps {min_t:.0f}°C–{max_t:.0f}°C")
                if avg_pop:
                    parts.append(f"Chance of precipitation ~{avg_pop}%")
                if will_rain:
                    parts.append('Rain likely within 24h')
                if wind_speeds:
                    parts.append(f"Wind up to {max(wind_speeds):.0f} m/s")
                summary = ' — '.join(parts)
        except Exception:
            summary = ''

        # Simple advice rules based on next 3 days
        advice = []
        daily = payload.get('daily', [])[:3]
        for day in daily:
            pop = day.get('pop', 0)  # probability of precipitation
            temps = day.get('temp', {})
            tmax = temps.get('max')
            tmin = temps.get('min')
            weather = (day.get('weather') or [{}])[0]
            wid = weather.get('id', 0)
            # Rain / precipitation
            if pop and pop >= 0.5:
                advice.append('Rain likely — consider covering susceptible crops and postponing sprays.')
            # High heat
            if tmax is not None and tmax >= 35:
                advice.append('High temperatures expected — increase irrigation and monitor for heat stress.')
            # Frost / cold
            if tmin is not None and tmin <= 3:
                advice.append('Low temperatures expected — protect young seedlings from frost.')
            # Wind
            wind = day.get('wind_speed', 0)
            if wind and wind >= 10:
                advice.append('Strong winds expected — secure structures and avoid spraying on high-wind days.')

        # Deduplicate while preserving order
        seen = set()
        dedup = []
        for a in advice:
            if a not in seen:
                dedup.append(a); seen.add(a)

        # Ensure advice is non-empty with a friendly fallback
        if not dedup:
            dedup = [ 'No specific advice for the next days.' ]

        out = {'forecast': payload, 'advice': dedup}
        if summary:
            out['summary'] = summary
        return jsonify(out)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/user')
def api_user():
    """Return basic user info for the current session."""
    user_email = session.get('user')
    is_admin = bool(session.get('admin'))
    if not user_email:
        return jsonify({'logged': False, 'user': None, 'is_admin': is_admin})

    users = load_users().get('users', [])
    urec = None
    for u in users:
        if u.get('email') == user_email:
            urec = u
            break

    # count orders (use Mongo when available)
    orders = read_orders()
    user_orders = [o for o in orders if o.get('user') == user_email]

    return jsonify({'logged': True, 'user': {'email': user_email, 'info': urec or {}}, 'is_admin': is_admin, 'orders_count': len(user_orders)})


@app.route('/auth/logout', methods=['POST'])
def auth_logout():
    session.pop('user', None)
    session.pop('admin', None)
    return jsonify({'success': True})


@app.route('/profile')
def profile_page():
    # profile page for users
    return send_from_directory('static', 'profile.html')



@app.route('/admin/api/product/<int:product_id>/delete', methods=['POST'])
def admin_api_product_delete(product_id):
    x = require_admin()
    if x:
        return x
    products_file = os.path.join(os.path.dirname(__file__), 'data', 'products.json')
    try:
        with open(products_file, 'r', encoding='utf-8') as f:
            pdata = json.load(f)
    except Exception:
        pdata = {"products": []}

    newp = [p for p in pdata.get('products', []) if int(p.get('id',0)) != product_id]
    pdata['products'] = newp
    # Use centralized writer so we log and avoid accidental writes elsewhere
    write_products(pdata)
    return jsonify({'success': True})


@app.route('/admin/api/product/<int:product_id>/toggle', methods=['POST'])
def admin_api_product_toggle(product_id):
    x = require_admin()
    if x:
        return x
    products_file = os.path.join(os.path.dirname(__file__), 'data', 'products.json')
    try:
        with open(products_file, 'r', encoding='utf-8') as f:
            pdata = json.load(f)
    except Exception:
        pdata = {"products": []}

    changed = False
    for p in pdata.get('products', []):
        if int(p.get('id',0)) == product_id:
            p['available'] = not bool(p.get('available', False))
            changed = True
            break

    if changed:
        # Use centralized writer so we log and avoid accidental writes elsewhere
        write_products(pdata)
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'not found'}), 404


@app.route('/admin/api/orders', methods=['GET'])
def admin_api_list_orders():
    x = require_admin()
    if x:
        return x
    orders = read_orders()

    # Optional filtering by type (e.g. ?type=sell or ?type=buy)
    req_type = (request.args.get('type') or '').strip().lower()
    if req_type in ('sell', 'buy'):
        try:
            orders = [o for o in orders if ((o.get('type') or 'sell').lower() == req_type)]
        except Exception:
            pass

    # Optional limit param
    try:
        limit = int(request.args.get('limit')) if request.args.get('limit') else None
    except Exception:
        limit = None

    # Sort by timestamp (newest first). Fallback to id if timestamp missing.
    def _order_key(o):
        try:
            return float(o.get('timestamp') or (int(o.get('id', 0)) / 1000.0))
        except Exception:
            return 0

    try:
        orders = sorted(orders, key=_order_key, reverse=True)
    except Exception:
        pass

    if limit:
        orders = orders[:limit]

    return jsonify({'success': True, 'orders': orders})


@app.route('/admin/api/order/<int:order_id>/delete', methods=['POST'])
def admin_api_delete_order(order_id):
    x = require_admin()
    if x:
        return x
    delete_order_by_id(order_id)
    return jsonify({'success': True})


@app.route('/admin/api/order/<int:order_id>/update', methods=['POST'])
def admin_api_update_order(order_id):
    x = require_admin()
    if x:
        return x
    data = request.get_json() or {}
    status = data.get('status')  # optional new status
    price = data.get('price')
    quantity = data.get('quantity')
    updates = {}
    if status is not None:
        updates['status'] = status
    if price is not None:
        try:
            updates['price'] = float(price)
        except:
            pass
    if quantity is not None:
        try:
            updates['quantity'] = float(quantity)
        except:
            pass

    ok = update_order_by_id(order_id, updates)
    if ok:
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Order not found'}), 404

@app.route("/admin/add_commodity", methods=["POST"])
def add_com():
    x = require_admin()
    if x:
        return x
    db = load_cache()
    name = request.json.get("name")
    key = norm(name)
    db.setdefault("commodities", {})
    if key not in db["commodities"]:
        db["commodities"][key] = {"fetched_at": None, "items": []}
        save_cache(db)
    return {"ok": True}

@app.route("/admin/add_disease", methods=["POST"])
def add_dis():
    x = require_admin()
    if x:
        return x
    db = load_cache()
    db.setdefault("diseases", [])
    db["diseases"].append({
        "name": request.json.get("name"),
        "solution": request.json.get("solution")
    })
    save_cache(db)
    return {"ok": True}

# -----------------------------------------------------
#   USER PAGES - static
# -----------------------------------------------------
@app.route("/")
def splash():
    # Always serve the login page as the site entry point. The client-side
    # login UI will check session state and redirect to /home when appropriate.
    return send_from_directory('static', 'login.html')


@app.route("/home")
def home():
    # Serve the home/dashboard only to authenticated users. If not
    # authenticated redirect to the login page. Always send headers
    # to prevent caching so browsers don't show stale login HTML for /home.
    try:
        print(f"[home-route] session.keys={list(session.keys())} user={session.get('user')} admin={bool(session.get('admin'))}")
    except Exception:
        pass

    if not session.get("user") and not session.get("admin"):
        print("[home-route] unauthenticated -> redirect /login")
        return redirect("/login")

    print("[home-route] authenticated -> serve home.html")
    resp = make_response(send_from_directory("static", "home.html"))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    return resp
@app.route("/detect")
def detect_page():
    # Serve the detect UI (requires login via before_request guard)
    return send_from_directory("static", "detect.html")
@app.route("/market")
def market_page():
    return send_from_directory("static", "market.html")


@app.route('/buy.html')
def buy_page_static():
    # Serve buyer page directly
    return send_from_directory('static', 'buy.html')


@app.route('/sell.html')
def sell_page_static():
    # Serve seller/contact page directly
    return send_from_directory('static', 'sell.html')


@app.route('/buy')
def buy_page_short():
    return send_from_directory('static', 'buy.html')


@app.route('/sell')
def sell_page_short():
    return send_from_directory('static', 'sell.html')


@app.route('/cart.html')
def cart_page_static():
    # Serve cart page
    try:
        print(f"[route] /cart.html requested session.user={'SET' if session.get('user') else 'NONE'} admin={bool(session.get('admin'))}")
    except Exception:
        pass
    return send_from_directory('static', 'cart.html')


@app.route('/cart')
def cart_page_short():
    try:
        print(f"[route] /cart requested session.user={'SET' if session.get('user') else 'NONE'} admin={bool(session.get('admin'))}")
    except Exception:
        pass
    return send_from_directory('static', 'cart.html')


@app.route('/ping')
def ping():
    return jsonify({'ok': True, 'time': time.time()})


@app.route("/buy-sell")
def buy_sell_page():
    # Allow public viewing of the Buy/Sell page so visitors can see listings.
    # Placing orders is still blocked by the `/api/order` login_required decorator.
    return send_from_directory("static", "buy_sell.html")

@app.route("/about")
def about_page():
    return send_from_directory("static", "about.html")

@app.route("/contact")
def contact_page():
    return send_from_directory("static", "contact.html")

# -----------------------------------------------------
#   STATIC FILES (icons & css)
# -----------------------------------------------------
@app.route("/icons/<path:f>")
def serve_icons(f):
    return send_from_directory("static/icons", f)

@app.route("/<filename>.css")
def serve_css(filename):
    return send_from_directory("static", f"{filename}.css")


@app.route('/header.js')
def serve_header_js():
    # Serve the shared header script at the top-level path so pages can
    # include <script src="/header.js"></script> without using /static/.
    return send_from_directory('static', 'header.js')


@app.route('/theme.js')
def serve_theme_js():
    # Serve theme loader so pages can set dark/light class early
    return send_from_directory('static', 'theme.js')


@app.route('/i18n.js')
def serve_i18n_js():
    # Serve the client-side translations file at top-level so pages
    # can include <script src="/i18n.js"></script> just like other helpers.
    return send_from_directory('static', 'i18n.js')


# Protect direct static access to the home page file. Some users may attempt to
# open `/static/home.html` directly; this route enforces the same login
# requirement as the `/home` view and redirects anonymous visitors to `/login`.
@app.route('/static/home.html')
def static_home_file():
    if not session.get('user') and not session.get('admin'):
        return redirect('/login')
    return send_from_directory('static', 'home.html')


# Global guard: ensure static file access to home cannot bypass login.
@app.before_request
def _guard_static_home_access():
    # If a request targets the static home file (or the file directly),
    # require an authenticated session. This catches Flask's built-in
    # static-file handling as well as direct requests.
    p = (request.path or '').lower()
    # Debugging: print path and minimal session state so we can see why
    # anonymous requests might be reaching /home.
    try:
        print(f"[guard] request.path={p} session.user={'SET' if session.get('user') else 'NONE'} admin={bool(session.get('admin'))}")
    except Exception:
        pass

    # Check common variants that should be protected
    if p.endswith('/static/home.html') or p.endswith('/home.html') or p == '/home' or p == '/home/':
        if not session.get('user') and not session.get('admin'):
            return redirect('/login')

    # --- GENERAL PAGE GUARD ---
    # Enforce login for any HTML page routes while allowing static assets,
    # auth endpoints and API/static resources to load.
    # Allowlist (public) prefixes and file types that must remain reachable
    public_prefixes = (
        '/login', '/auth', '/static/', '/icons/', '/header.js', '/model/status', '/predict', '/admin/login'
    )

    # allow direct access to buyer/seller static pages
    # (these are top-level static HTML files we added: /buy.html, /sell.html and short paths /buy, /sell)
    public_prefixes = public_prefixes + ('/buy.html', '/sell.html', '/buy', '/sell', '/cart.html', '/cart')

    # If request targets a public prefix or static asset, skip
    if any(p.startswith(pref) for pref in public_prefixes):
        return
    if p.endswith('.css') or p.endswith('.js') and p.endswith('/header.js'):
        return

    # Admin area requires admin session
    if p.startswith('/admin'):
        if not session.get('admin'):
            return redirect('/admin/login')
        return

    # For other page-like requests (common site pages or direct .html), require normal user login
    page_like = (
        '/', '/home', '/detect', '/market', '/buy-sell', '/about', '/contact', '/profile'
    )

    if p in page_like or p.endswith('.html'):
        if not session.get('user') and not session.get('admin'):
            return redirect('/login')

# -----------------------------------------------------
#   RUN SERVER
# -----------------------------------------------------
if __name__ == "__main__":
    # Prime cache with common commodities (best-effort)
    try:
        for c in ["tomato", "banana", "onion", "potato"]:
            try:
                update_prices_for_commodity(c)
                time.sleep(1)
            except Exception as e:
                print("Initial fetch error for", c, ":", e)
    except Exception as e:
        print("Initial seeding error:", e)

    app.run(debug=True, host="0.0.0.0", port=5000)
