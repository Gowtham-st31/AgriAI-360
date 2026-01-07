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
        # store cache object as single document
        coll.insert_one({'cache': data})
        print(f"Imported {fname} into collection {collname} (1 document)")
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
