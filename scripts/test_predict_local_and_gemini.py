import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import app as app_module


def post(client, path: str):
    img_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'icons', 'tomato.png')
    img_path = os.path.abspath(img_path)

    with open(img_path, 'rb') as f:
        data = {'image': (f, 'tomato.png')}
        resp = client.post(path, data=data, content_type='multipart/form-data')

    print(f"\n{path} -> {resp.status_code}")
    payload = resp.get_json(silent=True)
    if payload is not None:
        print(json.dumps(payload, indent=2)[:2000])
    else:
        print(resp.data[:500])


def main():
    client = app_module.app.test_client()
    post(client, '/predict')
    post(client, '/predict?ai=1')


if __name__ == '__main__':
    main()
