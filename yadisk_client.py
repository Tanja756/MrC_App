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
        cfg = load_config()
        refresh_token = cfg.get('Yandex', 'refresh_token', fallback='')
        if not refresh_token:
            logger.warning("No refresh token available")
            return False
        try:
            resp = requests.post("https://oauth.yandex.ru/token", data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": YANDEX_CLIENT_ID,
                "client_secret": YANDEX_CLIENT_SECRET,
            }, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                self.token = data.get('access_token')
                cfg.set('Yandex', 'token', self.token)
                if 'refresh_token' in data:
                    cfg.set('Yandex', 'refresh_token', data['refresh_token'])
                from config import save_config
                save_config(cfg)
                self._session.headers.update({"Authorization": f"OAuth {self.token}"})
                logger.info("Yandex token refreshed")
                return True
            else:
                logger.error(f"Token refresh failed: {resp.status_code} {resp.text[:200]}")
                return False
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return False

    def _request(self, method, url, **kwargs):
        kwargs.setdefault('timeout', 30)
        for attempt in range(2):
            try:
                resp = self._session.request(method, url, **kwargs)
                if resp.status_code == 401 and attempt == 0:
                    if self._refresh_token():
                        resp = self._session.request(method, url, **kwargs)
                return resp
            except requests.RequestException as e:
                logger.error(f"Request error: {e}")
                if attempt == 0:
                    continue
                raise
        return None

    def ensure_folder(self, path):
        parts = [p for p in path.strip('/').split('/')]
        current = ''
        for part in parts:
            current = f"{current}/{part}" if current else part
            resp = self._request('PUT', f"{API_BASE}/resources", params={'path': f'/{current}'})
            if resp and resp.status_code not in (201, 409):
                logger.warning(f"Failed to ensure folder {current}: {resp.status_code}")

    def upload_json(self, remote_path, data):
        remote_path = f'/{remote_path.strip("/")}'
        self.ensure_folder('/'.join(remote_path.strip('/').split('/')[:-1]))
        resp = self._request('DELETE', f"{API_BASE}/resources", params={'path': remote_path, 'permanently': 'false'})
        resp = self._request('GET', f"{API_BASE}/resources/upload", params={'path': remote_path, 'overwrite': 'true'})
        if not resp or resp.status_code != 200:
            logger.error(f"Failed to get upload URL for {remote_path}: {resp.status_code if resp else 'no response'}")
            return False
        upload_url = resp.json().get('href')
        if not upload_url:
            return False
        body = json.dumps(data, ensure_ascii=False, default=str).encode('utf-8')
        up_resp = requests.put(upload_url, data=body, timeout=30)
        if up_resp.status_code in (201, 202):
            return True
        logger.error(f"Upload failed: {up_resp.status_code} {up_resp.text[:200]}")
        return False

    def download_json(self, remote_path):
        remote_path = f"/{remote_path.strip('/')}"
        resp = self._request('GET', f"{API_BASE}/resources/download", params={'path': remote_path})
        if not resp or resp.status_code != 200:
            return None
        download_url = resp.json().get('href')
        if not download_url:
            return None
        dl_resp = requests.get(download_url, timeout=30)
        if dl_resp.status_code == 200:
            return dl_resp.json()
        return None

    def list_folder(self, remote_path):
        remote_path = f"/{remote_path.strip('/')}"
        items = []
        offset = 0
        while True:
            resp = self._request('GET', f"{API_BASE}/resources", params={
                'path': remote_path, 'offset': offset, 'limit': 100
            })
            if not resp or resp.status_code != 200:
                break
            data = resp.json()
            embedded = data.get('_embedded', {})
            items.extend(embedded.get('items', []))
            if embedded.get('offset', 0) + embedded.get('limit', 0) >= embedded.get('total', 0):
                break
            offset += embedded.get('limit', 100)
        return items

    def file_exists(self, remote_path):
        remote_path = f"/{remote_path.strip('/')}"
        resp = self._request('GET', f"{API_BASE}/resources", params={'path': remote_path})
        return resp is not None and resp.status_code == 200