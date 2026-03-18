# app.py
# app.py
import re
import os
import sys
import requests
import io
import json
import smtplib
import random
import difflib
import html
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import time
import ssl
import threading
import base64
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify, send_from_directory, session, redirect, make_response, has_request_context
from flask_cors import CORS
from functools import wraps  # 🔥 FIXED
import socket                # 🔥 moved here
import inspect
import hashlib
from bs4 import BeautifulSoup, FeatureNotFound
from apscheduler.schedulers.background import BackgroundScheduler
try:
    from google.auth.transport import requests as google_auth_requests
    from google.oauth2 import id_token as google_id_token
except Exception:
    google_auth_requests = None
    google_id_token = None

FIREBASE_PUBLIC_CONFIG_DEFAULTS = {
    'apiKey': 'AIzaSyBAYRHwH83zvX8EwAiLKvzPDvrkeYUyAAc',
    'authDomain': 'agriai360-33883.firebaseapp.com',
    'projectId': 'agriai360-33883',
    'storageBucket': 'agriai360-33883.firebasestorage.app',
    'messagingSenderId': '394654173571',
    'appId': '1:394654173571:web:3dee063716140c9b290eb6',
    'measurementId': 'G-Z9Y1Y6W8FV',
}

# ================== SMTP Mail Config ==================
# SMTP is configured via environment variables (optionally via .env).
# See `.env.example` for supported settings.



# ============================
# 🔥 MODEL DOWNLOAD + LOAD
# ============================

MODEL_URL = "https://drive.google.com/uc?export=download&id=1nn-JVOCSpMqYSNE6Vy0TQ9nq251M94BI"
MODEL_PATH = "model.keras"


def download_from_drive():
    print("\n📥 Requesting large model from Google Drive...\n")
    session = requests.Session()
    response = session.get(MODEL_URL, stream=True)

    token = None
    for key, value in response.cookies.items():
        if key.startswith("download_warning"):
            token = value
            break

    if token:
        print("⚠️ Large file detected — confirming download...")
        params = {"id": "1nn-JVOCSpMqYSNE6Vy0TQ9nq251M94BI", "confirm": token}
        response = session.get(MODEL_URL, params=params, stream=True)

    print("⬇ Saving model... may take a while\n")
    with open(MODEL_PATH, "wb") as f:
        for chunk in response.iter_content(32768):
            if chunk:
                f.write(chunk)

    print("✅ Model saved successfully as model.keras\n")


# ------------------ LOAD MODEL ON DEMAND ------------------
model = None

def load_model_lazy():
    global model
    if tf is None:
        raise RuntimeError('tensorflow not installed; install tensorflow to enable disease prediction')
    if model is None:
        if not os.path.exists(MODEL_PATH):
            download_from_drive()
        print("📦 Loading .keras model...")
        try:
            model = tf.keras.models.load_model(MODEL_PATH)
        except Exception as e:
            msg = str(e)
            # This project currently ships a .keras archive that is Keras v3 formatted.
            # If the runtime is TF 2.15 / Keras 2.x, deserialization commonly fails with
            # errors mentioning batch_shape / DTypePolicy.
            tf_ver = getattr(tf, '__version__', '') or ''
            try:
                import keras as _keras
                keras_ver = getattr(_keras, '__version__', '') or ''
            except Exception:
                keras_ver = ''

            if (('batch_shape' in msg) or ('DTypePolicy' in msg)) and (tf_ver.startswith('2.15') or keras_ver.startswith('2.')):
                raise RuntimeError(
                    'Disease model format requires TensorFlow/Keras v3. '
                    'Upgrade to tensorflow>=2.16 and redeploy.'
                ) from e
            raise
        print("🚀 Model Loaded Successfully!")
    return model

# Load .env if available (python-dotenv optional)
# Use an explicit path so it works even when the process CWD differs (e.g., Render/Gunicorn).
try:
    from dotenv import load_dotenv
    _dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
    load_dotenv(dotenv_path=_dotenv_path, override=True)
except Exception:
    # If python-dotenv isn't installed, env vars must be set by the host.
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

def _normalize_lang_code(lang: str) -> str:
    s = (lang or '').strip()
    if not s:
        return 'en'
    s = s.replace('_', '-').lower()
    # Handle Accept-Language like: "ta-IN,ta;q=0.9,en;q=0.8"
    s = s.split(',')[0].split(';')[0].strip()
    s = s.split('-')[0].strip()
    if s in ('en', 'hi', 'ta', 'kn', 'ml'):
        return s
    return 'en'


def _requested_lang_code() -> str:
    return _normalize_lang_code(
        request.args.get('lang')
        or request.headers.get('Accept-Language')
        or ''
    )


def _localized_fallback_texts(lang_code: str) -> dict:
    lc = _normalize_lang_code(lang_code)
    # Keep these short; they are only used when we truly can't provide content.
    table = {
        'en': {
            'no_desc': 'No description available',
            'no_remedies': 'No remedies found.',
            'no_prevention': 'No prevention steps found.',
            'no_daily': 'No daily care tips available.',
        },
        'hi': {
            'no_desc': 'विवरण उपलब्ध नहीं है',
            'no_remedies': 'कोई उपचार उपलब्ध नहीं।',
            'no_prevention': 'कोई रोकथाम कदम उपलब्ध नहीं।',
            'no_daily': 'दैनिक देखभाल सुझाव उपलब्ध नहीं।',
        },
        'ta': {
            'no_desc': 'விளக்கம் கிடைக்கவில்லை',
            'no_remedies': 'சிகிச்சைகள் கிடைக்கவில்லை.',
            'no_prevention': 'காக்க நடவடிக்கைகள் கிடைக்கவில்லை.',
            'no_daily': 'தினசரி பராமரிப்பு குறிப்புகள் கிடைக்கவில்லை.',
        },
        'kn': {
            'no_desc': 'ವಿವರಣೆ ಲಭ್ಯವಿಲ್ಲ',
            'no_remedies': 'ಯಾವುದೇ ಚಿಕಿತ್ಸೆ ಲಭ್ಯವಿಲ್ಲ.',
            'no_prevention': 'ತಡೆ ಕ್ರಮಗಳು ಲಭ್ಯವಿಲ್ಲ.',
            'no_daily': 'ದೈನಂದಿನ ಆರೈಕೆ ಸಲಹೆಗಳು ಲಭ್ಯವಿಲ್ಲ.',
        },
        'ml': {
            'no_desc': 'വിവരണം ലഭ്യമല്ല',
            'no_remedies': 'ചികിത്സകൾ ലഭ്യമല്ല.',
            'no_prevention': 'പ്രതിരോധ നടപടികൾ ലഭ്യമല്ല.',
            'no_daily': 'ദൈനംദിന പരിപാലന നിർദ്ദേശങ്ങൾ ലഭ്യമല്ല.',
        },
    }
    return table.get(lc, table['en'])


def _is_placeholder_text(s: str) -> bool:
    if s is None:
        return True
    v = str(s).strip().lower()
    if not v:
        return True
    # Common placeholders (English) sometimes returned by the model or UI.
    placeholders = {
        'no description available',
        'no remedies found.',
        'no prevention steps found.',
        'no daily care tips available.',
    }
    return v in placeholders


def _gemini_fill_text_only_disease_info(
    disease: str,
    lang_code: str,
    existing: dict | None = None,
):
    """Ask Gemini (text-only) to fill missing disease info.

    Used as a fallback when the image response is incomplete or when
    the disease label is too generic for our built-in mapping.
    """
    cfg = _gemini_config()
    if not cfg.get('api_key'):
        return None

    disease_name = (disease or '').strip()
    if not disease_name:
        return None

    lc = _normalize_lang_code(lang_code)
    lang_names = {
        'en': 'English',
        'hi': 'Hindi',
        'ta': 'Tamil',
        'kn': 'Kannada',
        'ml': 'Malayalam',
    }
    target_lang = lang_names.get(lc, 'English')

    existing = existing or {}
    existing_json = {
        'disease': disease_name,
        'description': (existing.get('description') or ''),
        'remedies': existing.get('remedies') if isinstance(existing.get('remedies'), list) else [],
        'prevention': existing.get('prevention') if isinstance(existing.get('prevention'), list) else [],
        'daily_care': existing.get('daily_care') if isinstance(existing.get('daily_care'), list) else [],
    }

    prompt = (
        "You are an expert agricultural assistant. "
        f"Answer in {target_lang}. "
        "Return ONLY valid JSON with keys: description, remedies, prevention, daily_care. "
        "description must be a short sentence (not empty). "
        "remedies/prevention/daily_care must be arrays of short strings (1-5 items each). "
        "Do NOT return translation keys. "
        f"Disease: {disease_name}. "
        "If the disease name is generic, provide best-practice guidance for that disease. "
        "Here is any existing info (may be incomplete): "
        + json.dumps(existing_json, ensure_ascii=False)
    )

    payload_v1 = {
        'contents': [
            {
                'role': 'user',
                'parts': [{'text': prompt}]
            }
        ],
        'generationConfig': {
            'temperature': 0.2,
            'maxOutputTokens': 512
        }
    }
    payload_v2 = {
        'contents': [
            {
                'role': 'user',
                'parts': [{'text': prompt}]
            }
        ],
        'generation_config': {
            'temperature': 0.2,
            'max_output_tokens': 512
        }
    }

    try:
        model_name = _gemini_disease_model_name()
        fallbacks = _gemini_disease_model_fallbacks()
        r, used_url, tried_urls = _gemini_generate_content_request(
            api_base=cfg['api_base'],
            api_key=cfg['api_key'],
            model=model_name,
            fallback_models=fallbacks,
            payload_primary=payload_v1,
            payload_secondary=payload_v2,
            timeout=20,
        )
        if isinstance(r, Exception) or (getattr(r, 'status_code', 0) != 200):
            return None

        data = r.json() if r.content else {}
        text = ''
        try:
            cand0 = (data.get('candidates') or [])[0] if (data.get('candidates') or []) else {}
            parts = (((cand0.get('content') or {}).get('parts')) or [])
            if parts and isinstance(parts[0], dict):
                text = parts[0].get('text') or ''
        except Exception:
            text = ''

        parsed = _extract_json_from_text(text)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None

# ------------------
# MongoDB (Atlas) init
# ------------------
mongo_client = None
mongo_db = None
MONGODB_URI = os.environ.get('MONGODB_URI')
if MONGODB_URI and MongoClient is not None:
    try:
        # Use short timeouts so the app doesn't hang on startup/deploy if Mongo is unreachable.
        mongo_client = MongoClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=int(os.environ.get('MONGODB_SERVER_SELECTION_TIMEOUT_MS', '2000')),
            connectTimeoutMS=int(os.environ.get('MONGODB_CONNECT_TIMEOUT_MS', '2000')),
            socketTimeoutMS=int(os.environ.get('MONGODB_SOCKET_TIMEOUT_MS', '2000')),
        )
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

PRICE_COLLECTION = 'prices'
PRICE_META_DOC_ID = '__meta__'
PRICE_SCHEMA_VERSION = 2
INDIA_TZ = timezone(timedelta(hours=5, minutes=30))
MANDI_PRICE_LATEST_COLLECTION = 'mandi_prices_latest'
MANDI_PRICE_HISTORY_COLLECTION = 'mandi_prices_history'


def _ensure_price_indexes():
    if mongo_db is None:
        return
    try:
        coll = mongo_db.get_collection(PRICE_COLLECTION)
        coll.create_index('key', unique=True, sparse=True)
        coll.create_index('fetched_at')
        coll.create_index('last_scraped_at')
        coll.create_index('items_hash')
    except Exception as e:
        print('ensure price indexes error:', e)

    try:
        latest_coll = mongo_db.get_collection(MANDI_PRICE_LATEST_COLLECTION)
        history_coll = mongo_db.get_collection(MANDI_PRICE_HISTORY_COLLECTION)

        latest_coll.create_index('natural_key', unique=True)
        latest_coll.create_index('state')
        latest_coll.create_index('district')
        latest_coll.create_index('market')
        latest_coll.create_index('commodity')
        latest_coll.create_index('price_date')
        latest_coll.create_index('last_scraped_at')

        history_coll.create_index('history_key', unique=True)
        history_coll.create_index('natural_key')
        history_coll.create_index('price_date')
        history_coll.create_index('recorded_at')
    except Exception as e:
        print('ensure mandi history indexes error:', e)


