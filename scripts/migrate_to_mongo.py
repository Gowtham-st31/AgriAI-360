"""
One-shot migration script to import existing JSON files into MongoDB collections.
Run with MONGODB_URI set (and optional MONGODB_DB). Example:

$ set MONGODB_URI=mongodb+srv://user:pass@cluster0.mongodb.net/mydb
$ python scripts/migrate_to_mongo.py

This will import:
 - data/users.json -> users collection
 - data/orders.json -> orders collection
 - data/products.json -> products collection
 - data/prices.json -> prices collection
 - data/today_deals.json -> today_deals collection

Be careful: this script will replace existing collections with the imported data.
"""
import os
import json
import sys
import hashlib
from datetime import datetime, timedelta, timezone

try:
    from pymongo import MongoClient
except Exception as e:
    print('pymongo not installed. Install requirements first:', e)
    sys.exit(1)

MONGODB_URI = os.environ.get('MONGODB_URI')
if not MONGODB_URI:
    print('Set MONGODB_URI environment variable to your Atlas URI and rerun.')
    sys.exit(1)

client = MongoClient(MONGODB_URI)
# determine DB
db_name = os.environ.get('MONGODB_DB')
if not db_name:
    try:
        db_name = client.get_default_database().name
    except Exception:
        db_name = 'agri'

db = client[db_name]
print('Connected to MongoDB, database:', db_name)

BASE = os.path.join(os.path.dirname(__file__), '..')
DATA_DIR = os.path.join(BASE, 'data')

mappings = [
    ('users.json', 'users'),
    ('orders.json', 'orders'),
    ('products.json', 'products'),
    ('prices.json', 'prices'),
    ('today_deals.json', 'today_deals'),
]

INDIA_TZ = timezone(timedelta(hours=5, minutes=30))


def _parse_arrival_date(value):
    text = str(value or '').strip()
    if not text:
        return None
    for fmt in (
        '%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%y', '%d-%b-%Y',
        '%d %b %Y', '%d %B %Y', '%m/%d/%Y'
    ):
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            continue
    return None


def _normalize_price_date(value):
    parsed = _parse_arrival_date(value)
    return parsed.date().isoformat() if parsed else ''


def _price_freshness(value):
    parsed = _parse_arrival_date(value)
    if parsed is None:
        return 'Old'
    return 'Fresh' if parsed.date() == datetime.now(INDIA_TZ).date() else 'Old'


def _enrich_items(items):
    out = []
    for item in (items or []):
        row = dict(item or {})
        row['price_date'] = _normalize_price_date(row.get('arrival_date'))
        row['price_freshness'] = _price_freshness(row.get('arrival_date'))
        out.append(row)
    return out


def _json_sha256(payload) -> str:
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

for fname, collname in mappings:
    path = os.path.join(DATA_DIR, fname)
    if not os.path.exists(path):
        print(f"Skipped {fname}: file not found")
        continue
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Failed to read {path}: {e}")
        continue

    coll = db[collname]
    # replace existing collection
    coll.delete_many({})
    to_insert = None
    if isinstance(data, dict) and 'users' in data and collname == 'users':
        to_insert = data.get('users', [])
    elif isinstance(data, dict) and 'products' in data and collname == 'products':
        to_insert = data.get('products', [])
    elif isinstance(data, dict) and 'commodities' in data and collname == 'prices':
        # price cache schema v2: one document per commodity + one metadata document
        now_iso = datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
        imported = 0
        commodities = data.get('commodities') or {}
        for key_raw, entry_raw in commodities.items():
            key = str(key_raw or '').strip().lower()
            if not key:
                continue
            entry = entry_raw if isinstance(entry_raw, dict) else {}
            items = _enrich_items(entry.get('items') or [])
            doc = {
                'key': key,
                'source': entry.get('source'),
                'fetched_at': entry.get('fetched_at'),
                'last_scraped_at': entry.get('last_scraped_at') or entry.get('fetched_at') or now_iso,
                'items': items,
                'items_hash': _json_sha256(items),
                'updated_at': now_iso,
            }
            coll.update_one({'key': key}, {'$set': doc, '$setOnInsert': {'created_at': now_iso}}, upsert=True)
            imported += 1

        coll.update_one(
            {'_id': '__meta__'},
            {
                '$set': {
                    '_id': '__meta__',
                    'schema_version': 2,
                    'last_updated': data.get('last_updated') or now_iso,
                    'last_scraped_at': data.get('last_scraped_at') or data.get('last_updated') or now_iso,
                    'updated_at': now_iso,
                },
                '$setOnInsert': {'created_at': now_iso},
            },
            upsert=True,
        )
        coll.create_index('key', unique=True, sparse=True)
        coll.create_index('fetched_at')
        coll.create_index('last_scraped_at')
        coll.create_index('items_hash')
        print(f"Imported {fname} into collection {collname} ({imported} commodity docs + metadata)")
        continue
    elif isinstance(data, list) and collname == 'today_deals':
        # store deals list as a single document
        ids = []
        for x in data:
            try:
                ids.append(int(x))
            except Exception:
                pass
        coll.insert_one({'_id': 'today_deals', 'ids': ids})
        print(f"Imported {fname} into collection {collname} (1 document)")
        continue
    else:
        # data is expected to be a list for orders
        to_insert = data if isinstance(data, list) else [data]

    if to_insert:
        # Ensure we don't insert Mongo ObjectId collisions; strip _id if present
        docs = []
        for d in to_insert:
            if isinstance(d, dict) and '_id' in d:
                d = {k: v for k, v in d.items() if k != '_id'}
            docs.append(d)
        if docs:
            coll.insert_many(docs)
            print(f"Imported {len(docs)} documents from {fname} into {collname}")
        else:
            print(f"No documents to import from {fname}")

print('Migration complete.')
