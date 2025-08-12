import threading
from typing import Any, Dict, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter

try:
    from urllib3.util.retry import Retry
except Exception:
    Retry = None

_thread_local = threading.local()


def _get_session() -> requests.Session:
    sess = getattr(_thread_local, "session", None)
    if sess is not None:
        return sess
    sess = requests.Session()
    adapter_kwargs = {"pool_connections": 50, "pool_maxsize": 100}

    if Retry is not None:
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"],
        )
        adapter = HTTPAdapter(max_retries=retry, **adapter_kwargs)
    else:
        adapter = HTTPAdapter(**adapter_kwargs)

    sess.mount("http://", adapter)
    sess.mount("https://", adapter)
    _thread_local.session = sess
    return sess


def get(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: float = 10.0,
) -> Tuple[str, requests.Response]:
    session = _get_session()
    resp = session.get(url, headers=headers, params=params, timeout=timeout)
    resp.raise_for_status()
    return ("success", resp)


def fetch_json(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: float = 10.0,
) -> Tuple[str, Any]:
    status, resp = get(url, headers=headers, params=params, timeout=timeout)
    try:
        return (status, resp.json())
    except Exception as e:
        return ("error", f"JSON parse error: {e}")


def fetch_text(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: float = 10.0,
    encoding: Optional[str] = None,
) -> Tuple[str, str]:
    status, resp = get(url, headers=headers, params=params, timeout=timeout)
    if encoding:
        resp.encoding = encoding
    return (status, resp.text)