_ensure_price_indexes()

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
    "fireblight": {
        "description": "Bacterial disease causing blackened, wilted shoots and blossoms that can look scorched (common in apple/pear).",
        "remedies": [
            "Prune infected shoots/branches 20–30 cm below visible damage and disinfect tools between cuts.",
            "Remove and destroy pruned infected material (do not compost if spread is a risk).",
            "Use recommended copper sprays during dormancy and follow local guidance for antibiotics where permitted."
        ],
        "prevention": [
            "Avoid excessive nitrogen fertilization that promotes tender growth.",
            "Prune to improve airflow; avoid pruning during wet conditions.",
            "Choose resistant varieties when available and monitor during bloom."
        ],
        "daily_care": [
            "Monitor new shoots and blossoms frequently during warm, humid periods.",
            "Remove any new infected tips early to reduce spread.",
            "Keep trees healthy with balanced watering and nutrition."
        ]
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
# Model is loaded on-demand via load_model_lazy().

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


PROFILE_FIELDS = ('name', 'phone', 'address', 'city', 'pincode')


def normalize_profile_payload(profile):
    if not isinstance(profile, dict):
        return {}

    cleaned = {}
    for field in PROFILE_FIELDS:
        value = profile.get(field)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            cleaned[field] = text
    return cleaned


def merge_user_profile(user_record, profile_updates):
    user = dict(user_record or {})
    merged = normalize_profile_payload(user.get('profile') or {})

    for field in PROFILE_FIELDS:
        if field not in merged:
            existing = user.get(field)
            if existing is not None:
                text = str(existing).strip()
                if text:
                    merged[field] = text

    for field, value in normalize_profile_payload(profile_updates).items():
        merged[field] = value

    if merged:
        user['profile'] = merged
        for field in PROFILE_FIELDS:
            if field in merged:
                user[field] = merged[field]
            else:
                user.pop(field, None)
    else:
        user.pop('profile', None)
        for field in PROFILE_FIELDS:
            user.pop(field, None)

    return user


def update_user_record(email: str, updater):
    users_data = load_users()
    users = users_data.setdefault('users', [])
    for index, user in enumerate(users):
        if user.get('email') == email:
            users[index] = updater(dict(user))
            save_users(users_data)
            return users[index]
    return None

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


def find_user_by_google_sub(google_sub: str):
    sub = (google_sub or '').strip()
    if not sub:
        return None

    try:
        if mongo_db is not None:
            coll = mongo_db.get_collection('users')
            doc = coll.find_one({'google_sub': sub}, {'_id': 0})
            if doc:
                return doc
    except Exception as e:
        print('find_user_by_google_sub -> mongo error:', e)

    users = load_users().get('users', [])
    for user in users:
        if (user.get('google_sub') or '').strip() == sub:
            return user
    return None


def firebase_public_config() -> dict:
    return {
        'apiKey': (os.environ.get('FIREBASE_API_KEY') or FIREBASE_PUBLIC_CONFIG_DEFAULTS['apiKey']).strip(),
        'authDomain': (os.environ.get('FIREBASE_AUTH_DOMAIN') or FIREBASE_PUBLIC_CONFIG_DEFAULTS['authDomain']).strip(),
        'projectId': (os.environ.get('FIREBASE_PROJECT_ID') or FIREBASE_PUBLIC_CONFIG_DEFAULTS['projectId']).strip(),
        'storageBucket': (os.environ.get('FIREBASE_STORAGE_BUCKET') or FIREBASE_PUBLIC_CONFIG_DEFAULTS['storageBucket']).strip(),
        'messagingSenderId': (os.environ.get('FIREBASE_MESSAGING_SENDER_ID') or FIREBASE_PUBLIC_CONFIG_DEFAULTS['messagingSenderId']).strip(),
        'appId': (os.environ.get('FIREBASE_APP_ID') or FIREBASE_PUBLIC_CONFIG_DEFAULTS['appId']).strip(),
        'measurementId': (os.environ.get('FIREBASE_MEASUREMENT_ID') or FIREBASE_PUBLIC_CONFIG_DEFAULTS['measurementId']).strip(),
    }


def firebase_project_id() -> str:
    return (firebase_public_config().get('projectId') or '').strip()


def upsert_google_user(email: str, google_claims: dict | None = None):
    claims = google_claims or {}
    clean_email = (email or '').strip()
    if not clean_email:
        return None

    profile_updates = {}
    full_name = (claims.get('name') or '').strip()
    if full_name:
        profile_updates['name'] = full_name

    existing_user = find_user(clean_email)
    google_sub = (claims.get('sub') or '').strip()

    if existing_user is None:
        new_user = merge_user_profile({'email': clean_email}, profile_updates)
        if google_sub:
            new_user['google_sub'] = google_sub
        new_user['auth_provider'] = 'google'
        users_data = load_users()
        users_data.setdefault('users', []).append(new_user)
        save_users(users_data)
        return new_user

    def updater(user):
        updated = merge_user_profile(user, profile_updates)
        if google_sub and not updated.get('google_sub'):
            updated['google_sub'] = google_sub
        updated['auth_provider'] = updated.get('auth_provider') or 'google'
        return updated

    return update_user_record(clean_email, updater)


# -------------------------
# Orders / persistence helpers
# -------------------------
def get_orders_collection():
    return mongo_db.get_collection('orders') if mongo_db is not None else None


def get_today_deals_collection():
    return mongo_db.get_collection('today_deals') if mongo_db is not None else None


def _normalize_icon_path(icon_value):
    text = str(icon_value or '').strip()
    if not text:
        return ''
    lowered = text.lower()
    if lowered.startswith(('http://', 'https://', 'data:')):
        return text
    if text.startswith('/icons/') or text.startswith('/api/'):
        return text
    return f"/icons/{text.lstrip('/')}"


def _sanitize_order_record(order, include_image=False):
    if not isinstance(order, dict):
        return order
    out = {k: v for k, v in order.items() if k != '_id'}
    if 'icon' in out:
        out['icon'] = _normalize_icon_path(out.get('icon'))
    if not include_image:
        out.pop('image_data', None)
        out.pop('image_mime', None)
    return out


def _listing_image_endpoint(listing_id) -> str:
    return f'/api/listing/{int(listing_id)}/image'


def get_order_by_id(order_id, include_image=False):
    try:
        oid = int(order_id)
    except Exception:
        return None

    try:
        coll = get_orders_collection()
        if coll is not None:
            projection = {'_id': 0} if include_image else {'_id': 0, 'image_data': 0, 'image_mime': 0}
            doc = coll.find_one({'id': oid}, projection)
            if doc:
                return _sanitize_order_record(doc, include_image=include_image)
    except Exception as e:
        print('get_order_by_id -> mongo error:', e)

    orders_file = os.path.join(os.path.dirname(__file__), 'data', 'orders.json')
    try:
        with open(orders_file, 'r', encoding='utf-8') as f:
            orders = json.load(f)
    except Exception:
        orders = []

    for order in orders:
        try:
            if int(order.get('id', 0)) == oid:
                return _sanitize_order_record(order, include_image=include_image)
        except Exception:
            continue
    return None


def _delete_listing_icon_assets(order):
    if not isinstance(order, dict):
        return
    icon = str(order.get('icon') or '').strip()
    if not icon.startswith('/icons/'):
        return
    try:
        filename = os.path.basename(icon)
        if not filename:
            return
        path = os.path.join(os.path.dirname(__file__), 'static', 'icons', filename)
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        print('delete listing icon asset error:', e)


def _apply_terminal_listing_state(order_id, *, status=None):
    order = get_order_by_id(order_id, include_image=True)
    if not order or (order.get('type') or 'sell').lower() != 'sell':
        return False
    updates = {}
    unset_fields = ['image_data', 'image_mime']
    if status:
        updates['status'] = status
    if str(order.get('icon') or '').startswith(_listing_image_endpoint(order_id)):
        unset_fields.append('icon')
    ok = update_order_by_id(order_id, updates, unset_fields=unset_fields)
    _delete_listing_icon_assets(order)
    return ok

def read_orders():
    # Return list of orders from Mongo or fallback file
    try:
        coll = get_orders_collection()
        if coll is not None:
            docs = list(coll.find({}, {'_id': 0, 'image_data': 0, 'image_mime': 0}))
            return [_sanitize_order_record(doc) for doc in docs]
    except Exception as e:
        print('read_orders -> mongo error:', e)

    orders_file = os.path.join(os.path.dirname(__file__), 'data', 'orders.json')
    try:
        with open(orders_file, 'r', encoding='utf-8') as f:
            return [_sanitize_order_record(order) for order in json.load(f)]
    except Exception:
        return []


def read_today_deals():
    """Read admin-marked today's deals IDs from data/today_deals.json (list of ids).
       Returns list of ints.
    """
    # Prefer MongoDB on hosted deployments (Render filesystem is ephemeral)
    try:
        coll = get_today_deals_collection()
        if coll is not None:
            doc = coll.find_one({'_id': 'today_deals'}, {'_id': 0})
            ids = (doc or {}).get('ids')
            if isinstance(ids, list):
                return [int(x) for x in ids]
    except Exception as e:
        print('read_today_deals -> mongo error:', e)

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
    # Prefer MongoDB on hosted deployments (Render filesystem is ephemeral)
    try:
        coll = get_today_deals_collection()
        if coll is not None:
            ids = [int(x) for x in (id_list or [])]
            coll.replace_one(
                {'_id': 'today_deals'},
                {'_id': 'today_deals', 'ids': ids, 'updated_at': datetime.utcnow().isoformat() + 'Z'},
                upsert=True
            )
            return True
    except Exception as e:
        print('save_today_deals -> mongo error:', e)

    fn = os.path.join(os.path.dirname(__file__), 'data', 'today_deals.json')
    try:
        with open(fn, 'w', encoding='utf-8') as f:
            json.dump([int(x) for x in (id_list or [])], f, indent=2)
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
    order = get_order_by_id(order_id, include_image=True)
    try:
        coll = get_orders_collection()
        if coll is not None:
            coll.delete_one({'id': order_id})
            _delete_listing_icon_assets(order)
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
    _delete_listing_icon_assets(order)
    return True

def update_order_by_id(order_id, updates: dict, unset_fields=None):
    unset_fields = [field for field in (unset_fields or []) if field]
    try:
        coll = get_orders_collection()
        if coll is not None:
            # only set provided fields
            set_doc = {k: v for k, v in updates.items()}
            ops = {}
            if set_doc:
                ops['$set'] = set_doc
            if unset_fields:
                ops['$unset'] = {field: '' for field in unset_fields}
            res = coll.update_one({'id': order_id}, ops)
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
            for field in unset_fields:
                o.pop(field, None)
            changed = True
            break
    if changed:
        with open(orders_file, 'w', encoding='utf-8') as f:
            json.dump(orders, f, indent=2)
    return changed

import smtplib
from email.mime.text import MIMEText
import os
import requests


def _email_escape(value) -> str:
    return html.escape('' if value is None else str(value))


def _email_format_currency(value) -> str:
    if value is None or value == '':
        return 'Not available'
    try:
        amount = float(value)
        if amount.is_integer():
            return f'Rs {int(amount)}'
        return f'Rs {amount:.2f}'
    except Exception:
        return str(value)


def _email_format_quantity(value) -> str:
    if value is None or value == '':
        return 'Not available'
    try:
        quantity = float(value)
        if quantity.is_integer():
            return f'{int(quantity)} kg'
        return f'{quantity:.2f} kg'
    except Exception:
        return str(value)


def _email_format_timestamp(value) -> str:
    if value is None or value == '':
        return 'Not available'
    try:
        return datetime.fromtimestamp(float(value)).strftime('%d %b %Y, %I:%M %p')
    except Exception:
        return str(value)


def _normalize_email_address(value) -> str | None:
    if value is None:
        return None
    email = str(value).strip()
    if not email or '@' not in email or ' ' in email or '@…' in email:
        return None
    return email


def _resolve_notification_email(record, *preferred_fields) -> str | None:
    if isinstance(record, str):
        return _normalize_email_address(record)
    if not isinstance(record, dict):
        return None

    fields = list(preferred_fields or [])
    fields.extend(['user', 'buyer_email', 'seller_email', 'contact', 'email', 'seller'])

    seen = set()
    for field in fields:
        if field in seen:
            continue
        seen.add(field)
        email = _normalize_email_address(record.get(field))
        if email:
            return email
    return None


def _build_rich_email_content(title: str, message: str, details=None, badge: str = '', accent: str = 'green'):
    palette = {
        'green': {'solid': '#10b981', 'soft': '#ecfdf5', 'dark': '#064e3b'},
        'blue': {'solid': '#3b82f6', 'soft': '#eff6ff', 'dark': '#1e3a8a'},
        'amber': {'solid': '#f59e0b', 'soft': '#fffbeb', 'dark': '#92400e'},
        'red': {'solid': '#ef4444', 'soft': '#fef2f2', 'dark': '#991b1b'},
    }
    colors = palette.get((accent or 'green').lower(), palette['green'])
    detail_rows = []
    for label, value in (details or []):
        if value is None or value == '':
            continue
        detail_rows.append(
            f"""
            <tr>
              <td style=\"padding:10px 12px;border-bottom:1px solid #e2e8f0;color:#64748b;font-size:13px;font-weight:600;width:34%\">{_email_escape(label)}</td>
              <td style=\"padding:10px 12px;border-bottom:1px solid #e2e8f0;color:#0f172a;font-size:13px\">{_email_escape(value)}</td>
            </tr>
            """
        )
    details_html = ''
    if detail_rows:
        details_html = (
            "<div style=\"margin-top:24px;background:#ffffff;border:1px solid #e2e8f0;border-radius:18px;overflow:hidden\">"
            "<div style=\"padding:14px 18px;background:#f8fafc;color:#0f172a;font-size:14px;font-weight:700\">Details</div>"
            "<table role=\"presentation\" cellspacing=\"0\" cellpadding=\"0\" style=\"width:100%;border-collapse:collapse\">"
            + ''.join(detail_rows) +
            "</table></div>"
        )
    badge_html = ''
    if badge:
        badge_html = f"<div style=\"display:inline-block;padding:8px 14px;border-radius:999px;background:{colors['soft']};color:{colors['dark']};font-size:12px;font-weight:800;letter-spacing:.06em;text-transform:uppercase\">{_email_escape(badge)}</div>"

    html_body = f"""<!DOCTYPE html>
<html>
  <body style=\"margin:0;padding:0;background:#e2e8f0;font-family:Arial,sans-serif;color:#0f172a\">
    <div style=\"padding:28px 12px\">
      <div style=\"max-width:640px;margin:0 auto;background:linear-gradient(135deg,#0f172a 0%,#1e293b 65%,{colors['dark']} 100%);border-radius:28px;overflow:hidden;box-shadow:0 18px 48px rgba(15,23,42,.28)\">
        <div style=\"padding:34px 32px 26px;color:#ffffff\">
          <div style=\"font-size:14px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#cbd5e1;margin-bottom:14px\">AgriAI360</div>
          {badge_html}
          <h1 style=\"margin:18px 0 10px;font-size:30px;line-height:1.2\">{_email_escape(title)}</h1>
          <p style=\"margin:0;color:#e2e8f0;font-size:15px;line-height:1.7\">{_email_escape(message)}</p>
        </div>
        <div style=\"background:#f8fafc;padding:28px 26px 30px\">
          <div style=\"background:linear-gradient(135deg,#ffffff 0%,{colors['soft']} 100%);border:1px solid rgba(148,163,184,.22);border-radius:22px;padding:20px 22px\">
            <div style=\"font-size:15px;font-weight:700;color:{colors['dark']};margin-bottom:6px\">Status Update</div>
            <div style=\"font-size:13px;line-height:1.7;color:#334155\">Please review the latest information below.</div>
            {details_html}
          </div>
          <div style=\"margin-top:22px;font-size:12px;line-height:1.7;color:#64748b\">This is an automated AgriAI360 notification about your marketplace activity.</div>
        </div>
      </div>
    </div>
  </body>
</html>"""

    text_lines = [title, '', message]
    if details:
        text_lines.extend(['', 'Details:'])
        for label, value in details:
            if value is None or value == '':
                continue
            text_lines.append(f'- {label}: {value}')
    text_lines.extend(['', 'AgriAI360'])
    return {'text': '\n'.join(text_lines), 'html': html_body}


def _smtp_is_configured() -> bool:
    sender_email = (os.getenv("EMAIL_USER") or "").strip()
    app_password = (os.getenv("EMAIL_PASS") or "").strip().replace(" ", "")
    return bool(sender_email and app_password)


def _brevo_is_configured() -> bool:
    api_key = (os.getenv('BREVO_API_KEY') or '').strip()
    from_email = (os.getenv('BREVO_FROM') or '').strip()
    return bool(api_key and from_email)


def _email_provider() -> str:
    return (os.getenv('EMAIL_PROVIDER') or 'auto').strip().lower()


def _resolve_email_provider() -> str:
    configured = []
    if _brevo_is_configured():
        configured.append('brevo')
    if _smtp_is_configured():
        configured.append('smtp')

    provider = _email_provider()
    if provider in ('smtp', 'brevo'):
        return provider if provider in configured else ''

    # In auto mode choose one provider only. Prefer Brevo because it is the
    # currently used branded transactional sender for this app.
    if 'brevo' in configured:
        return 'brevo'
    if 'smtp' in configured:
        return 'smtp'
    return ''


def _email_hint_for_provider(provider: str) -> str:
    p = (provider or '').strip().lower() or 'auto'
    if p == 'smtp':
        return 'Set EMAIL_USER (Gmail) and EMAIL_PASS (Gmail App Password).'
    if p == 'brevo':
        return 'Set BREVO_API_KEY and BREVO_FROM (verified sender) in environment.'
    return 'Configure at least one provider: SMTP (EMAIL_USER/EMAIL_PASS) or Brevo (BREVO_API_KEY/BREVO_FROM).'


def _email_is_configured() -> bool:
    return bool(_resolve_email_provider())


def _smtp_timeout_seconds() -> float:
    try:
        v = float(os.getenv('SMTP_TIMEOUT', '8').strip())
        return 2.0 if v < 2 else v
    except Exception:
        return 8.0


def _send_otp_smtp(receiver_email: str, otp: str) -> bool:
    """Send OTP via Gmail SMTP (TLS 587) using an App Password."""
    sender_email = (os.getenv("EMAIL_USER") or "").strip()
    app_password = (os.getenv("EMAIL_PASS") or "").strip().replace(" ", "")
    if not sender_email or not app_password:
        raise RuntimeError("SMTP not configured: set EMAIL_USER and EMAIL_PASS")

    otp_email = _build_rich_email_content(
        'OTP Verification',
        'Use the one-time password below to continue your AgriAI360 sign in or registration.',
        details=[
            ('OTP Code', otp),
            ('Valid For', '10 minutes'),
            ('Email', receiver_email),
        ],
        badge='Secure Access',
        accent='blue',
    )
    msg = MIMEMultipart('alternative')
    msg.attach(MIMEText(otp_email['text'], 'plain'))
    msg.attach(MIMEText(otp_email['html'], 'html'))
    msg["Subject"] = "OTP Verification"
    msg["From"] = sender_email
    msg["To"] = receiver_email

    timeout = _smtp_timeout_seconds()
    server = smtplib.SMTP("smtp.gmail.com", 587, timeout=timeout)
    try:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(sender_email, app_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
    finally:
        try:
            server.quit()
        except Exception:
            pass

    return True


def _http_timeout_seconds() -> float:
    """Timeout for HTTP email APIs (Brevo/Resend)."""
    try:
        v = float(os.getenv('EMAIL_HTTP_TIMEOUT', os.getenv('SMTP_TIMEOUT', '8')).strip())
        return 2.0 if v < 2 else v
    except Exception:
        return 8.0


def _send_otp_brevo(receiver_email: str, otp: str) -> bool:
    """Send OTP using Brevo Transactional Email API."""
    api_key = (os.getenv('BREVO_API_KEY') or '').strip()
    from_email = (os.getenv('BREVO_FROM') or '').strip()
    sender_name = (os.getenv('BREVO_SENDER_NAME') or 'AgriAI360').strip() or 'AgriAI360'
    if not api_key or not from_email:
        raise RuntimeError('Brevo not configured: set BREVO_API_KEY and BREVO_FROM')

    # Log high-level intent only (do not log OTP).
    print(f"[OTP][brevo] sending to={receiver_email} from={from_email}")

    payload = {
        'sender': {
            'email': from_email,
            'name': sender_name,
        },
        'to': [
            {'email': receiver_email},
        ],
        'subject': 'OTP Verification',
        'textContent': _build_rich_email_content(
            'OTP Verification',
            'Use the one-time password below to continue your AgriAI360 sign in or registration.',
            details=[
                ('OTP Code', otp),
                ('Valid For', '10 minutes'),
                ('Email', receiver_email),
            ],
            badge='Secure Access',
            accent='blue',
        )['text'],
        'htmlContent': _build_rich_email_content(
            'OTP Verification',
            'Use the one-time password below to continue your AgriAI360 sign in or registration.',
            details=[
                ('OTP Code', otp),
                ('Valid For', '10 minutes'),
                ('Email', receiver_email),
            ],
            badge='Secure Access',
            accent='blue',
        )['html'],
    }

    headers = {
        'accept': 'application/json',
        'content-type': 'application/json',
        'api-key': api_key,
    }

    timeout = _http_timeout_seconds()
    resp = requests.post('https://api.brevo.com/v3/smtp/email', json=payload, headers=headers, timeout=timeout)
    if resp.status_code in (200, 201, 202):
        print(f"[OTP][brevo] success status={resp.status_code}")
        return True

    # Log response body for debugging on server logs only.
    try:
        body = (resp.text or '')
        body = body[:8000]  # cap to keep logs sane
    except Exception:
        body = ''
    print(f"[OTP][brevo] failed status={resp.status_code} body={body}")
    raise RuntimeError(f'Brevo send failed (HTTP {resp.status_code})')


def send_otp(receiver_email, otp):
    """Send OTP using configured provider.

    Providers:
      - smtp: Gmail SMTP (TLS 587)
      - brevo: Brevo Transactional Email API
            - auto: choose one configured provider only
    """
    provider = _resolve_email_provider()
    if provider == 'smtp':
        return _send_otp_smtp(receiver_email, otp)
    if provider == 'brevo':
        return _send_otp_brevo(receiver_email, otp)

    raise RuntimeError('No email provider configured. Set EMAIL_PROVIDER and credentials.')


def send_otp_email(email, otp):
    # Backward-compatible wrapper used by existing OTP routes.
    return send_otp(email, otp)


def send_otp_email_async(email, otp):
    """Send OTP in a background thread so HTTP responds quickly."""

    # Fail fast if nothing is configured.
    if not _email_is_configured():
        raise RuntimeError('Email not configured: set EMAIL_USER and EMAIL_PASS')

    def _runner():
        try:
            send_otp_email(email, otp)
        except Exception as e:
            print(f"[OTP] Email send failed for {email}: {e}")

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    return True


def _send_notification_email(to_email: str, subject: str, body: str, html_body: str = None):
    """Send a generic notification email (non-OTP) using configured provider."""
    if not _email_is_configured():
        print('[NOTIFY] Email not configured, skipping notification')
        return

    provider = _resolve_email_provider()

    def _send():
        try:
            if provider == 'brevo':
                api_key = (os.getenv('BREVO_API_KEY') or '').strip()
                from_email = (os.getenv('BREVO_FROM') or '').strip()
                sender_name = (os.getenv('BREVO_SENDER_NAME') or 'AgriAI360').strip() or 'AgriAI360'
                payload = {
                    'sender': {'email': from_email, 'name': sender_name},
                    'to': [{'email': to_email}],
                    'subject': subject,
                    'textContent': body,
                }
                if html_body:
                    payload['htmlContent'] = html_body
                headers = {
                    'accept': 'application/json',
                    'content-type': 'application/json',
                    'api-key': api_key,
                }
                resp = requests.post('https://api.brevo.com/v3/smtp/email', json=payload, headers=headers, timeout=_http_timeout_seconds())
                if resp.status_code in (200, 201, 202):
                    print(f'[NOTIFY] Brevo email sent to {to_email}')
                else:
                    print(f'[NOTIFY] Brevo failed status={resp.status_code}')
            elif provider == 'smtp':
                sender_email = (os.getenv("EMAIL_USER") or "").strip()
                app_password = (os.getenv("EMAIL_PASS") or "").strip().replace(" ", "")
                if html_body:
                    msg = MIMEMultipart('alternative')
                    msg.attach(MIMEText(body, 'plain'))
                    msg.attach(MIMEText(html_body, 'html'))
                else:
                    msg = MIMEText(body)
                msg["Subject"] = subject
                msg["From"] = sender_email
                msg["To"] = to_email
                server = smtplib.SMTP("smtp.gmail.com", 587, timeout=_smtp_timeout_seconds())
                try:
                    server.ehlo(); server.starttls(); server.ehlo()
                    server.login(sender_email, app_password)
                    server.sendmail(sender_email, to_email, msg.as_string())
                finally:
                    try: server.quit()
                    except Exception: pass
                print(f'[NOTIFY] SMTP email sent to {to_email}')
        except Exception as e:
            print(f'[NOTIFY] Email send failed for {to_email}: {e}')

    t = threading.Thread(target=_send, daemon=True)
    t.start()


def _send_email_now_or_async(email: str, otp: str):
    """Send OTP either synchronously (default) or asynchronously.

    Synchronous mode makes it much easier to detect delivery/config errors.
    Set EMAIL_SEND_ASYNC=1 to switch to background-thread delivery.
    """
    async_enabled = str(os.environ.get('EMAIL_SEND_ASYNC', '0')).lower() in ('1', 'true', 'yes')
    if async_enabled:
        return send_otp_email_async(email, otp)
    return send_otp_email(email, otp)


@app.route("/auth/request_otp", methods=["POST"])
def request_otp():
    try:
        data = request.get_json()
        email = data.get("email")

        if not email:
            return jsonify({"success": False, "message": "Email required"}), 400

        if not _email_is_configured():
            provider = _email_provider()
            return jsonify({
                "success": False,
                "message": "Email not configured on server",
                "hint": _email_hint_for_provider(provider)
            }), 500

        otp = str(random.randint(100000, 999999))

        # store otp in session
        session["otp"] = otp
        session["otp_email"] = email
        session["otp_expires_at"] = time.time() + 120

        try:
            _send_email_now_or_async(email, otp)
            return jsonify({"success": True, "message": "OTP sent to email"})
        except Exception as e:
            # Do not leak sensitive details; give actionable hint.
            print(f"[OTP] send failed for {email}: {e}")
            provider = _email_provider()
            if provider == 'brevo':
                return jsonify({
                    "success": False,
                    "message": "Brevo OTP email failed",
                    "hint": "Check BREVO_API_KEY, BREVO_FROM (verified sender), and Render outbound HTTPS access. See server logs for Brevo response."
                }), 502

            return jsonify({
                "success": False,
                "message": "Failed to send OTP email",
                "hint": "Set EMAIL_PROVIDER=brevo and configure BREVO_API_KEY/BREVO_FROM. Check server logs for details."
            }), 502

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/auth/verify_otp", methods=["POST"])
def verify_otp():
    data = request.get_json()
    user_otp = data.get("otp")

    if "otp" not in session or "otp_email" not in session:
        return {"success": False, "message": "OTP not generated"}

    # expiry check
    try:
        exp = session.get('otp_expires_at')
        if exp and time.time() > float(exp):
            # clear expired OTP
            session.pop('otp', None)
            session.pop('otp_email', None)
            session.pop('otp_expires_at', None)
            return {"success": False, "message": "OTP expired"}
    except Exception:
        pass

    # OTP stored as string → compare string
    if user_otp != session["otp"]:
        return {"success": False, "message": "Invalid OTP"}

    email = session.get("otp_email")  # FIXED ⬅ correct source
    register_password_hash = session.pop('register_password_hash', None)
    register_profile = normalize_profile_payload(session.pop('register_profile', {}) or {})
    session.pop('register_email', None)
    # one-time use
    session.pop('otp', None)
    session.pop('otp_email', None)
    session.pop('otp_expires_at', None)
    users = load_users()

    # ADMIN LOGIN
    if email.lower() in ADMIN_EMAILS:
        session["admin"] = True
        session["user"] = email
        return {"success": True, "role": "admin", "redirect": "/admin/dashboard"}

    # NORMAL LOGIN
    existing_user = next((u for u in users.get("users", []) if u.get("email") == email), None)
    if existing_user is None:
        new_user = {'email': email}
        if register_password_hash:
            new_user['password'] = register_password_hash
        new_user = merge_user_profile(new_user, register_profile)
        users.setdefault("users", []).append(new_user)
        save_users(users)
    elif register_profile:
        update_user_record(email, lambda user: merge_user_profile(user, register_profile))

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
    if not session.get('admin'):
        return {"success": False, "message": "Not authorized"}, 403

    data = request.json or {}
    email = data.get("email")
    if not email:
        return {"success": False, "message": "email required"}, 400

    test_otp = random.randint(100000, 999999)
    try:
        send_otp_email(email, str(test_otp))
        return {"success": True, "message": f"Test email sent to {email}"}
    except Exception as e:
        return {"success": False, "message": str(e)}, 500
@app.route("/test_email")
def test_email():
    if os.environ.get('ENABLE_TEST_EMAIL') not in ('1', 'true', 'True', 'yes'):
        return "Not found", 404
    send_otp_email(os.environ.get('TEST_EMAIL_TO') or "test@example.com", "999999")
    return "Test email queued"



@app.route("/auth/register", methods=["POST"])
def register():
    data = request.json or {}
    email = data.get("email")
    password = data.get("password")
    profile = normalize_profile_payload(data.get('profile') or {})
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
    session['register_profile'] = profile

    if not _email_is_configured():
        provider = _email_provider()
        return {"success": False, "message": "Email not configured on server"}, 500

    otp = str(random.randint(100000, 999999))
    session["otp"] = otp
    session["otp_email"] = email
    session["otp_expires_at"] = time.time() + 120

    try:
        _send_email_now_or_async(email, otp)
        return {"success": True, "message": "OTP sent for registration"}
    except Exception as e:
        print(f"[OTP] send failed for {email} (register): {e}")
        return {"success": False, "message": "Failed to send OTP email"}, 502


@app.route('/auth/google/config')
def auth_google_config():
    firebase_cfg = firebase_public_config()
    return jsonify({
        'success': True,
        'enabled': bool(
            firebase_cfg.get('apiKey')
            and firebase_cfg.get('authDomain')
            and firebase_cfg.get('projectId')
            and firebase_cfg.get('appId')
            and google_id_token
            and google_auth_requests
        ),
        'firebase': firebase_cfg,
    })


@app.route('/auth/google', methods=['POST'])
def auth_google():
    if google_id_token is None or google_auth_requests is None:
        return {'success': False, 'message': 'Google auth dependency is not installed on the server'}, 500

    data = request.get_json() or {}
    firebase_token = (data.get('firebase_token') or '').strip()
    credential = (data.get('credential') or '').strip()
    mode = (data.get('mode') or 'login').strip().lower()
    if mode not in ('login', 'signup'):
        mode = 'login'
    if not firebase_token and not credential:
        return {'success': False, 'message': 'Google credential is required'}, 400

    request_adapter = google_auth_requests.Request()
    token_info = None

    if firebase_token:
        project_id = firebase_project_id()
        if not project_id:
            return {'success': False, 'message': 'Firebase project is not configured on the server'}, 503
        try:
            token_info = google_id_token.verify_firebase_token(
                firebase_token,
                request_adapter,
                project_id,
            )
        except Exception as exc:
            print(f'[firebase-auth] token verification failed: {exc}')
            return {'success': False, 'message': 'Firebase Google sign up failed. Please try again.'}, 401

        issuer = (token_info.get('iss') or '').strip()
        expected_issuer = f'https://securetoken.google.com/{project_id}'
        if issuer != expected_issuer or (token_info.get('aud') or '').strip() != project_id:
            return {'success': False, 'message': 'Invalid Firebase token issuer'}, 401
    else:
        firebase_cfg = firebase_public_config()
        client_id = (data.get('client_id') or '').strip() or firebase_cfg.get('appId') or ''
        try:
            token_info = google_id_token.verify_oauth2_token(
                credential,
                request_adapter,
                client_id,
            )
        except Exception as exc:
            print(f'[google-auth] token verification failed: {exc}')
            return {'success': False, 'message': 'Google sign up failed. Please try again.'}, 401

        issuer = (token_info.get('iss') or '').strip()
        if issuer not in ('accounts.google.com', 'https://accounts.google.com'):
            return {'success': False, 'message': 'Invalid Google token issuer'}, 401

    email = (token_info.get('email') or '').strip().lower()
    google_sub = (token_info.get('sub') or '').strip()
    if not email:
        return {'success': False, 'message': 'Google account email is unavailable'}, 400
    if not token_info.get('email_verified'):
        return {'success': False, 'message': 'Google account email is not verified'}, 400

    if mode == 'signup':
        existing_user = find_user(email) or find_user_by_google_sub(google_sub)
        if existing_user:
            return {'success': False, 'message': 'User already exists. Please sign in.'}, 409

    user = upsert_google_user(email, token_info)
    if user is None:
        return {'success': False, 'message': 'Unable to create your account'}, 500

    if email.lower() in ADMIN_EMAILS:
        session['admin'] = True
        session['user'] = email
        return {'success': True, 'role': 'admin', 'redirect': '/admin/dashboard'}

    session['user'] = email
    session.pop('admin', None)
    return {'success': True, 'role': 'user', 'redirect': '/home'}


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

    # Password OK — log in directly (no OTP 2FA)
    # Check for admin
    if email.lower() in ADMIN_EMAILS:
        session["admin"] = True
        session["user"] = email
        return {"success": True, "role": "admin", "redirect": "/admin/dashboard"}

    session["user"] = email
    return {"success": True, "role": "user", "redirect": "/home"}


@app.route("/auth/forgot_password", methods=["POST"])
def forgot_password():
    """Send OTP for password reset."""
    data = request.json or {}
    email = data.get("email")
    if not email:
        return {"success": False, "message": "email required"}, 400

    u = find_user(email)
    if not u:
        return {"success": False, "message": "No account found with that email"}, 404

    if not _email_is_configured():
        return {"success": False, "message": "Email not configured on server"}, 500

    otp = str(random.randint(100000, 999999))
    session["otp"] = otp
    session["otp_email"] = email
    session["otp_expires_at"] = time.time() + 120
    session["forgot_password"] = True

    try:
        _send_email_now_or_async(email, otp)
        return {"success": True, "message": "OTP sent to your email"}
    except Exception as e:
        print(f"[OTP] send failed for {email} (forgot): {e}")
        return {"success": False, "message": "Failed to send OTP email"}, 502


@app.route("/auth/reset_password", methods=["POST"])
def reset_password():
    """Verify OTP and set a new password."""
    data = request.json or {}
    user_otp = data.get("otp")
    new_password = data.get("new_password")

    if not user_otp or not new_password:
        return {"success": False, "message": "OTP and new password required"}, 400

    if "otp" not in session or "otp_email" not in session:
        return {"success": False, "message": "OTP not generated"}, 400

    # expiry check
    try:
        exp = session.get('otp_expires_at')
        if exp and time.time() > float(exp):
            session.pop('otp', None)
            session.pop('otp_email', None)
            session.pop('otp_expires_at', None)
            return {"success": False, "message": "OTP expired"}
    except Exception:
        pass

    if user_otp != session["otp"]:
        return {"success": False, "message": "Invalid OTP"}

    email = session.get("otp_email")
    session.pop('otp', None)
    session.pop('otp_email', None)
    session.pop('otp_expires_at', None)
    session.pop('forgot_password', None)

    # Update user's password
    users = load_users()
    for u in users.get("users", []):
        if u.get("email") == email:
            u["password"] = hash_password(new_password)
            break
    save_users(users)

    return {"success": True, "message": "Password reset successfully"}


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

    order_type = (data.get('type') or '').lower()
    requested_quantity = data.get('quantity')
    try:
        requested_quantity_num = float(requested_quantity)
    except Exception:
        requested_quantity_num = None
    if requested_quantity_num is None or requested_quantity_num <= 0:
        return jsonify({'success': False, 'message': 'Quantity must be greater than zero'}), 400

    target_listing = None
    listing_id_value = None
    seller_email = None

    if order_type == 'buy':
        listing_id = data.get('listing_id')
        if listing_id is not None:
            try:
                listing_id_value = int(listing_id)
                target_listing = get_order_by_id(listing_id_value, include_image=False)
            except Exception:
                target_listing = None
                listing_id_value = None
            if not target_listing or (target_listing.get('type') or 'sell').lower() != 'sell':
                return jsonify({'success': False, 'message': 'Listing not found'}), 404
            if (target_listing.get('status') or '').lower() != 'approved':
                return jsonify({'success': False, 'message': 'This listing is not currently available'}), 400
            seller_email = _resolve_notification_email(target_listing, 'user', 'contact', 'email')
            try:
                available_quantity_num = float(target_listing.get('quantity'))
            except Exception:
                available_quantity_num = None
            if available_quantity_num is not None and requested_quantity_num > available_quantity_num:
                available_label = int(available_quantity_num) if float(available_quantity_num).is_integer() else round(available_quantity_num, 2)
                return jsonify({'success': False, 'message': f'Only {available_label} kg is available for this product'}), 400

    order = {
        'id': int(time.time() * 1000),
        'user': session.get('user'),
        'type': data['type'],  # 'buy' or 'sell'
        'product': data['product'],
        'quantity': data['quantity'],
        'price': data['price'],
        'timestamp': time.time()
    }
    if listing_id_value is not None:
        order['listing_id'] = listing_id_value
    if target_listing:
        order['seller'] = target_listing.get('user') or data.get('seller')
    elif data.get('seller'):
        order['seller'] = data.get('seller')
    if seller_email:
        order['seller_email'] = seller_email

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
                                    _apply_terminal_listing_state(target.get('id'), status='completed')
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

        email_order = saved if isinstance(saved, dict) else order
        if (email_order.get('type') or '').lower() == 'buy':
            buyer_email = _resolve_notification_email(email_order, 'user', 'buyer_email')
            seller_notification_email = seller_email or _resolve_notification_email(email_order, 'seller_email', 'seller')
            buyer_content = _build_rich_email_content(
                'Buy Order Confirmed',
                'Your purchase request has been recorded successfully. We will use the order details below for the next step in fulfilment.',
                details=[
                    ('Product', email_order.get('product') or 'Order item'),
                    ('Order ID', email_order.get('id')),
                    ('Listing ID', email_order.get('listing_id') or 'Not linked'),
                    ('Quantity', _email_format_quantity(email_order.get('quantity'))),
                    ('Price', _email_format_currency(email_order.get('price'))),
                    ('Seller', email_order.get('seller') or 'Marketplace seller'),
                    ('Placed At', _email_format_timestamp(email_order.get('timestamp'))),
                ],
                badge='Buy Confirmed',
                accent='blue',
            )
            if buyer_email:
                _send_notification_email(
                    buyer_email,
                    'AgriAI360 - Buy Order Confirmation',
                    buyer_content['text'],
                    html_body=buyer_content['html'],
                )

            if seller_notification_email and seller_notification_email != buyer_email:
                seller_content = _build_rich_email_content(
                    'New Buy Request',
                    'A buyer has placed an order for your marketplace listing. Review the order details below.',
                    details=[
                        ('Product', email_order.get('product') or 'Your listing'),
                        ('Order ID', email_order.get('id')),
                        ('Listing ID', email_order.get('listing_id') or 'Not linked'),
                        ('Quantity', _email_format_quantity(email_order.get('quantity'))),
                        ('Price', _email_format_currency(email_order.get('price'))),
                        ('Buyer', email_order.get('user') or 'Registered buyer'),
                        ('Placed At', _email_format_timestamp(email_order.get('timestamp'))),
                    ],
                    badge='New Order',
                    accent='amber',
                )
                _send_notification_email(
                    seller_notification_email,
                    'AgriAI360 - New Buy Order Received',
                    seller_content['text'],
                    html_body=seller_content['html'],
                )

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
        image_bytes = None
        image_mime = None
        if request.files and 'image' in request.files:
            form = request.form
            product = (form.get('product') or '').strip()
            quantity = form.get('quantity')
            price = form.get('price')
            location = form.get('location')
            notes = form.get('notes')
            contact = form.get('contact') or form.get('seller') or form.get('seller_contact_email')

            image_file = request.files.get('image')
            try:
                image_bytes = image_file.read() if image_file is not None else None
                image_mime = (getattr(image_file, 'mimetype', None) or 'image/png').strip() or 'image/png'
                if image_bytes and mongo_db is None:
                    slug = re.sub(r"\s+", "-", (product or 'market').strip().lower())
                    slug = slug.replace('/', '').replace('\\', '')
                    fname = f"{slug}.png"
                    icons_dir = os.path.join(os.path.dirname(__file__), 'static', 'icons')
                    os.makedirs(icons_dir, exist_ok=True)
                    save_path = os.path.join(icons_dir, fname)
                    with open(save_path, 'wb') as fh:
                        fh.write(image_bytes)
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
            contact = data.get('contact') or data.get('seller') or data.get('seller_contact_email')

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
            'status': 'pending',
            'timestamp': time.time()
        }
        if contact:
            listing['contact'] = contact

        if image_bytes and mongo_db is not None:
            listing['image_data'] = base64.b64encode(image_bytes).decode('ascii')
            listing['image_mime'] = image_mime or 'image/png'
            listing['icon'] = _listing_image_endpoint(new_id)
        elif image_filename:
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

    # Exclude listings pending admin approval from public marketplace
    try:
        filtered = [o for o in filtered if (o.get('status') or '').lower() == 'approved']
    except Exception:
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


@app.route('/api/listing/<int:listing_id>/image', methods=['GET'])
def api_listing_image(listing_id):
    listing = get_order_by_id(listing_id, include_image=True)
    if not listing:
        return 'Not found', 404

    image_data = listing.get('image_data')
    image_mime = (listing.get('image_mime') or 'image/png').strip() or 'image/png'
    if not image_data:
        return 'Not found', 404

    try:
        raw = base64.b64decode(image_data)
    except Exception:
        return 'Invalid image', 500

    resp = make_response(raw)
    resp.headers['Content-Type'] = image_mime
    resp.headers['Cache-Control'] = 'public, max-age=3600'
    return resp


@app.route('/api/order/<int:order_id>/price-change-request', methods=['POST'])
@login_required
def api_request_price_change(order_id):
    order = get_order_by_id(order_id, include_image=True)
    if not order:
        return jsonify({'success': False, 'message': 'Listing not found'}), 404

    current_user = session.get('user')
    if (order.get('user') or '') != current_user:
        return jsonify({'success': False, 'message': 'Not authorized'}), 403
    if (order.get('type') or 'sell').lower() != 'sell':
        return jsonify({'success': False, 'message': 'Only sell listings can request price changes'}), 400

    status = (order.get('status') or '').lower()
    if status in ('completed', 'cancelled', 'rejected'):
        return jsonify({'success': False, 'message': 'Listing is no longer active'}), 400

    data = request.get_json() or {}
    requested_price = data.get('requested_price')
    try:
        requested_price = float(requested_price)
    except Exception:
        return jsonify({'success': False, 'message': 'Valid requested_price is required'}), 400
    if requested_price <= 0:
        return jsonify({'success': False, 'message': 'requested_price must be greater than zero'}), 400

    reason = str(data.get('reason') or '').strip()
    request_payload = {
        'requested_price': requested_price,
        'reason': reason,
        'requested_at': time.time(),
        'status': 'pending',
    }
    ok = update_order_by_id(order_id, {'price_change_request': request_payload})
    if not ok:
        return jsonify({'success': False, 'message': 'Could not save request'}), 500

    return jsonify({'success': True, 'request': request_payload})


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
    if Image is None or np is None:
        raise RuntimeError('Image preprocessing unavailable: install Pillow and numpy')
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
    if "image" not in request.files:
        return jsonify({"error": "Missing image"}), 400

    # If ai=1 is requested (or if local ML is unavailable), use Gemini API.
    ai_flag = str(request.args.get('ai') or '').strip().lower() in ('1', 'true', 'yes')
    local_ml_available = not (tf is None or np is None or Image is None)

    img_file = request.files.get('image')
    img_bytes = b''
    try:
        img_bytes = img_file.read() if img_file is not None else b''
    except Exception:
        img_bytes = b''
    mime_type = (getattr(img_file, 'mimetype', None) or '').strip() if img_file is not None else ''

    if ai_flag or not local_ml_available:
        lang_code = _requested_lang_code()
        ai = gemini_disease_detection(img_bytes, mime_type=mime_type, response_lang=lang_code)
        if ai.get('enabled') and isinstance(ai.get('parsed'), dict):
            p = ai.get('parsed') or {}

            def _clean_str(v):
                if v is None:
                    return ''
                return str(v).strip()

            def _clean_str_list(v):
                if not isinstance(v, list):
                    return []
                out = []
                for item in v:
                    s = _clean_str(item)
                    if s:
                        out.append(s)
                return out

            disease_name = _clean_str(p.get('disease')) or 'Unknown'
            description = _clean_str(p.get('description'))
            remedies = _clean_str_list(p.get('remedies'))
            prevention = _clean_str_list(p.get('prevention'))
            daily_care = _clean_str_list(p.get('daily_care'))

            # Treat placeholder strings as missing.
            if _is_placeholder_text(description):
                description = ''
            if len(remedies) == 1 and _is_placeholder_text(remedies[0]):
                remedies = []
            if len(prevention) == 1 and _is_placeholder_text(prevention[0]):
                prevention = []
            if len(daily_care) == 1 and _is_placeholder_text(daily_care[0]):
                daily_care = []

            # If Gemini returns incomplete fields, fill from built-in DISEASE_REMEDIES.
            filled_from_local = False
            if (not description) or (not remedies) or (not prevention) or (not daily_care):
                try:
                    key = normalize_key_from_label(disease_name)
                    info = find_remedy(key, disease_name)
                    if info is not None and info is not DEFAULT_INFO:
                        if not description:
                            description = _clean_str(info.get('description'))
                        if not remedies:
                            remedies = _clean_str_list(info.get('remedies'))
                        if not prevention:
                            prevention = _clean_str_list(info.get('prevention'))
                        if not daily_care:
                            daily_care = _clean_str_list(info.get('daily_care'))
                        filled_from_local = True
                except Exception:
                    pass

            # If still missing, ask Gemini (text-only) to fill.
            if (not description) or (not remedies) or (not prevention) or (not daily_care) or (filled_from_local and _normalize_lang_code(lang_code) != 'en'):
                filled = _gemini_fill_text_only_disease_info(
                    disease=disease_name,
                    lang_code=lang_code,
                    existing={
                        'description': description,
                        'remedies': remedies,
                        'prevention': prevention,
                        'daily_care': daily_care,
                    },
                )
                if isinstance(filled, dict):
                    if not description:
                        description = _clean_str(filled.get('description'))
                    if not remedies:
                        remedies = _clean_str_list(filled.get('remedies'))
                    if not prevention:
                        prevention = _clean_str_list(filled.get('prevention'))
                    if not daily_care:
                        daily_care = _clean_str_list(filled.get('daily_care'))

            # Localized fallbacks (last resort)
            fb = _localized_fallback_texts(lang_code)
            if not description:
                description = fb['no_desc']
            if not remedies:
                remedies = [fb['no_remedies']]
            if not prevention:
                prevention = [fb['no_prevention']]
            if not daily_care:
                daily_care = [fb['no_daily']]

            return jsonify({
                "provider": "gemini",
                "model": ai.get('model'),
                "lang": lang_code,
                "disease": disease_name,
                "confidence": p.get('confidence'),
                "description": description,
                "remedies": remedies,
                "prevention": prevention,
                "daily_care": daily_care,
            })

        # If AI was forced, do not silently fall back to local ML
        if ai_flag:
            return jsonify({
                "error": "AI disease detection failed",
                "reason": ai.get('reason') or 'Unknown',
                "details": ai.get('details') or '',
                "url": ai.get('url'),
                "tried": ai.get('tried'),
                "hint": "Check GEMINI_API_KEY/GOOGLE_API_KEY and DISEASE_GEMINI_MODEL"
            }), 503

        # If local ML isn't available and AI failed, return a clear error.
        if not local_ml_available:
            return jsonify({
                "error": "Disease detection is not available on this server",
                "reason": ai.get('reason') or 'Local ML disabled and AI failed',
                "details": ai.get('details') or '',
                "url": ai.get('url'),
                "tried": ai.get('tried'),
                "hint": "Set GEMINI_API_KEY (and optionally DISEASE_GEMINI_MODEL) OR install tensorflow/numpy/Pillow"
            }), 503

    # Local ML path
    try:
        model = load_model_lazy()  #  ⬅ IMPORTANT
    except Exception as e:
        return jsonify({"error": str(e)}), 503

    try:
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
        "provider": "local",
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


def _read_price_cache_file():
    if os.path.exists(CACHE_FILE):
        try:
            return json.load(open(CACHE_FILE, "r", encoding="utf-8"))
        except Exception as e:
            print("Warning: failed to read cache:", e)
    return {"last_updated": None, "commodities": {}}


def _merge_price_caches(primary, fallback):
    primary = primary if isinstance(primary, dict) else {}
    fallback = fallback if isinstance(fallback, dict) else {}

    merged = {
        'last_updated': primary.get('last_updated') or fallback.get('last_updated'),
        'commodities': {}
    }

    primary_commodities = primary.get('commodities') or {}
    fallback_commodities = fallback.get('commodities') or {}

    for key in set(fallback_commodities.keys()) | set(primary_commodities.keys()):
        primary_entry = primary_commodities.get(key) or {}
        fallback_entry = fallback_commodities.get(key) or {}
        primary_items = primary_entry.get('items') or []
        fallback_items = fallback_entry.get('items') or []

        if primary_items:
            merged['commodities'][key] = primary_entry
        elif fallback_items:
            merged['commodities'][key] = fallback_entry
        elif primary_entry:
            merged['commodities'][key] = primary_entry
        elif fallback_entry:
            merged['commodities'][key] = fallback_entry

    return merged


def _json_sha256(payload) -> str:
    try:
        serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    except Exception:
        serialized = str(payload)
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()


def _today_india_date():
    return datetime.now(INDIA_TZ).date()


def _normalize_price_date(value):
    parsed = _parse_arrival_date(value)
    if parsed is None:
        return ''
    return parsed.date().isoformat()


def _arrival_freshness(value, today_date=None):
    parsed = _parse_arrival_date(value)
    if parsed is None:
        return 'Old'
    if today_date is None:
        today_date = _today_india_date()
    return 'Fresh' if parsed.date() == today_date else 'Old'


def _enrich_market_price_item(item, today_date=None):
    base = dict(item or {})
    if today_date is None:
        today_date = _today_india_date()
    base['price_date'] = _normalize_price_date(base.get('arrival_date'))
    base['price_freshness'] = _arrival_freshness(base.get('arrival_date'), today_date=today_date)
    return base


def _enrich_market_price_items(items):
    today_date = _today_india_date()
    return [_enrich_market_price_item(row, today_date=today_date) for row in (items or [])]

def load_cache():
    # Prefer Mongo-stored cache when available
    mongo_cache = None
    try:
        if mongo_db is not None:
            coll = mongo_db.get_collection(PRICE_COLLECTION)
            meta_doc = coll.find_one({'_id': PRICE_META_DOC_ID}, {'_id': 0}) or {}
            cache = {
                'last_updated': meta_doc.get('last_updated'),
                'last_scraped_at': meta_doc.get('last_scraped_at'),
                'commodities': {},
            }

            docs = list(coll.find({'key': {'$exists': True}}, {'_id': 0}))
            for doc in docs:
                key = norm(doc.get('key') or '')
                if not key:
                    continue
                cache['commodities'][key] = {
                    'fetched_at': doc.get('fetched_at'),
                    'last_scraped_at': doc.get('last_scraped_at'),
                    'items': _enrich_market_price_items(doc.get('items') or []),
                    'source': doc.get('source'),
                    'items_hash': doc.get('items_hash'),
                }

            # Backward compatibility: legacy single-cache document.
            if not cache['commodities']:
                legacy_doc = coll.find_one({'cache': {'$exists': True}}, {'_id': 0, 'cache': 1})
                if legacy_doc and isinstance(legacy_doc.get('cache'), dict):
                    mongo_cache = legacy_doc.get('cache')
            else:
                mongo_cache = cache
    except Exception as e:
        print('load_cache -> mongo error:', e)

    file_cache = _read_price_cache_file()
    if mongo_cache is not None:
        return _merge_price_caches(mongo_cache, file_cache)
    return file_cache

def save_cache(cache):
    # Prefer storing cache to Mongo when available
    try:
        if mongo_db is not None:
            coll = mongo_db.get_collection(PRICE_COLLECTION)
            commodities = (cache or {}).get('commodities') or {}
            now_iso = datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'

            keys = [norm(k) for k in commodities.keys() if norm(k)]
            existing_docs = {}
            if keys:
                for doc in coll.find({'key': {'$in': keys}}, {'_id': 0, 'key': 1, 'items_hash': 1, 'fetched_at': 1, 'last_scraped_at': 1, 'source': 1}):
                    existing_docs[norm(doc.get('key') or '')] = doc

            for key_raw, entry_raw in commodities.items():
                key = norm(key_raw)
                if not key:
                    continue
                entry = entry_raw if isinstance(entry_raw, dict) else {}
                items = _enrich_market_price_items(entry.get('items') or [])
                items_hash = _json_sha256(items)
                doc = {
                    'key': key,
                    'items': items,
                    'items_hash': items_hash,
                    'source': entry.get('source'),
                    'fetched_at': entry.get('fetched_at'),
                    'last_scraped_at': entry.get('last_scraped_at'),
                    'updated_at': now_iso,
                }

                existing = existing_docs.get(key) or {}
                is_unchanged = (
                    existing.get('items_hash') == doc.get('items_hash') and
                    existing.get('fetched_at') == doc.get('fetched_at') and
                    existing.get('last_scraped_at') == doc.get('last_scraped_at') and
                    existing.get('source') == doc.get('source')
                )
                if is_unchanged:
                    continue

                coll.update_one(
                    {'key': key},
                    {
                        '$set': doc,
                        '$setOnInsert': {'created_at': now_iso}
                    },
                    upsert=True
                )

            coll.update_one(
                {'_id': PRICE_META_DOC_ID},
                {
                    '$set': {
                        '_id': PRICE_META_DOC_ID,
                        'schema_version': PRICE_SCHEMA_VERSION,
                        'last_updated': (cache or {}).get('last_updated') or now_iso,
                        'last_scraped_at': (cache or {}).get('last_scraped_at') or now_iso,
                        'updated_at': now_iso,
                    },
                    '$setOnInsert': {'created_at': now_iso},
                },
                upsert=True,
            )
            return
    except Exception as e:
        print('save_cache -> mongo error:', e)

    try:
        json.dump(cache, open(CACHE_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    except Exception as e:
        print("Warning: failed to write cache:", e)

def norm(c: str):
    return c.strip().lower()


def _price_cache_ttl_hours() -> int:
    raw_value = str(os.environ.get('PRICE_CACHE_TTL_HOURS', '1') or '').strip()
    try:
        ttl_hours = int(raw_value)
        return ttl_hours if ttl_hours > 0 else 1
    except Exception:
        return 1


def _parse_utc_iso_datetime(value):
    text = str(value or '').strip()
    if not text:
        return None
    if text.endswith('Z'):
        text = text[:-1] + '+00:00'
    try:
        parsed = datetime.fromisoformat(text)
    except Exception:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _parse_arrival_date(value):
    text = str(value or '').strip()
    if not text:
        return None

    parsed_iso = _parse_utc_iso_datetime(text)
    if parsed_iso is not None:
        return parsed_iso

    for fmt in (
        '%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%y', '%d-%b-%Y',
        '%d %b %Y', '%d %B %Y', '%m/%d/%Y'
    ):
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            continue
    return None


def _build_exact_commodity_match(commodity_name: str) -> dict:
    commodity_text = str(commodity_name or '').strip()
    return {
        'requested': commodity_text,
        'requested_key': _commodity_lookup_key(commodity_text),
        'resolved': commodity_text,
        'resolved_key': norm(commodity_text) if commodity_text else '',
        'match_type': 'exact',
    }


def _is_commodity_cache_stale(entry, ttl_hours=None) -> bool:
    entry = entry if isinstance(entry, dict) else {}
    items = entry.get('items') or []
    if not items:
        return True
    if not entry.get('source'):
        return True

    fetched_at = _parse_utc_iso_datetime(entry.get('fetched_at'))
    if fetched_at is None:
        return True

    max_age = timedelta(hours=ttl_hours if ttl_hours is not None else _price_cache_ttl_hours())
    return (datetime.utcnow() - fetched_at) >= max_age


def _latest_price_date_from_items(items):
    latest = None
    for row in (items or []):
        parsed = _parse_arrival_date((row or {}).get('arrival_date'))
        if parsed is None:
            continue
        row_date = parsed.date()
        if latest is None or row_date > latest:
            latest = row_date
    return latest


def _should_refresh_price_entry(entry, ttl_hours=None):
    entry = entry if isinstance(entry, dict) else {}
    items = _enrich_market_price_items(entry.get('items') or [])
    today_date = _today_india_date()

    if not items:
        return True, 'missing-data'

    latest_price_date = _latest_price_date_from_items(items)
    if latest_price_date is None:
        return True, 'invalid-price-date'
    if latest_price_date < today_date:
        return True, 'price-date-old'

    # Keep TTL as a secondary safety net while making price_date freshness primary.
    if _is_commodity_cache_stale(entry, ttl_hours=ttl_hours):
        return True, 'cache-ttl-expired'

    return False, 'fresh'


def _should_refresh_for_latest_market_day(entry):
    """Refresh when no records exist or latest trading day is older than today."""
    entry = entry if isinstance(entry, dict) else {}
    items = _enrich_market_price_items(entry.get('items') or [])
    if not items:
        return True, 'missing-data', None

    latest_price_date = _latest_price_date_from_items(items)
    if latest_price_date is None:
        return True, 'invalid-price-date', None

    today_date = _today_india_date()
    if latest_price_date < today_date:
        return True, 'price-date-old', latest_price_date.isoformat()

    return False, 'fresh', latest_price_date.isoformat()


def _select_latest_price_item(items):
    candidates = [row for row in (items or []) if _coerce_market_numeric((row or {}).get('modal_price')) is not None]
    if not candidates:
        candidates = list(items or [])
    if not candidates:
        return None

    best_row = candidates[0]
    best_date = _parse_arrival_date(best_row.get('arrival_date'))

    for row in candidates[1:]:
        row_date = _parse_arrival_date(row.get('arrival_date'))
        if row_date is None:
            continue
        if best_date is None or row_date > best_date:
            best_row = row
            best_date = row_date

    return best_row


def _price_response_metadata(entry):
    entry = entry if isinstance(entry, dict) else {}
    items = _enrich_market_price_items(entry.get('items') or [])
    latest_item = _select_latest_price_item(items)
    latest_price = None
    arrival_date = None
    freshness_status = 'Old'
    fresh_count = 0
    old_count = 0
    if latest_item:
        latest_price = _coerce_market_numeric(latest_item.get('modal_price'))
        arrival_date = latest_item.get('arrival_date')
        freshness_status = latest_item.get('price_freshness') or _arrival_freshness(arrival_date)

    for row in items:
        status = str(row.get('price_freshness') or '').strip() or _arrival_freshness(row.get('arrival_date'))
        if status == 'Fresh':
            fresh_count += 1
        else:
            old_count += 1

    return {
        'latest_price': latest_price,
        'arrival_date': arrival_date,
        'price_date': _normalize_price_date(arrival_date),
        'price_freshness': freshness_status,
        'fresh_count': fresh_count,
        'old_count': old_count,
        'fetched_at': entry.get('fetched_at'),
        'last_scraped_at': entry.get('last_scraped_at'),
        'source': entry.get('source'),
    }


DEFAULT_COMMODITY_NAMES = [
    'Tomato', 'Onion', 'Potato', 'Banana', 'Paddy', 'Maize', 'Cotton',
    'Groundnut', 'Sugarcane', 'Turmeric', 'Chilli', 'Coriander'
]


def _commodity_lookup_key(value: str) -> str:
    s = str(value or '').strip().lower()
    s = re.sub(r'[^a-z0-9\s]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _display_commodity_name(value: str) -> str:
    s = str(value or '').strip()
    if not s:
        return ''
    return ' '.join(part.capitalize() for part in re.split(r'\s+', s) if part)


def _read_json_if_exists(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return default


def _collect_known_commodity_candidates(cache=None):
    candidates = {}

    def add_candidate(raw_name, *, stored_key=None, display_name=None):
        text = str(raw_name or '').strip()
        if not text:
            return
        lookup_key = _commodity_lookup_key(text)
        if not lookup_key:
            return
        if lookup_key in {'other', 'local', 'faq', 'medium', 'grade a'}:
            return
        candidates.setdefault(lookup_key, {
            'stored_key': stored_key or norm(text),
            'display_name': display_name or _display_commodity_name(text),
        })

    for name in DEFAULT_COMMODITY_NAMES:
        add_candidate(name)

    cache = cache or load_cache()
    commodities = (cache.get('commodities') or {}) if isinstance(cache, dict) else {}
    for cache_key, cache_entry in commodities.items():
        if not ((cache_entry or {}).get('items') or []):
            continue
        add_candidate(cache_key, stored_key=cache_key, display_name=_display_commodity_name(cache_key))

    products = _read_json_if_exists(os.path.join(CACHE_DIR, 'products.json'), {})
    for product in (products.get('products') or []):
        add_candidate(product.get('name'))

    orders = _read_json_if_exists(os.path.join(CACHE_DIR, 'orders.json'), [])
    for order in orders:
        add_candidate(order.get('product'))

    return candidates


def resolve_commodity_name(raw_name: str, cache=None) -> dict:
    requested = str(raw_name or '').strip()
    requested_key = _commodity_lookup_key(requested)
    result = {
        'requested': requested,
        'requested_key': requested_key,
        'resolved': requested,
        'resolved_key': norm(requested) if requested else '',
        'match_type': 'exact',
    }
    if not requested_key:
        return result

    candidates = _collect_known_commodity_candidates(cache=cache)
    exact = candidates.get(requested_key)
    if exact:
        result['resolved'] = exact['display_name']
        result['resolved_key'] = exact['stored_key']
        return result

    prefix_matches = []
    if len(requested_key) >= 3:
        for lookup_key, meta in candidates.items():
            if lookup_key.startswith(requested_key) or requested_key.startswith(lookup_key):
                prefix_matches.append((lookup_key, meta))
        if prefix_matches:
            prefix_matches.sort(key=lambda item: (abs(len(item[0]) - len(requested_key)), item[0]))
            match = prefix_matches[0][1]
            result['resolved'] = match['display_name']
            result['resolved_key'] = match['stored_key']
            result['match_type'] = 'prefix'
            return result

    close = difflib.get_close_matches(requested_key, list(candidates.keys()), n=1, cutoff=0.72)
    if close:
        match = candidates[close[0]]
        result['resolved'] = match['display_name']
        result['resolved_key'] = match['stored_key']
        result['match_type'] = 'fuzzy'

    return result

# AGMARKNET / datagov urls & headers
AGMARKNET_SEARCH_URL = "https://agmarknet.gov.in/SearchCmmMkt.aspx?CommName={commodity}"
AGMARKNET_COMMODITY_URL = "https://agmarknet.gov.in/PriceAndArrivals/CommodityWisePrices.aspx?CommName={commodity}"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FarmerAssistant/1.0; +http://localhost/)"}


def _http_retry_count() -> int:
    raw = str(os.environ.get('AGMARKNET_HTTP_RETRIES', '3') or '').strip()
    try:
        val = int(raw)
        return val if val > 0 else 3
    except Exception:
        return 3


def _http_timeout_seconds() -> int:
    raw = str(os.environ.get('AGMARKNET_HTTP_TIMEOUT_SECONDS', '15') or '').strip()
    try:
        val = int(raw)
        return val if val > 0 else 15
    except Exception:
        return 15


def _agmarknet_max_pages() -> int:
    raw = str(os.environ.get('AGMARKNET_MAX_PAGES', '30') or '').strip()
    try:
        val = int(raw)
        return val if val > 0 else 30
    except Exception:
        return 30


def _request_with_retry(session_obj, method, url, *, params=None, data=None, headers=None):
    retries = _http_retry_count()
    timeout = _http_timeout_seconds()
    final_error = None
    for attempt in range(1, retries + 1):
        try:
            response = session_obj.request(method=method, url=url, params=params, data=data, headers=headers, timeout=timeout)
            if response.status_code == 200:
                return response
            final_error = RuntimeError(f'HTTP {response.status_code}')
        except Exception as e:
            final_error = e

        if attempt < retries:
            time.sleep(min(0.5 * (2 ** (attempt - 1)), 4.0))

    raise final_error if final_error is not None else RuntimeError('request failed')


def _agmarknet_hidden_fields(soup):
    form = soup.find('form')
    if form is None:
        return {}
    fields = {}
    for inp in form.find_all('input'):
        input_type = str(inp.get('type') or '').lower()
        name = str(inp.get('name') or '').strip()
        if not name:
            continue
        if input_type in ('hidden', 'text', 'search'):
            fields[name] = inp.get('value') or ''
    return fields


def _agmarknet_extract_pager_targets(soup):
    targets = []
    for a in soup.find_all('a'):
        href = str(a.get('href') or '').strip()
        if '__doPostBack' not in href:
            continue
        m = re.search(r"__doPostBack\('([^']*)','([^']*)'\)", href)
        if not m:
            continue
        event_target = m.group(1)
        event_argument = m.group(2)
        if not event_argument.startswith('Page$'):
            continue
        page_num = 0
        try:
            page_num = int(event_argument.split('$', 1)[1])
        except Exception:
            page_num = 0
        targets.append((page_num, event_target, event_argument))

    targets.sort(key=lambda x: (x[0] if x[0] > 0 else 999999, x[1], x[2]))
    unique = []
    seen = set()
    for page_num, event_target, event_argument in targets:
        key = (event_target, event_argument)
        if key in seen:
            continue
        seen.add(key)
        unique.append((page_num, event_target, event_argument))
    return unique


def _coerce_price_number(v):
    if isinstance(v, (int, float)):
        return float(v)
    text = str(v or '').strip()
    if not text:
        return None
    text = text.replace(',', '')
    m = re.search(r'-?\d+(?:\.\d+)?', text)
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None


def _normalize_unit_text(unit_text):
    u = str(unit_text or '').strip().lower()
    if not u:
        return 'INR/quintal'
    if 'quintal' in u or '/q' in u or 'qtl' in u:
        return 'INR/quintal'
    if '/kg' in u or 'kilogram' in u or 'per kg' in u:
        return 'INR/kg'
    return 'INR/quintal'


def _to_inr_per_kg(value, base_unit):
    num = _coerce_price_number(value)
    if num is None:
        return None
    if base_unit == 'INR/quintal':
        return round(num / 100.0, 4)
    return round(num, 4)


def _normalize_market_key_part(value):
    s = str(value or '').strip().lower()
    s = re.sub(r'\s+', ' ', s)
    return s


def _build_mandi_natural_key(record):
    parts = [
        _normalize_market_key_part(record.get('state')),
        _normalize_market_key_part(record.get('district')),
        _normalize_market_key_part(record.get('market')),
        _normalize_market_key_part(record.get('commodity')),
        _normalize_market_key_part(record.get('variety')),
        _normalize_market_key_part(record.get('grade')),
    ]
    return '|'.join(parts)


def _build_mandi_history_key(record):
    parts = [
        _build_mandi_natural_key(record),
        str(record.get('price_date') or ''),
        str(record.get('min_price') if record.get('min_price') is not None else ''),
        str(record.get('max_price') if record.get('max_price') is not None else ''),
        str(record.get('modal_price') if record.get('modal_price') is not None else ''),
    ]
    return hashlib.sha256('|'.join(parts).encode('utf-8')).hexdigest()


def _persist_mandi_price_history(commodity, records, source, scraped_at):
    summary = {
        'inserted': 0,
        'updated': 0,
        'unchanged': 0,
        'history_inserted': 0,
        'history_unchanged': 0,
        'errors': 0,
        'total': 0,
    }

    if mongo_db is None:
        return summary

    latest_coll = mongo_db.get_collection(MANDI_PRICE_LATEST_COLLECTION)
    history_coll = mongo_db.get_collection(MANDI_PRICE_HISTORY_COLLECTION)
    now_iso = datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'

    seen_history_keys = set()
    for row in (records or []):
        try:
            rec = dict(row or {})
            rec['commodity'] = str(rec.get('commodity') or commodity or '').strip()
            rec['state'] = str(rec.get('state') or '').strip()
            rec['district'] = str(rec.get('district') or '').strip()
            rec['market'] = str(rec.get('market') or '').strip()
            rec['variety'] = str(rec.get('variety') or '').strip()
            rec['grade'] = str(rec.get('grade') or '').strip()
            rec['price_date'] = _normalize_price_date(rec.get('arrival_date'))
            rec['source'] = source
            rec['last_scraped_at'] = scraped_at
            rec['recorded_at'] = now_iso

            rec['min_price'] = _coerce_price_number(rec.get('min_price'))
            rec['max_price'] = _coerce_price_number(rec.get('max_price'))
            rec['modal_price'] = _coerce_price_number(rec.get('modal_price'))

            base_unit = _normalize_unit_text(rec.get('price_unit_raw') or rec.get('price_unit'))
            rec['price_unit_base'] = base_unit
            rec['price_unit'] = 'INR/kg'
            rec['min_price_per_kg'] = _to_inr_per_kg(rec.get('min_price'), base_unit)
            rec['max_price_per_kg'] = _to_inr_per_kg(rec.get('max_price'), base_unit)
            rec['modal_price_per_kg'] = _to_inr_per_kg(rec.get('modal_price'), base_unit)

            natural_key = _build_mandi_natural_key(rec)
            rec['natural_key'] = natural_key

            existing = latest_coll.find_one({'natural_key': natural_key}, {'_id': 0, 'price_date': 1, 'min_price': 1, 'max_price': 1, 'modal_price': 1})
            is_insert = existing is None
            is_changed = is_insert or any([
                str(existing.get('price_date') or '') != str(rec.get('price_date') or ''),
                _coerce_price_number(existing.get('min_price')) != _coerce_price_number(rec.get('min_price')),
                _coerce_price_number(existing.get('max_price')) != _coerce_price_number(rec.get('max_price')),
                _coerce_price_number(existing.get('modal_price')) != _coerce_price_number(rec.get('modal_price')),
            ])

            latest_doc = {
                'natural_key': natural_key,
                'state': rec.get('state'),
                'district': rec.get('district'),
                'market': rec.get('market'),
                'commodity': rec.get('commodity'),
                'variety': rec.get('variety'),
                'grade': rec.get('grade'),
                'arrival_date': rec.get('arrival_date'),
                'price_date': rec.get('price_date'),
                'min_price': rec.get('min_price'),
                'max_price': rec.get('max_price'),
                'modal_price': rec.get('modal_price'),
                'price_unit_base': rec.get('price_unit_base'),
                'price_unit': rec.get('price_unit'),
                'min_price_per_kg': rec.get('min_price_per_kg'),
                'max_price_per_kg': rec.get('max_price_per_kg'),
                'modal_price_per_kg': rec.get('modal_price_per_kg'),
                'source': source,
                'last_scraped_at': scraped_at,
                'updated_at': now_iso,
            }
            latest_coll.update_one(
                {'natural_key': natural_key},
                {'$set': latest_doc, '$setOnInsert': {'created_at': now_iso}},
                upsert=True,
            )

            if is_insert:
                summary['inserted'] += 1
            elif is_changed:
                summary['updated'] += 1
            else:
                summary['unchanged'] += 1

            history_key = _build_mandi_history_key(rec)
            if history_key in seen_history_keys:
                summary['history_unchanged'] += 1
            else:
                seen_history_keys.add(history_key)
                history_doc = {
                    'history_key': history_key,
                    'natural_key': natural_key,
                    'state': rec.get('state'),
                    'district': rec.get('district'),
                    'market': rec.get('market'),
                    'commodity': rec.get('commodity'),
                    'variety': rec.get('variety'),
                    'grade': rec.get('grade'),
                    'arrival_date': rec.get('arrival_date'),
                    'price_date': rec.get('price_date'),
                    'min_price': rec.get('min_price'),
                    'max_price': rec.get('max_price'),
                    'modal_price': rec.get('modal_price'),
                    'price_unit_base': rec.get('price_unit_base'),
                    'price_unit': rec.get('price_unit'),
                    'min_price_per_kg': rec.get('min_price_per_kg'),
                    'max_price_per_kg': rec.get('max_price_per_kg'),
                    'modal_price_per_kg': rec.get('modal_price_per_kg'),
                    'source': source,
                    'recorded_at': now_iso,
                    'last_scraped_at': scraped_at,
                }
                hres = history_coll.update_one(
                    {'history_key': history_key},
                    {'$setOnInsert': history_doc},
                    upsert=True,
                )
                if getattr(hres, 'upserted_id', None) is not None:
                    summary['history_inserted'] += 1
                else:
                    summary['history_unchanged'] += 1

            summary['total'] += 1
        except Exception as e:
            summary['errors'] += 1
            print('persist mandi history row error:', e)

    return summary

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

    def canonical_header(h):
        s = str(h or '').strip().lower()
        s = re.sub(r'\s+', ' ', s)
        if 'market' in s:
            return 'market'
        if 'district' in s:
            return 'district'
        if 'state' in s:
            return 'state'
        if 'variety' in s:
            return 'variety'
        if 'grade' in s:
            return 'grade'
        if ('min' in s and 'price' in s) or 'minimum price' in s:
            return 'min_price'
        if ('max' in s and 'price' in s) or 'maximum price' in s:
            return 'max_price'
        if ('modal' in s and 'price' in s):
            return 'modal_price'
        if 'arrival' in s and 'date' in s:
            return 'arrival_date'
        if 'unit' in s:
            return 'price_unit_raw'
        return s.replace(' ', '_')

    canonical_headers = [canonical_header(h) for h in headers]
    inferred_unit = 'Rs./Quintal' if any('price' in h and 'quintal' in h for h in headers) else ''
    rows_out = []
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        texts = [td.get_text(strip=True) for td in tds]
        n = len(texts)
        rec = {}
        if n >= 6:
            if "market" in canonical_headers:
                for i, h in enumerate(canonical_headers[:n]):
                    key = h
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
        rec.setdefault("price_unit_raw", rec.get("price_unit_raw") or inferred_unit or "Rs./Quintal")

        rows_out.append(rec)
    return rows_out

def fetch_from_agmarknet(commodity):
    c = commodity.strip()
    try_urls = [
        AGMARKNET_COMMODITY_URL.format(commodity=c),
        AGMARKNET_SEARCH_URL.format(commodity=c)
    ]
    session_obj = requests.Session()
    for url in try_urls:
        try:
            response = _request_with_retry(session_obj, 'GET', url, headers=HEADERS)
            try:
                soup = BeautifulSoup(response.text, "lxml")
            except FeatureNotFound:
                soup = BeautifulSoup(response.text, "html.parser")

            all_rows = []
            seen_row_keys = set()

            def add_rows(rows):
                for rec in (rows or []):
                    row = dict(rec or {})
                    row['commodity'] = commodity
                    base_unit = _normalize_unit_text(row.get('price_unit_raw') or row.get('price_unit'))
                    row['price_unit_base'] = base_unit
                    row['price_unit'] = 'INR/kg'
                    row['min_price_per_kg'] = _to_inr_per_kg(row.get('min_price'), base_unit)
                    row['max_price_per_kg'] = _to_inr_per_kg(row.get('max_price'), base_unit)
                    row['modal_price_per_kg'] = _to_inr_per_kg(row.get('modal_price'), base_unit)
                    key = _json_sha256([
                        _normalize_market_key_part(row.get('state')),
                        _normalize_market_key_part(row.get('district')),
                        _normalize_market_key_part(row.get('market')),
                        _normalize_market_key_part(row.get('commodity')),
                        _normalize_market_key_part(row.get('variety')),
                        _normalize_market_key_part(row.get('grade')),
                        str(row.get('arrival_date') or ''),
                        str(row.get('min_price') or ''),
                        str(row.get('max_price') or ''),
                        str(row.get('modal_price') or ''),
                    ])
                    if key in seen_row_keys:
                        continue
                    seen_row_keys.add(key)
                    all_rows.append(row)

            add_rows(parse_price_table_from_soup(soup))

            queue = []
            visited_targets = set()
            max_pages = _agmarknet_max_pages()

            def enqueue_from_soup(page_soup):
                hidden = _agmarknet_hidden_fields(page_soup)
                for _, event_target, event_argument in _agmarknet_extract_pager_targets(page_soup):
                    tkey = (event_target, event_argument)
                    if tkey in visited_targets:
                        continue
                    queue.append((event_target, event_argument, dict(hidden)))

            enqueue_from_soup(soup)
            pages_fetched = 1

            while queue and pages_fetched < max_pages:
                event_target, event_argument, hidden_fields = queue.pop(0)
                target_key = (event_target, event_argument)
                if target_key in visited_targets:
                    continue
                visited_targets.add(target_key)

                payload = dict(hidden_fields)
                payload['__EVENTTARGET'] = event_target
                payload['__EVENTARGUMENT'] = event_argument

                try:
                    page_resp = _request_with_retry(session_obj, 'POST', url, data=payload, headers=HEADERS)
                except Exception as e:
                    print('agmarknet page fetch error for', event_argument, ':', e)
                    continue

                try:
                    page_soup = BeautifulSoup(page_resp.text, "lxml")
                except FeatureNotFound:
                    page_soup = BeautifulSoup(page_resp.text, "html.parser")

                add_rows(parse_price_table_from_soup(page_soup))
                enqueue_from_soup(page_soup)
                pages_fetched += 1

            if all_rows:
                return all_rows
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
            unit_raw = d.get('price_unit') or d.get('unit') or 'Rs./Quintal'
            base_unit = _normalize_unit_text(unit_raw)
            rec = {
                "market": d.get("market", ""),
                "district": d.get("district", ""),
                "state": d.get("state", ""),
                "variety": d.get("variety", None),
                "grade": d.get("grade", None),
                "min_price": int(d.get("min_price")) if d.get("min_price") and str(d.get("min_price")).isdigit() else None,
                "max_price": int(d.get("max_price")) if d.get("max_price") and str(d.get("max_price")).isdigit() else None,
                "modal_price": int(d.get("modal_price")) if d.get("modal_price") and str(d.get("modal_price")).isdigit() else None,
                "arrival_date": d.get("arrival_date") or d.get("date"),
                "price_unit_raw": unit_raw,
                "price_unit_base": base_unit,
                "price_unit": 'INR/kg',
            }
            rec['min_price_per_kg'] = _to_inr_per_kg(rec.get('min_price'), base_unit)
            rec['max_price_per_kg'] = _to_inr_per_kg(rec.get('max_price'), base_unit)
            rec['modal_price_per_kg'] = _to_inr_per_kg(rec.get('modal_price'), base_unit)
            out.append(rec)
        return out
    except Exception as e:
        print("fetch_from_datagov error:", e)
        return []


def fetch_prices_from_upstream(commodity):
    recs = fetch_from_agmarknet(commodity)
    if recs:
        return recs, 'agmarknet'

    recs = fetch_from_datagov(commodity)
    if recs:
        return recs, 'fallback'

    return [], None

def update_prices_for_commodity(commodity, force=False, return_summary=False):
    cache = load_cache()
    key = norm(commodity)
    now = datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
    existing = cache.get("commodities", {}).get(key)
    if existing and not force and not _is_commodity_cache_stale(existing):
        print("Using recent cache for", key)
        return cache

    recs, source = fetch_prices_from_upstream(commodity)
    sync_summary = {
        'inserted': 0,
        'updated': 0,
        'unchanged': 0,
        'history_inserted': 0,
        'history_unchanged': 0,
        'errors': 0,
        'total': 0,
    }

    if recs:
        enriched_items = _enrich_market_price_items(recs)
        new_hash = _json_sha256(enriched_items)
        existing_hash = _json_sha256(_enrich_market_price_items((existing or {}).get('items') or [])) if existing else None
        data_changed = (existing_hash != new_hash) or ((existing or {}).get('source') != source)

        try:
            sync_summary = _persist_mandi_price_history(
                commodity=commodity,
                records=enriched_items,
                source=source,
                scraped_at=now,
            )
        except Exception as e:
            print('persist mandi sync error:', e)

        cache.setdefault("commodities", {})[key] = {
            "fetched_at": now if data_changed else (existing or {}).get('fetched_at') or now,
            "last_scraped_at": now,
            "items": enriched_items,
            "source": source,
            "items_hash": new_hash,
            "sync_summary": sync_summary,
        }
    else:
        cache.setdefault("commodities", {})[key] = {
            "fetched_at": (existing or {}).get('fetched_at'),
            "last_scraped_at": now,
            "items": (existing or {}).get('items', []),
            "source": (existing or {}).get('source'),
            "items_hash": (existing or {}).get('items_hash'),
            "sync_summary": sync_summary,
        }

    cache["last_updated"] = now
    cache["last_scraped_at"] = now
    save_cache(cache)
    try:
        print(
            "Mandi sync summary",
            key,
            "inserted=", sync_summary.get('inserted', 0),
            "updated=", sync_summary.get('updated', 0),
            "unchanged=", sync_summary.get('unchanged', 0),
            "history_inserted=", sync_summary.get('history_inserted', 0),
            "errors=", sync_summary.get('errors', 0),
        )
    except Exception:
        pass
    if return_summary:
        return {'cache': cache, 'sync_summary': sync_summary}
    return cache


def scrape_agmarknet(commodity):
    """Synchronous on-demand refresh used by the price route."""
    return update_prices_for_commodity(commodity, force=True)


# -----------------------------------------------------
#   OPTIONAL: GEMINI/GEMMA AI SUMMARY FOR LIVE PRICE
# -----------------------------------------------------
def _gemini_config():
    api_key = (os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY') or '').strip()
    model = (os.environ.get('GEMINI_MODEL') or 'gemini-2.0-flash').strip()
    # Optional comma-separated fallback model names to try if the primary model fails.
    # Example: GEMINI_MODEL_FALLBACKS=gemini-2.0-flash-lite,gemini-1.5-flash,gemini-1.5-flash-8b
    fallbacks_raw = (os.environ.get('GEMINI_MODEL_FALLBACKS') or '').strip()
    fallbacks = [m.strip() for m in fallbacks_raw.split(',') if m.strip()] if fallbacks_raw else []
    api_base = (os.environ.get('GEMINI_API_BASE') or 'https://generativelanguage.googleapis.com').strip()
    return {
        'api_key': api_key,
        'model': _normalize_gemini_model_name(model),
        'fallback_models': fallbacks,
        'api_base': api_base,
    }


def _normalize_gemini_model_name(model_name: str) -> str:
    """Normalize model names from API outputs.

    The Models API returns names like 'models/gemma-3-4b-it'. The generateContent
    endpoint expects just 'gemma-3-4b-it' in the URL path.
    """
    s = (model_name or '').strip()
    if not s:
        return ''
    if s.startswith('models/'):
        return s[len('models/'):]
    return s


def _iter_unique_models(primary: str, fallbacks=None):
    seen = set()
    for m in ([primary] + (fallbacks or [])):
        mm = _normalize_gemini_model_name(m)
        if not mm or mm in seen:
            continue
        seen.add(mm)
        yield mm


def _iter_unique_payloads(payload_primary: dict, payload_secondary: dict = None, payload_variants=None):
    seen = set()
    for payload in [payload_primary, payload_secondary] + (payload_variants or []):
        if not payload:
            continue
        try:
            marker = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        except Exception:
            marker = repr(payload)
        if marker in seen:
            continue
        seen.add(marker)
        yield payload


def _model_from_used_url(url: str, default_model: str = None) -> str:
    if not url:
        return (default_model or '').strip() or None
    try:
        # .../models/<MODEL>:generateContent
        s = str(url)
        if '/models/' not in s:
            return (default_model or '').strip() or None
        tail = s.split('/models/', 1)[1]
        model_part = tail.split(':generateContent', 1)[0]
        model_part = model_part.strip()
        return model_part or ((default_model or '').strip() or None)
    except Exception:
        return (default_model or '').strip() or None


@app.route('/api/gemini/models', methods=['GET'])
def api_gemini_models():
    """List models visible to the current GEMINI_API_KEY.

    Useful for debugging 404/unsupported-model issues.
    """
    cfg = _gemini_config()
    if not cfg.get('api_key'):
        return jsonify({'enabled': False, 'error': 'GEMINI_API_KEY not set'}), 503

    base = (cfg.get('api_base') or '').strip().rstrip('/') or 'https://generativelanguage.googleapis.com'
    key = cfg.get('api_key')

    out = []
    errors = []
    for version in ('v1', 'v1beta'):
        url = f"{base}/{version}/models"
        try:
            r = requests.get(url, params={'key': key}, timeout=15)
            if r.status_code != 200:
                errors.append({'version': version, 'status': r.status_code, 'details': (r.text[:300] if getattr(r, 'text', None) else '')})
                continue
            jd = r.json() if r.content else {}
            models = jd.get('models') or []
            for m in models:
                name = m.get('name')
                methods = m.get('supportedGenerationMethods') or m.get('supported_generation_methods') or []
                out.append({'version': version, 'name': name, 'methods': methods})
        except Exception as e:
            errors.append({'version': version, 'error': str(e)[:200]})

    return jsonify({'enabled': True, 'count': len(out), 'models': out[:500], 'errors': errors})


def _gemini_generate_content_request(
    *,
    api_base: str,
    api_key: str,
    model: str,
    fallback_models: list = None,
    payload_primary: dict,
    payload_secondary: dict = None,
    payload_variants: list = None,
    timeout: int = 20,
):
    """POST to Gemini REST generateContent.

    Gemini has had multiple REST versions over time. Some hosts now return 404 for
    deprecated paths (e.g. /v1beta). We try /v1 first, then /v1beta.

    Returns: (response, url_used, tried_urls)
    Where response may be a requests.Response or an Exception.
    """
    base = (api_base or '').strip().rstrip('/') or 'https://generativelanguage.googleapis.com'
    key = (api_key or '').strip()
    primary_model = (model or '').strip()
    tried = []
    last = None
    last_url = None

    for m in _iter_unique_models(primary_model, fallback_models):
        for version in ('v1', 'v1beta'):
            url = f"{base}/{version}/models/{m}:generateContent"
            last_url = url
            for payload in _iter_unique_payloads(payload_primary, payload_secondary, payload_variants):
                tried.append(url)
                try:
                    r = requests.post(url, params={'key': key}, json=payload, timeout=timeout)
                except Exception as e:
                    last = e
                    continue

                # If this model/version isn't supported, keep trying fallbacks.
                if r.status_code == 404:
                    last = r
                    break

                if r.status_code == 400:
                    last = r
                    continue

                return r, url, tried

    return last, last_url, tried


def _gemini_market_model_name() -> str:
    return 'gemma-3-4b-it'


def _gemini_market_model_fallbacks() -> list:
    return []


def _extract_grounding_sources(candidate: dict) -> list:
    out = []
    seen = set()
    metadata = (candidate or {}).get('groundingMetadata') or {}
    for chunk in (metadata.get('groundingChunks') or []):
        web = (chunk or {}).get('web') or {}
        uri = (web.get('uri') or '').strip()
        title = (web.get('title') or '').strip()
        if not uri:
            continue
        key = (uri, title)
        if key in seen:
            continue
        seen.add(key)
        out.append({'uri': uri, 'title': title or uri})
    return out[:8]


def _extract_json_from_text(text: str):
    if not text:
        return None
    text = text.strip()
    # direct JSON
    try:
        if text.startswith('{') and text.endswith('}'):
            return json.loads(text)
    except Exception:
        pass

    # fenced block
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            return None

    # best-effort: first {...} block
    m2 = re.search(r"(\{.*\})", text, flags=re.DOTALL)
    if m2:
        try:
            return json.loads(m2.group(1))
        except Exception:
            return None
    return None


def _coerce_market_numeric(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip()
    if not text:
        return None
    if re.search(r'[A-Za-z:]', text):
        return None
    cleaned = text.replace(',', '').strip()
    if re.fullmatch(r'-?\d+(?:\.\d+)?', cleaned):
        number = float(cleaned)
        return int(number) if number.is_integer() else number
    return None


def _sanitize_market_ai_payload(parsed, expected_commodity: str):
    if not isinstance(parsed, dict):
        return None

    expected = _display_commodity_name(expected_commodity)
    corrected = str(parsed.get('commodity_corrected') or '').strip() or expected
    lowered = corrected.lower()
    if any(sep in corrected for sep in [',', ';', '/', '|']) or ' or ' in lowered:
        corrected = expected

    recommended_modal_price = _coerce_market_numeric(parsed.get('recommended_modal_price'))
    price_min = _coerce_market_numeric(parsed.get('price_min'))
    price_max = _coerce_market_numeric(parsed.get('price_max'))
    markets_count = _coerce_market_numeric(parsed.get('markets_count'))

    return {
        'commodity_corrected': corrected,
        'recommended_modal_price': recommended_modal_price,
        'currency': str(parsed.get('currency') or 'INR').strip() or 'INR',
        'unit': str(parsed.get('unit') or '100kg').strip() or '100kg',
        'price_min': price_min,
        'price_max': price_max,
        'markets_count': markets_count,
        'as_of': str(parsed.get('as_of') or '').strip(),
        'rationale': str(parsed.get('rationale') or '').strip(),
    }


def _fallback_market_ai_payload(items: list, commodity: str):
    modal_prices = []
    min_prices = []
    max_prices = []
    for row in (items or []):
        if not isinstance(row, dict):
            continue
        modal_value = _coerce_market_numeric(row.get('modal_price'))
        min_value = _coerce_market_numeric(row.get('min_price'))
        max_value = _coerce_market_numeric(row.get('max_price'))
        if modal_value is not None:
            modal_prices.append(modal_value)
        if min_value is not None:
            min_prices.append(min_value)
        if max_value is not None:
            max_prices.append(max_value)

    if not modal_prices and not min_prices and not max_prices:
        return None

    sorted_modal = sorted(modal_prices)
    recommended = None
    if sorted_modal:
        mid = len(sorted_modal) // 2
        if len(sorted_modal) % 2 == 1:
            recommended = sorted_modal[mid]
        else:
            recommended = int(round((sorted_modal[mid - 1] + sorted_modal[mid]) / 2.0))

    return {
        'commodity_corrected': _display_commodity_name(commodity),
        'recommended_modal_price': recommended,
        'currency': 'INR',
        'unit': '100kg',
        'price_min': min(min_prices) if min_prices else (min(sorted_modal) if sorted_modal else None),
        'price_max': max(max_prices) if max_prices else (max(sorted_modal) if sorted_modal else None),
        'markets_count': len(sorted_modal),
        'as_of': '',
        'rationale': '',
    }


def _redact_api_key(text: str, api_key: str = None) -> str:
    if not text:
        return text
    out = str(text)
    try:
        if api_key:
            out = out.replace(api_key, 'REDACTED')
    except Exception:
        pass
    try:
        out = re.sub(r'([?&]key=)[^&\s]+', r'\1REDACTED', out)
    except Exception:
        pass
    return out


def _gemini_error_payload(r):
    """Return (message, details, hint) for a Gemini HTTP error response."""
    status = getattr(r, 'status_code', None)
    message = ''
    details = ''

    try:
        jd = r.json() if getattr(r, 'content', None) else {}
    except Exception:
        jd = {}

    err = (jd.get('error') if isinstance(jd, dict) else None) or {}
    if isinstance(err, dict):
        message = (err.get('message') or '').strip()
        try:
            details = json.dumps(err, ensure_ascii=False, indent=2)[:1000]
        except Exception:
            details = ''

    if not details:
        try:
            details = (r.text[:1000] if getattr(r, 'text', None) else '')
        except Exception:
            details = ''

    if not message:
        message = f"Gemini API error {status}" if status else "Gemini API error"

    hint = None
    lower_message = message.lower()
    if 'search as tool is not enabled' in lower_message:
        return (
            'Live web search is not available for gemma-3-4b-it.',
            details,
            'The market AI is pinned to gemma-3-4b-it, but this model cannot use the Google Search tool in the current API.'
        )
    if 'json mode is not enabled' in lower_message:
        return (
            'Structured JSON mode is not available for gemma-3-4b-it.',
            details,
            'This model must be called without JSON response mode. The market request has been adjusted to avoid that mode.'
        )

    if status == 429:
        hint = (
            "Quota/rate-limit exceeded for this API key. "
            "Check your plan/billing and current usage limits in Google AI Studio, "
            "or wait and retry later."
        )
    elif status in (401, 403):
        hint = (
            "API key rejected. Verify the key is correct, the Gemini API is enabled for the project/account, "
            "and the key has no restrictive application/IP referrer rules for your server."
        )
    elif status == 404:
        hint = "Model not found or not available to this key. Try a model name returned by /api/gemini/models."
    elif status == 400:
        hint = "Bad request. Check model name and request payload format."

    return message, details, hint


def gemini_live_price_summary(commodity: str, items: list, state: str = None, district: str = None, market: str = None):
    """Use Gemini/Gemma to answer a commodity price query without tool grounding."""
    cfg = _gemini_config()
    if not cfg['api_key']:
        return {
            'enabled': False,
            'reason': 'GEMINI_API_KEY (or GOOGLE_API_KEY) not configured'
        }

    focus_bits = []
    if state:
        focus_bits.append(f"state={state}")
    if district:
        focus_bits.append(f"district={district}")
    if market:
        focus_bits.append(f"market={market}")
    focus = (', '.join(focus_bits)) if focus_bits else 'none'

    sample_rows = []
    for row in (items or [])[:5]:
        if not isinstance(row, dict):
            continue
        sample_rows.append({
            'market': row.get('market'),
            'district': row.get('district'),
            'state': row.get('state'),
            'modal_price': row.get('modal_price'),
            'arrival_date': row.get('arrival_date'),
        })

    prompt = (
        "You are an agriculture market analyst. "
        "The user searched for exactly one commodity price. "
        "Correct spelling mistakes in the commodity name if needed, then answer for that one commodity only. "
        "Do not mention alternative commodities, comparisons, suggestion lists, or multiple product names. "
        "Do not use tools. Just answer from the model directly. "
        "Use INR and unit '100kg'. "
        "Return ONLY valid JSON with these keys: "
        "commodity_corrected, recommended_modal_price, currency, unit, price_min, price_max, markets_count, as_of, rationale. "
        "recommended_modal_price must be a single number or null, never a string list. "
        "If you are uncertain, still return JSON and explain the uncertainty in rationale.\n"
        f"User searched: {commodity}\n"
        f"Focus location: {focus}\n"
        f"Optional cached market rows for context: {json.dumps(sample_rows, ensure_ascii=False)}"
    )

    try:
        generation_config = {
            'temperature': 0.2,
            'maxOutputTokens': 512,
        }
        generation_config_snake = {
            'temperature': 0.2,
            'max_output_tokens': 512,
        }

        payload_plain = {
            'contents': [
                {'role': 'user', 'parts': [{'text': prompt}]}
            ],
            'generationConfig': generation_config,
        }
        payload_plain_snake = {
            'contents': [
                {'role': 'user', 'parts': [{'text': prompt}]}
            ],
            'generation_config': generation_config_snake,
        }
        model_name = _gemini_market_model_name()
        fallback_models = _gemini_market_model_fallbacks()
        r, used_url, tried_urls = _gemini_generate_content_request(
            api_base=cfg['api_base'],
            api_key=cfg['api_key'],
            model=model_name,
            fallback_models=fallback_models,
            payload_primary=payload_plain,
            payload_secondary=payload_plain_snake,
            timeout=20,
        )

        if isinstance(r, Exception):
            return {
                'enabled': False,
                'reason': f"Gemini request failed: {_redact_api_key(str(r), cfg.get('api_key'))}",
                'url': used_url,
                'tried': tried_urls,
            }
        if r.status_code != 200:
            msg, details, hint = _gemini_error_payload(r)
            return {
                'enabled': False,
                'reason': msg,
                'details': details,
                'hint': hint,
                'url': used_url,
                'tried': tried_urls,
            }

        data = r.json() if r.content else {}
        text = ''
        candidate = {}
        try:
            # candidates[0].content.parts[0].text
            candidate = (data.get('candidates') or [])[0] if (data.get('candidates') or []) else {}
            parts = (((candidate.get('content') or {}).get('parts')) or [])
            if parts and isinstance(parts[0], dict):
                text = parts[0].get('text') or ''
        except Exception:
            text = ''

        parsed = _sanitize_market_ai_payload(_extract_json_from_text(text), commodity)
        if not parsed:
            parsed = _fallback_market_ai_payload(items, commodity)
        elif parsed.get('recommended_modal_price') is None:
            fallback_parsed = _fallback_market_ai_payload(items, commodity)
            if fallback_parsed and fallback_parsed.get('recommended_modal_price') is not None:
                parsed['recommended_modal_price'] = fallback_parsed.get('recommended_modal_price')
                if parsed.get('price_min') is None:
                    parsed['price_min'] = fallback_parsed.get('price_min')
                if parsed.get('price_max') is None:
                    parsed['price_max'] = fallback_parsed.get('price_max')
                if parsed.get('markets_count') is None:
                    parsed['markets_count'] = fallback_parsed.get('markets_count')
        model_used = _model_from_used_url(used_url, cfg.get('model'))

        return {
            'enabled': True,
            'model': model_used,
            'raw_text': text,
            'parsed': parsed,
            'sources': [],
            'web_search_queries': [],
            'grounded': False,
        }
    except Exception as e:
        return {
            'enabled': False,
            'reason': f"Gemini request failed: {_redact_api_key(str(e), cfg.get('api_key'))}"
        }


def _gemini_disease_model_name():
    """Model name for Gemini disease detection.

    Note: image-based prompts require a multimodal Gemini model.
    """
    return (
        os.environ.get('DISEASE_GEMINI_MODEL')
        or os.environ.get('GEMINI_DISEASE_MODEL')
        or 'gemma-3-4b-it'
    ).strip()


def _gemini_disease_model_fallbacks():
    raw = (
        os.environ.get('DISEASE_GEMINI_MODEL_FALLBACKS')
        or os.environ.get('GEMINI_DISEASE_MODEL_FALLBACKS')
        or ''
    ).strip()
    if not raw:
        return []
    return [_normalize_gemini_model_name(m) for m in raw.split(',') if (m or '').strip()]


def gemini_disease_detection(image_bytes: bytes, mime_type: str = None, response_lang: str = 'en'):
    """Use Gemini to classify plant disease from an image.

    Returns a dict shaped similarly to the local /predict response.
    """
    cfg = _gemini_config()
    if not cfg['api_key']:
        return {
            'enabled': False,
            'reason': 'GEMINI_API_KEY (or GOOGLE_API_KEY) not configured'
        }

    mime = (mime_type or '').strip() or 'image/jpeg'
    try:
        b64 = base64.b64encode(image_bytes or b'').decode('ascii')
    except Exception:
        b64 = ''
    if not b64:
        return {
            'enabled': False,
            'reason': 'Empty image'
        }

    model_name = _gemini_disease_model_name()
    disease_fallbacks = _gemini_disease_model_fallbacks()

    lang_code = _normalize_lang_code(response_lang)
    lang_names = {
        'en': 'English',
        'hi': 'Hindi',
        'ta': 'Tamil',
        'kn': 'Kannada',
        'ml': 'Malayalam',
    }
    target_lang = lang_names.get(lang_code, 'English')
    prompt = (
        "You are a plant disease detection assistant. "
        "Analyze the plant image and identify the most likely disease (or Healthy). "
        "Return ONLY valid JSON with keys: disease, confidence, description, remedies, prevention, daily_care. "
        "confidence must be a number from 0 to 1. remedies/prevention/daily_care must be arrays of strings. "
        "IMPORTANT: Return human-readable text, NOT translation keys. "
        "Do NOT return strings like 'disease.xxx', 'remedy.xxx', 'prevention.xxx', 'daily.xxx' or '...\.description'. "
        "If the crop/plant is recognizable, include the crop name in the disease field (e.g., 'Apple Scab', 'Pear Fire Blight'). "
        "description must not be empty. "
        f"Answer in {target_lang}. "
        "Keep answers short and practical."
    )

    def _humanize_keyish_text(val):
        """Convert i18n-like keys (e.g. 'disease.foo_bar.description') into readable text."""
        if val is None:
            return val
        if isinstance(val, (int, float, bool)):
            return val
        s = str(val).strip()
        if not s:
            return s
        # Strip common suffixes and prefixes
        s = re.sub(r"\.(description|details|info)$", "", s, flags=re.IGNORECASE)
        s = re.sub(r"^(disease|remedy|prevention|daily|daily_care)\.", "", s, flags=re.IGNORECASE)
        # If dotted, keep last segment
        if '.' in s:
            s = s.split('.')[-1]
        # Replace underscores/delimiters with spaces
        s = re.sub(r"[^a-zA-Z0-9]+", " ", s).strip()
        s = re.sub(r"\s+", " ", s)
        # Title case words
        s = " ".join([w[:1].upper() + w[1:] if w else "" for w in s.split(" ")]).strip()
        return s

    def _sanitize_gemini_disease_payload(p):
        if not isinstance(p, dict):
            return p
        out = dict(p)
        out['disease'] = _humanize_keyish_text(out.get('disease'))
        out['description'] = _humanize_keyish_text(out.get('description'))
        for k in ('remedies', 'prevention', 'daily_care'):
            v = out.get(k)
            if isinstance(v, list):
                out[k] = [_humanize_keyish_text(x) for x in v]
            elif v is None:
                out[k] = []
            else:
                out[k] = [_humanize_keyish_text(v)]
        return out

    try:
        payload_v1 = {
            'contents': [
                {
                    'role': 'user',
                    'parts': [
                        {'text': prompt},
                        {
                            'inlineData': {
                                'mimeType': mime,
                                'data': b64
                            }
                        }
                    ]
                }
            ],
            'generationConfig': {
                'temperature': 0.2,
                'maxOutputTokens': 512
            }
        }

        payload_v2 = {
            'contents': [
                {
                    'role': 'user',
                    'parts': [
                        {'text': prompt},
                        {
                            'inline_data': {
                                'mime_type': mime,
                                'data': b64
                            }
                        }
                    ]
                }
            ],
            'generation_config': {
                'temperature': 0.2,
                'max_output_tokens': 512
            }
        }

        r, used_url, tried_urls = _gemini_generate_content_request(
            api_base=cfg['api_base'],
            api_key=cfg['api_key'],
            model=model_name,
            fallback_models=disease_fallbacks,
            payload_primary=payload_v1,
            payload_secondary=payload_v2,
            timeout=25,
        )

        if isinstance(r, Exception):
            return {
                'enabled': False,
                'reason': f"Gemini request failed: {_redact_api_key(str(r), cfg.get('api_key'))}",
                'url': used_url,
                'tried': tried_urls,
            }
        if r.status_code != 200:
            msg, details, hint = _gemini_error_payload(r)
            return {
                'enabled': False,
                'reason': msg,
                'details': details,
                'hint': hint,
                'url': used_url,
                'tried': tried_urls,
            }

        data = r.json() if r.content else {}
        text = ''
        try:
            cand0 = (data.get('candidates') or [])[0] if (data.get('candidates') or []) else {}
            parts = (((cand0.get('content') or {}).get('parts')) or [])
            if parts and isinstance(parts[0], dict):
                text = parts[0].get('text') or ''
        except Exception:
            text = ''

        parsed = _extract_json_from_text(text)
        model_used = _model_from_used_url(used_url, model_name)
        if not isinstance(parsed, dict):
            return {
                'enabled': True,
                'model': model_used,
                'raw_text': text,
                'parsed': None,
                'reason': 'Model did not return JSON'
            }

        return {
            'enabled': True,
            'model': model_used,
            'raw_text': text,
            'parsed': _sanitize_gemini_disease_payload(parsed)
        }
    except Exception as e:
        return {
            'enabled': False,
            'reason': f"Gemini request failed: {_redact_api_key(str(e), cfg.get('api_key'))}"
        }


# -----------------------------------------------------
#   GEMINI AGENT FOR DISEASE FOLLOW-UP QUESTIONS
# -----------------------------------------------------
@app.route("/disease/ask", methods=["POST"])
def disease_ask():
    """Handle follow-up questions about a detected plant disease using Gemini."""
    data = request.get_json(silent=True) or {}
    question = (data.get('question') or '').strip()
    disease = (data.get('disease') or '').strip()
    context = data.get('context') or {}

    if not question:
        return jsonify({"error": "Missing question"}), 400

    cfg = _gemini_config()
    if not cfg['api_key']:
        return jsonify({
            "enabled": False,
            "error": "AI assistant not configured",
            "reason": "GEMINI_API_KEY not set"
        }), 503

    model_name = _gemini_disease_model_name()
    disease_fallbacks = _gemini_disease_model_fallbacks()

    lang_code = _requested_lang_code()
    lang_names = {
        'en': 'English',
        'hi': 'Hindi',
        'ta': 'Tamil',
        'kn': 'Kannada',
        'ml': 'Malayalam',
    }
    target_lang = lang_names.get(lang_code, 'English')

    # Build context from previous disease detection
    context_text = ""
    if disease:
        context_text += f"The detected plant disease is: {disease}. "
    if context.get('description'):
        context_text += f"Description: {context['description']}. "
    if context.get('remedies') and isinstance(context['remedies'], list):
        context_text += f"Suggested remedies: {', '.join(context['remedies'])}. "
    if context.get('prevention') and isinstance(context['prevention'], list):
        context_text += f"Prevention tips: {', '.join(context['prevention'])}. "

    prompt = (
        "You are an expert agricultural assistant specializing in plant diseases. "
        f"{context_text}"
        f"The farmer has the following question: {question}\n\n"
        "Provide a helpful, practical, and concise answer. "
        "Focus on actionable advice. Keep the response under 200 words. "
        f"Answer in {target_lang}. "
        "If you don't know the answer, say so honestly."
    )

    try:
        payload_v1 = {
            'contents': [
                {
                    'role': 'user',
                    'parts': [{'text': prompt}]
                }
            ],
            'generationConfig': {
                'temperature': 0.3,
                'maxOutputTokens': 512
            }
        }

        payload_v2 = {
            'contents': [
                {
                    'role': 'user',
                    'parts': [{'text': prompt}]
                }
            ],
            'generation_config': {
                'temperature': 0.3,
                'max_output_tokens': 512
            }
        }

        r, used_url, tried_urls = _gemini_generate_content_request(
            api_base=cfg['api_base'],
            api_key=cfg['api_key'],
            model=model_name,
            fallback_models=disease_fallbacks,
            payload_primary=payload_v1,
            payload_secondary=payload_v2,
            timeout=25,
        )

        if isinstance(r, Exception):
            return jsonify({
                "enabled": False,
                "error": "AI request failed",
                "reason": _redact_api_key(str(r), cfg.get('api_key'))
            }), 503

        if r.status_code != 200:
            msg, details, hint = _gemini_error_payload(r)
            return jsonify({
                "enabled": False,
                "error": msg,
                "details": details,
                "hint": hint,
            }), 503

        data_resp = r.json() if r.content else {}
        answer = ''
        try:
            cand0 = (data_resp.get('candidates') or [])[0] if (data_resp.get('candidates') or []) else {}
            parts = (((cand0.get('content') or {}).get('parts')) or [])
            if parts and isinstance(parts[0], dict):
                answer = parts[0].get('text') or ''
        except Exception:
            answer = ''

        if not answer:
            return jsonify({
                "enabled": True,
                "model": _model_from_used_url(used_url, model_name),
                "answer": "I could not generate a response. Please try rephrasing your question."
            })

        return jsonify({
            "enabled": True,
            "model": _model_from_used_url(used_url, model_name),
            "answer": answer.strip()
        })

    except Exception as e:
        return jsonify({
            "enabled": False,
            "error": "AI request failed",
            "reason": _redact_api_key(str(e), cfg.get('api_key'))
        }), 503


# -----------------------------------------------------
#   Scheduler: hourly refresh
# -----------------------------------------------------
scheduler = BackgroundScheduler()
def _price_refresh_interval_hours() -> int:
    raw_value = str(os.environ.get('PRICE_REFRESH_INTERVAL_HOURS', '1') or '').strip()
    try:
        interval = int(raw_value)
        return interval if interval > 0 else 1
    except Exception:
        return 1


def scheduled_price_refresh():
    cache = load_cache()
    commodities = list(cache.get("commodities", {}).keys())
    if not commodities:
        for c in ["tomato", "banana", "onion", "potato"]:
            print("Initial scheduled fetch:", c)
            update_prices_for_commodity(c, force=True)
    else:
        for c in commodities:
            print("Scheduled refresh:", c)
            update_prices_for_commodity(c, force=True)

scheduler.add_job(
    scheduled_price_refresh,
    'interval',
    hours=_price_refresh_interval_hours(),
    next_run_time=datetime.utcnow(),
    max_instances=1,
    coalesce=True,
)
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

    ai_requested = str(request.args.get('ai') or '').lower() in ('1', 'true', 'yes')
    strict_match = str(request.args.get('strict') or request.args.get('exact') or '').lower() in ('1', 'true', 'yes')
    focus_state = request.args.get('state')
    focus_district = request.args.get('district')
    focus_market = request.args.get('market')

    cache = load_cache()
    if strict_match:
        commodity_match = _build_exact_commodity_match(commodity)
    else:
        commodity_match = resolve_commodity_name(commodity, cache=cache)
    resolved_commodity = commodity_match.get('resolved') or commodity
    resolved_key = commodity_match.get('resolved_key') or norm(commodity)

    data = cache.get("commodities", {}).get(resolved_key, {})
    refresh_needed, refresh_reason, pre_refresh_latest_date = _should_refresh_for_latest_market_day(data)
    refresh_triggered = False

    if refresh_needed:
        fetch_candidates = []
        if commodity_match.get('match_type') in ('prefix', 'fuzzy'):
            candidate_pool = (resolved_commodity,)
        else:
            candidate_pool = (resolved_commodity, commodity)

        seen_fetch_keys = set()
        for candidate in candidate_pool:
            candidate_name = str(candidate or '').strip()
            if not candidate_name:
                continue
            candidate_key = norm(candidate_name)
            if candidate_key in seen_fetch_keys:
                continue
            seen_fetch_keys.add(candidate_key)
            fetch_candidates.append(candidate_name)

        for candidate in fetch_candidates:
            try:
                refresh_triggered = True
                scrape_agmarknet(candidate)
                cache = load_cache()
                refreshed_match = _build_exact_commodity_match(candidate) if strict_match else resolve_commodity_name(candidate, cache=cache)
                candidate_key = refreshed_match.get('resolved_key') or norm(candidate)
                candidate_data = cache.get("commodities", {}).get(candidate_key, {})
                data = candidate_data
                resolved_commodity = refreshed_match.get('resolved') or candidate
                resolved_key = candidate_key
                commodity_match = {
                    'requested': commodity,
                    'requested_key': commodity_match.get('requested_key') or _commodity_lookup_key(commodity),
                    'resolved': resolved_commodity,
                    'resolved_key': resolved_key,
                    'match_type': commodity_match.get('match_type') if norm(candidate) == norm(resolved_commodity) else 'resolved-fetch',
                }

                # After synchronous scrape completes, always re-check latest trading day.
                post_refresh_needed, _, _ = _should_refresh_for_latest_market_day(candidate_data)
                if not post_refresh_needed:
                    break
            except Exception:
                continue

    # Always re-read final resolved key after refresh attempts so response uses persisted state.
    data = cache.get("commodities", {}).get(resolved_key, data if isinstance(data, dict) else {})
    items = _enrich_market_price_items(data.get("items", []))
    price_meta = _price_response_metadata(data)
    latest_trading_date = _latest_price_date_from_items(items)
    market_not_updated_today = True
    if latest_trading_date is not None:
        market_not_updated_today = latest_trading_date < _today_india_date()

    resp = {
        "success": True,
        "data": items,
        "latest_price": price_meta.get('latest_price'),
        "arrival_date": price_meta.get('arrival_date'),
        "price_date": price_meta.get('price_date'),
        "price_freshness": price_meta.get('price_freshness'),
        "fresh_count": price_meta.get('fresh_count'),
        "old_count": price_meta.get('old_count'),
        "fetched_at": price_meta.get('fetched_at'),
        "last_scraped_at": price_meta.get('last_scraped_at'),
        "source": price_meta.get('source'),
        "commodity": {
            "requested": commodity,
            "resolved": resolved_commodity,
            "match_type": commodity_match.get('match_type') or 'exact',
        },
        "refresh_triggered": refresh_triggered,
        "refresh_reason": refresh_reason,
        "market_not_updated_today": market_not_updated_today,
        "last_trading_date": latest_trading_date.isoformat() if latest_trading_date is not None else pre_refresh_latest_date,
    }
    if ai_requested:
        resp['ai'] = gemini_live_price_summary(
            commodity=resolved_commodity,
            items=items,
            state=focus_state,
            district=focus_district,
            market=focus_market
        )
    return jsonify(resp)

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
                for product in prods:
                    if isinstance(product, dict):
                        product['icon'] = _normalize_icon_path(product.get('icon'))
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
        products = []
        for product in pdata.get('products', []):
            item = dict(product)
            item['icon'] = _normalize_icon_path(item.get('icon'))
            products.append(item)
        return jsonify({'success': True, 'products': products})


@app.route('/api/products', methods=['GET'])
def public_products():
    """Public endpoint returning available products for marketplace and buy/sell pages."""
    try:
        if mongo_db is not None:
            coll = mongo_db.get_collection('products')
            prods = list(coll.find({'available': True}, {'_id': 0}))
            for product in prods:
                if isinstance(product, dict):
                    product['icon'] = _normalize_icon_path(product.get('icon'))
            return jsonify({'success': True, 'products': prods})
    except Exception as e:
        print('public_products -> mongo error:', e)

    products_file = os.path.join(os.path.dirname(__file__), 'data', 'products.json')
    try:
        with open(products_file, 'r', encoding='utf-8') as f:
            pdata = json.load(f)
    except Exception:
        pdata = {"products": []}

    available = []
    for product in pdata.get('products', []):
        if not product.get('available', False):
            continue
        item = dict(product)
        item['icon'] = _normalize_icon_path(item.get('icon'))
        available.append(item)
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
                docs = []
                for product in pdata.get('products'):
                    item = product.copy()
                    if 'icon' in item:
                        item['icon'] = _normalize_icon_path(item.get('icon'))
                    docs.append(item)
                coll.insert_many(docs)
            print(f"[PRODUCTS] Updated Mongo 'products' collection (caller={caller})")
            return
    except Exception as e:
        print('write_products -> mongo error:', e)

    products_file = os.path.join(os.path.dirname(__file__), 'data', 'products.json')
    try:
        serializable = {'products': []}
        for product in pdata.get('products', []):
            item = product.copy()
            if 'icon' in item:
                item['icon'] = _normalize_icon_path(item.get('icon'))
            serializable['products'].append(item)
        with open(products_file, 'w', encoding='utf-8') as f:
            json.dump(serializable, f, indent=2)
        print(f"[PRODUCTS] Wrote products.json (caller={caller})")
    except Exception as e:
        print('write_products -> file error:', e)


@app.route('/model/status')
def model_status():
    """Return whether ML model is ready (and load it on demand)."""
    try:
        tf_ver = getattr(tf, '__version__', None) if tf is not None else None
        try:
            import keras as _keras
            keras_ver = getattr(_keras, '__version__', None)
        except Exception:
            keras_ver = None

        if tf is None:
            return jsonify({
                'loaded': False,
                'message': 'TensorFlow not installed',
                'python': sys.executable if 'sys' in globals() else None,
                'tf': tf_ver,
                'keras': keras_ver,
            }), 200

        try:
            load_model_lazy()
            return jsonify({
                'loaded': True,
                'message': 'Model loaded',
                'python': sys.executable if 'sys' in globals() else None,
                'tf': tf_ver,
                'keras': keras_ver,
            }), 200
        except Exception as e:
            return jsonify({
                'loaded': False,
                'message': f'Model not loaded: {e}',
                'python': sys.executable if 'sys' in globals() else None,
                'tf': tf_ver,
                'keras': keras_ver,
            }), 200
    except Exception as e:
        return jsonify({'loaded': False, 'message': f'Error checking model: {e}'}), 200


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
    Accepts query parameters: lat, lon OR q (city name).
    Uses Open-Meteo (free, no API key required).
    Returns the upstream forecast JSON under `forecast` and an `advice` array.
    """
    def _open_meteo_weather_desc(code):
        # https://open-meteo.com/en/docs (WMO weather interpretation codes)
        try:
            c = int(code)
        except Exception:
            return ''
        mapping = {
            0: 'Clear sky',
            1: 'Mainly clear',
            2: 'Partly cloudy',
            3: 'Overcast',
            45: 'Fog',
            48: 'Depositing rime fog',
            51: 'Light drizzle',
            53: 'Moderate drizzle',
            55: 'Dense drizzle',
            61: 'Slight rain',
            63: 'Moderate rain',
            65: 'Heavy rain',
            71: 'Slight snow fall',
            73: 'Moderate snow fall',
            75: 'Heavy snow fall',
            80: 'Rain showers',
            81: 'Heavy rain showers',
            82: 'Violent rain showers',
            95: 'Thunderstorm',
            96: 'Thunderstorm with hail',
            99: 'Thunderstorm with heavy hail',
        }
        return mapping.get(c, f'Weather code {c}')

    def _open_meteo_geocode(name: str):
        url = 'https://geocoding-api.open-meteo.com/v1/search'
        r = requests.get(url, params={'name': name, 'count': 1, 'language': 'en', 'format': 'json'}, timeout=12)
        if r.status_code != 200:
            return None, None, {'error': 'Geocoding failed', 'details': r.text}
        jd = r.json() if r.content else {}
        results = jd.get('results') or []
        if not results:
            return None, None, {'error': 'Could not resolve location name'}
        top = results[0]
        return top.get('latitude'), top.get('longitude'), None

    def _open_meteo_fetch_onecall_like(lat_v, lon_v):
        url = 'https://api.open-meteo.com/v1/forecast'
        params = {
            'latitude': lat_v,
            'longitude': lon_v,
            'hourly': 'temperature_2m,precipitation_probability,windspeed_10m,weathercode',
            'daily': 'temperature_2m_max,temperature_2m_min,precipitation_probability_max,windspeed_10m_max,weathercode',
            'timezone': 'auto',
            'forecast_days': 7,
        }
        r = requests.get(url, params=params, timeout=12)
        if r.status_code != 200:
            return None, {'error': 'Weather provider error', 'details': r.text}

        om = r.json() if r.content else {}
        daily = (om or {}).get('daily') or {}
        times = daily.get('time') or []
        tmax = daily.get('temperature_2m_max') or []
        tmin = daily.get('temperature_2m_min') or []
        pop = daily.get('precipitation_probability_max') or []
        wind = daily.get('windspeed_10m_max') or []
        wcode = daily.get('weathercode') or []

        # Hourly arrays
        hourly = (om or {}).get('hourly') or {}
        h_times = hourly.get('time') or []
        h_temp = hourly.get('temperature_2m') or []
        h_pop = hourly.get('precipitation_probability') or []
        h_wind = hourly.get('windspeed_10m') or []
        h_wcode = hourly.get('weathercode') or []

        out_hourly = []
        for i, t in enumerate(h_times[:48]):
            # open-meteo hourly time is usually like 2026-03-06T01:00
            try:
                dt = int(time.mktime(datetime.strptime(t, '%Y-%m-%dT%H:%M').timetuple()))
            except Exception:
                try:
                    dt = int(time.mktime(datetime.fromisoformat(t).timetuple()))
                except Exception:
                    dt = None

            try:
                pop_pct = h_pop[i] if i < len(h_pop) else None
                pop_frac = (float(pop_pct) / 100.0) if pop_pct is not None else 0
            except Exception:
                pop_frac = 0

            code_i = h_wcode[i] if i < len(h_wcode) else None
            out_hourly.append({
                'dt': dt,
                'temp': (h_temp[i] if i < len(h_temp) else None),
                'pop': pop_frac,
                'wind_speed': (h_wind[i] if i < len(h_wind) else None),
                'weather': [{'id': 0, 'description': _open_meteo_weather_desc(code_i)}],
                'weathercode': code_i,
            })

        out_daily = []
        for i, d in enumerate(times[:7]):
            try:
                dt = int(time.mktime(datetime.strptime(d, '%Y-%m-%d').timetuple()))
            except Exception:
                dt = None

            try:
                pop_pct = pop[i] if i < len(pop) else None
                pop_frac = (float(pop_pct) / 100.0) if pop_pct is not None else 0
            except Exception:
                pop_frac = 0

            code_i = wcode[i] if i < len(wcode) else None
            out_daily.append({
                'dt': dt,
                'temp': {
                    'max': (tmax[i] if i < len(tmax) else None),
                    'min': (tmin[i] if i < len(tmin) else None),
                },
                'pop': pop_frac,
                'wind_speed': (wind[i] if i < len(wind) else None),
                # Keep a OneCall-like weather object so the frontend can render `description`.
                'weather': [{'id': 0, 'description': _open_meteo_weather_desc(code_i)}],
                'weathercode': code_i,
            })

        payload = {
            'provider': 'open-meteo',
            'latitude': (om or {}).get('latitude'),
            'longitude': (om or {}).get('longitude'),
            'timezone': (om or {}).get('timezone'),
            'hourly': out_hourly,
            'daily': out_daily,
        }
        return payload, None

    lat = request.args.get('lat')
    lon = request.args.get('lon')
    q = request.args.get('q')
    try:
        # Open-Meteo: free, no API key required
        if (not lat or not lon) and q:
            lat2, lon2, err = _open_meteo_geocode(q)
            if err:
                return jsonify(err), 502
            lat, lon = lat2, lon2

        if not lat or not lon:
            return jsonify({'error': 'Provide lat & lon or q (city name) as query parameters.'}), 400

        payload, err = _open_meteo_fetch_onecall_like(lat, lon)
        if err:
            return jsonify(err), 502

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


@app.route('/api/user/profile', methods=['POST'])
@login_required
def update_profile():
    data = request.get_json() or {}
    profile = normalize_profile_payload(data.get('profile') or data)
    user_email = session.get('user')

    updated = update_user_record(user_email, lambda user: merge_user_profile(user, profile))
    if not updated:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    return jsonify({'success': True, 'user': {'email': user_email, 'info': updated}})


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


@app.route('/admin/api/pending_listings', methods=['GET'])
def admin_api_pending_listings():
    """Return pending sell listings and pending sell price-change requests for admin review."""
    x = require_admin()
    if x:
        return x
    orders = read_orders()
    pending = []
    for o in orders:
        if (o.get('type') or 'sell').lower() != 'sell':
            continue
        price_change_request = o.get('price_change_request') or {}
        if (o.get('status') == 'pending'):
            item = dict(o)
            item['review_type'] = 'new-listing'
            pending.append(item)
        elif (price_change_request.get('status') == 'pending'):
            item = dict(o)
            item['review_type'] = 'price-change'
            pending.append(item)
    # Sanitize _id for JSON serialization
    out = []
    for o in pending:
        item = {k: v for k, v in o.items() if k != '_id'}
        out.append(item)
    return jsonify({'success': True, 'listings': out})


@app.route('/admin/api/listing/<int:listing_id>/approve', methods=['POST'])
def admin_api_approve_listing(listing_id):
    """Approve a pending sell listing or approve a pending sell price change request."""
    x = require_admin()
    if x:
        return x
    try:
        listing = get_order_by_id(listing_id, include_image=True)
        if not listing:
            return jsonify({'success': False, 'message': 'Listing not found'}), 404

        price_change_request = listing.get('price_change_request') or {}
        if price_change_request.get('status') == 'pending':
            requested_price = price_change_request.get('requested_price')
            update_order_by_id(listing_id, {'price': requested_price}, unset_fields=['price_change_request'])
            recipient_email = _resolve_notification_email(listing, 'user', 'contact')
            if recipient_email:
                email_content = _build_rich_email_content(
                    'Price Change Approved',
                    'Your requested listing price has been approved by the admin team and is now live on the marketplace.',
                    details=[
                        ('Product', listing.get('product') or 'Your listing'),
                        ('Listing ID', listing.get('id')),
                        ('Previous Price', _email_format_currency(listing.get('price'))),
                        ('Approved Price', _email_format_currency(requested_price)),
                        ('Quantity', _email_format_quantity(listing.get('quantity'))),
                        ('Seller Account', listing.get('user')),
                        ('Reason', price_change_request.get('reason') or 'Not provided'),
                    ],
                    badge='Price Approved',
                    accent='green',
                )
                _send_notification_email(
                    recipient_email,
                    'AgriAI360 - Price Change Approved',
                    email_content['text'],
                    html_body=email_content['html'],
                )
            return jsonify({'success': True})

        update_order_by_id(listing_id, {'status': 'approved'})
        if listing:
            user_email = _resolve_notification_email(listing, 'user', 'contact')
        else:
            user_email = None
        if user_email:
            product = listing.get('product', 'your listing')
            email_content = _build_rich_email_content(
                'Listing Approved',
                'Your product has been approved and is now visible to buyers in the marketplace.',
                details=[
                    ('Product', product),
                    ('Listing ID', listing.get('id')),
                    ('Quantity', _email_format_quantity(listing.get('quantity'))),
                    ('Price', _email_format_currency(listing.get('price'))),
                    ('Location', listing.get('location') or 'Not provided'),
                    ('Seller Account', listing.get('user')),
                    ('Notes', listing.get('notes') or 'Not provided'),
                    ('Submitted At', _email_format_timestamp(listing.get('timestamp'))),
                ],
                badge='Listing Approved',
                accent='green',
            )
            _send_notification_email(
                user_email,
                'AgriAI360 - Your Listing Has Been Approved!',
                email_content['text'],
                html_body=email_content['html'],
            )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/admin/api/listing/<int:listing_id>/reject', methods=['POST'])
def admin_api_reject_listing(listing_id):
    """Reject a pending sell listing or reject a pending sell price change request."""
    x = require_admin()
    if x:
        return x
    try:
        listing = get_order_by_id(listing_id, include_image=True)
        if not listing:
            return jsonify({'success': False, 'message': 'Listing not found'}), 404

        price_change_request = listing.get('price_change_request') or {}
        if price_change_request.get('status') == 'pending':
            update_order_by_id(listing_id, {}, unset_fields=['price_change_request'])
            recipient_email = _resolve_notification_email(listing, 'user', 'contact')
            if recipient_email:
                email_content = _build_rich_email_content(
                    'Price Change Rejected',
                    'Your requested price update was not approved. You can review the listing and submit another request later.',
                    details=[
                        ('Product', listing.get('product') or 'Your listing'),
                        ('Listing ID', listing.get('id')),
                        ('Current Price', _email_format_currency(listing.get('price'))),
                        ('Requested Price', _email_format_currency(price_change_request.get('requested_price'))),
                        ('Quantity', _email_format_quantity(listing.get('quantity'))),
                        ('Seller Account', listing.get('user')),
                        ('Reason', price_change_request.get('reason') or 'Not provided'),
                    ],
                    badge='Price Rejected',
                    accent='red',
                )
                _send_notification_email(
                    recipient_email,
                    'AgriAI360 - Price Change Rejected',
                    email_content['text'],
                    html_body=email_content['html'],
                )
            return jsonify({'success': True})

        delete_order_by_id(listing_id)
        if listing:
            user_email = _resolve_notification_email(listing, 'user', 'contact')
        else:
            user_email = None
        if user_email:
            product = listing.get('product', 'your listing')
            email_content = _build_rich_email_content(
                'Listing Not Approved',
                'Your sell listing was not approved by the admin team. Please review the details and submit it again if needed.',
                details=[
                    ('Product', product),
                    ('Listing ID', listing.get('id')),
                    ('Quantity', _email_format_quantity(listing.get('quantity'))),
                    ('Price', _email_format_currency(listing.get('price'))),
                    ('Location', listing.get('location') or 'Not provided'),
                    ('Seller Account', listing.get('user')),
                    ('Notes', listing.get('notes') or 'Not provided'),
                ],
                badge='Listing Rejected',
                accent='red',
            )
            _send_notification_email(
                user_email,
                'AgriAI360 - Listing Update',
                email_content['text'],
                html_body=email_content['html'],
            )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


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

    order_info = None
    if updates:
        orders = read_orders()
        order_info = next((o for o in orders if int(o.get('id', 0)) == order_id), None)

    ok = update_order_by_id(order_id, updates)
    if ok:
        email_snapshot = dict(order_info or {})
        email_snapshot.update(updates)
        order_type_value = (email_snapshot.get('type') or '').lower()
        if order_type_value == 'sell' and status in ('completed', 'cancelled', 'rejected'):
            _apply_terminal_listing_state(order_id, status=status)
        changed_fields = []
        for field in ('status', 'price', 'quantity'):
            if field in updates:
                changed_fields.append(field)

        user_email = _resolve_notification_email(email_snapshot, 'user', 'buyer_email', 'contact')
        if email_snapshot and user_email and changed_fields:
            product = email_snapshot.get('product', 'your order')
            order_type = (email_snapshot.get('type') or 'order').capitalize()
            status_value = str(email_snapshot.get('status') or 'Updated').capitalize()
            if changed_fields == ['status']:
                title = f'{order_type} Status Updated'
                message = f'Your {order_type.lower()} status has been updated by the admin team.'
                subject = f'AgriAI360 - {order_type} Status Update'
            else:
                title = f'{order_type} Updated'
                message = 'Your order details were updated by the admin team. Review the latest information below.'
                subject = f'AgriAI360 - {order_type} Update'

            email_content = _build_rich_email_content(
                title,
                message,
                details=[
                    ('Order Type', order_type),
                    ('Product', product),
                    ('Order ID', email_snapshot.get('id') or order_id),
                    ('Listing ID', email_snapshot.get('listing_id') or 'Not linked'),
                    ('Status', status_value),
                    ('Quantity', _email_format_quantity(email_snapshot.get('quantity'))),
                    ('Price', _email_format_currency(email_snapshot.get('price'))),
                    ('Seller / Account', email_snapshot.get('seller') or email_snapshot.get('user')),
                    ('Location', email_snapshot.get('location') or 'Not provided'),
                    ('Notes', email_snapshot.get('notes') or 'Not provided'),
                    ('Updated Fields', ', '.join(field.replace('_', ' ').title() for field in changed_fields)),
                    ('Created At', _email_format_timestamp(email_snapshot.get('timestamp'))),
                ],
                badge=f'{order_type} Update',
                accent='blue' if order_type_value == 'buy' else 'amber',
            )
            _send_notification_email(
                user_email,
                subject,
                email_content['text'],
                html_body=email_content['html'],
            )
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
        db["commodities"][key] = {"fetched_at": None, "items": [], "source": None}
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

@app.route('/favicon.ico')
def serve_favicon():
    return send_from_directory('static/icons', 'logo.png', mimetype='image/png')

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
    # Optional: Prime cache with common commodities.
    # Disabled by default to keep startup fast on hosted platforms.
    if str(os.environ.get('SEED_PRICES_ON_START', '0')).lower() in ('1', 'true', 'yes'):
        def _seed_prices_bg():
            try:
                for c in ["tomato", "banana", "onion", "potato"]:
                    try:
                        update_prices_for_commodity(c)
                        time.sleep(1)
                    except Exception as e:
                        print("Initial fetch error for", c, ":", e)
            except Exception as e:
                print("Initial seeding error:", e)

        threading.Thread(target=_seed_prices_bg, daemon=True).start()

    # Render/hosted platforms provide PORT; default to 5000 for local.
    try:
        port = int(os.environ.get('PORT', '5000'))
    except Exception:
        port = 5000
    debug = str(os.environ.get('FLASK_DEBUG', '0')).lower() in ('1', 'true', 'yes')
    app.run(debug=debug, host="0.0.0.0", port=port, use_reloader=False)