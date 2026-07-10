import os
import json
import logging
import requests
from config import load_config, YANDEX_CLIENT_ID, YANDEX_CLIENT_SECRET

logger = logging.getLogger(__name__)

API_BASE = "https://cloud-api.yandex.net/v1/disk"


class YandexDiskClient:
    def __init__(self, token=None):
        self.token = token
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"OAuth {self.token}",
            "User-Agent": "MrC_App/1.0"
        })
        self._load_token()

    def _load_token(self):
        if not self.token:
            cfg = load_config()
            self.token = cfg.get('Yandex', 'token', fallback='')
            if self.token:
                self._session.headers.update({"Authorization": f"OAuth {self.token}"})

    def _refresh_token(self):
        print(f"[YADISK] _refresh_token: attempting token refresh")
        cfg = load_config()
        refresh_token = cfg.get('Yandex', 'refresh_token', fallback='')
        if not refresh_token:
            logger.warning("No refresh token available")
            print(f"[YADISK] _refresh_token: no refresh token")
            return False
        try:
            resp = requests.post("https://oauth.yandex.ru/token", data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": YANDEX_CLIENT_ID,
                "client_secret": YANDEX_CLIENT_SECRET,
            }, timeout=15)
            print(f"[YADISK] _refresh_token: status={resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                self.token = data.get('access_token')
                cfg.set('Yandex', 'token', self.token)
                if 'refresh_token' in data:
                    cfg.set('Yandex', 'refresh_token', data['refresh_token'])
                    print(f"[YADISK] _refresh_token: got new refresh_token")
                from config import save_config
                save_config(cfg)
                self._session.headers.update({"Authorization": f"OAuth {self.token}"})
                logger.info("Yandex token refreshed")
                print(f"[YADISK] _refresh_token: success")
                return True
            else:
                logger.error(f"Token refresh failed: {resp.status_code} {resp.text[:200]}")
                print(f"[YADISK] _refresh_token: failed: {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            print(f"[YADISK] _refresh_token: error: {e}")
            return False

    def _request(self, method, url, **kwargs):
        kwargs.setdefault('timeout', 30)
        print(f"[YADISK] _request: {method} {url[:120]}")
        for attempt in range(2):
            try:
                resp = self._session.request(method, url, **kwargs)
                print(f"[YADISK] _request: attempt={attempt}, status={resp.status_code}")
                if resp.status_code == 401 and attempt == 0:
                    print(f"[YADISK] _request: got 401, refreshing token...")
                    if self._refresh_token():
                        resp = self._session.request(method, url, **kwargs)
                        print(f"[YADISK] _request: retry status={resp.status_code}")
                return resp
            except requests.RequestException as e:
                logger.error(f"Request error: {e}")
                print(f"[YADISK] _request: error={e}")
                if attempt == 0:
                    continue
                raise
        return None

    def ensure_folder(self, path):
        parts = [p for p in path.strip('/').split('/')]
        current = ''
        for part in parts:
            current = f"{current}/{part}" if current else part
            print(f"[YADISK] ensure_folder: {current}")
            resp = self._request('PUT', f"{API_BASE}/resources", params={'path': f'/{current}'})
            if resp and resp.status_code not in (201, 409):
                logger.warning(f"Failed to ensure folder {current}: {resp.status_code}")

    def upload_json(self, remote_path, data):
        remote_path = f'/{remote_path.strip("/")}'
        print(f"[YADISK] upload_json: path={remote_path}, data_size={len(json.dumps(data, ensure_ascii=False, default=str))}")
        self.ensure_folder('/'.join(remote_path.strip('/').split('/')[:-1]))
        resp = self._request('DELETE', f"{API_BASE}/resources", params={'path': remote_path, 'permanently': 'false'})
        resp = self._request('GET', f"{API_BASE}/resources/upload", params={'path': remote_path, 'overwrite': 'true'})
        if not resp or resp.status_code != 200:
            logger.error(f"Failed to get upload URL for {remote_path}: {resp.status_code if resp else 'no response'}")
            print(f"[YADISK] upload_json: failed to get upload URL, status={resp.status_code if resp else 'None'}")
            return False
        upload_url = resp.json().get('href')
        if not upload_url:
            print(f"[YADISK] upload_json: no href in upload response")
            return False
        body = json.dumps(data, ensure_ascii=False, default=str).encode('utf-8')
        print(f"[YADISK] upload_json: uploading {len(body)} bytes...")
        up_resp = requests.put(upload_url, data=body, timeout=30)
        print(f"[YADISK] upload_json: upload status={up_resp.status_code}")
        if up_resp.status_code in (201, 202):
            print(f"[YADISK] upload_json: upload OK")
            return True
        logger.error(f"Upload failed: {up_resp.status_code} {up_resp.text[:200]}")
        print(f"[YADISK] upload_json: upload failed: {up_resp.status_code}")
        return False

    def download_json(self, remote_path):
        remote_path = f"/{remote_path.strip('/')}"
        print(f"[YADISK] download_json: path={remote_path}")
        resp = self._request('GET', f"{API_BASE}/resources/download", params={'path': remote_path})
        if not resp or resp.status_code != 200:
            print(f"[YADISK] download_json: failed to get download URL, status={resp.status_code if resp else 'None'}")
            return None
        download_url = resp.json().get('href')
        if not download_url:
            print(f"[YADISK] download_json: no href in response")
            return None
        print(f"[YADISK] download_json: got href, fetching...")
        dl_resp = requests.get(download_url, timeout=30)
        print(f"[YADISK] download_json: download status={dl_resp.status_code}, content_length={len(dl_resp.content)}")
        if dl_resp.status_code == 200:
            return dl_resp.json()
        print(f"[YADISK] download_json: download failed with status {dl_resp.status_code}")
        return None

    def list_folder(self, remote_path):
        remote_path = f"/{remote_path.strip('/')}"
        print(f"[YADISK] list_folder: path={remote_path}")
        items = []
        offset = 0
        while True:
            resp = self._request('GET', f"{API_BASE}/resources", params={
                'path': remote_path, 'offset': offset, 'limit': 100
            })
            if not resp or resp.status_code != 200:
                print(f"[YADISK] list_folder: failed at offset={offset}, status={resp.status_code if resp else 'None'}")
                break
            data = resp.json()
            embedded = data.get('_embedded', {})
            batch = embedded.get('items', [])
            items.extend(batch)
            print(f"[YADISK] list_folder: offset={offset}, batch={len(batch)}, total={embedded.get('total', 0)}")
            if embedded.get('offset', 0) + embedded.get('limit', 0) >= embedded.get('total', 0):
                break
            offset += embedded.get('limit', 100)
        print(f"[YADISK] list_folder: total items={len(items)}")
        return items

    def file_exists(self, remote_path):
        remote_path = f"/{remote_path.strip('/')}"
        print(f"[YADISK] file_exists: path={remote_path}")
        resp = self._request('GET', f"{API_BASE}/resources", params={'path': remote_path})
        exists = resp is not None and resp.status_code == 200
        print(f"[YADISK] file_exists: {exists}")
        return exists