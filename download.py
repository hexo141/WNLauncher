import requests
import prints
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import hashlib
import time
from config_loader import load_config
import threading
from requests.adapters import HTTPAdapter
try:
    from urllib3.util.retry import Retry
except Exception:
    Retry = None

_TOML_CONFIG = None
_thread_local = threading.local()


def get_sha1(file_path):
    """计算文件的SHA1哈希值"""
    #prints.prints("info",f"Verify SHA1 of {file_path}")
    sha1_hash = hashlib.sha1()
    with open(file_path, 'rb') as f:
        while chunk := f.read(4096):
            sha1_hash.update(chunk)
    return sha1_hash.hexdigest()

def _get_session(timeout):
    sess = getattr(_thread_local, "session", None)
    if sess is not None:
        return sess
    sess = requests.Session()
    # Configure HTTPAdapter for connection pooling
    adapter_kwargs = {"pool_connections": 50, "pool_maxsize": 100}
    if Retry is not None:
        retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry, **adapter_kwargs)
    else:
        adapter = HTTPAdapter(**adapter_kwargs)
    sess.mount('http://', adapter)
    sess.mount('https://', adapter)
    _thread_local.session = sess
    return sess

def download(url, save_path, size, sha1, PassCheck, config):
    max_retries = config["launcher"]["download_max_retries"]
    timeout = config["launcher"]["download_time_out"]

    # 预先存在校验
    if os.path.exists(save_path) and PassCheck:
        try:
            if (size is None or os.path.getsize(save_path) == size) and (sha1 is None or get_sha1(save_path) == sha1):
                return ["success", f"Download complete: {url}"]
        except Exception:
            # 如果读取失败，则继续重新下载
            pass

    for attempt in range(max_retries + 1):
        try:
            # 确保保存目录存在
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            # 流式下载并在写入时校验哈希
            hasher = hashlib.sha1() if sha1 else None
            bytes_written = 0

            session = _get_session(timeout)
            with session.get(url, timeout=timeout, stream=True) as response:
                response.raise_for_status()
                prints.prints("info", f"Downloading: {url} to {save_path} Size: {size} (Attempt {attempt + 1})")

                with open(save_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=65536):
                        if not chunk:
                            continue
                        f.write(chunk)
                        bytes_written += len(chunk)
                        if hasher:
                            hasher.update(chunk)

            # 大小校验（如果提供）
            if size is not None and bytes_written != int(size):
                prints.prints("warning", f"Size mismatch for {url}: expected {size}, got {bytes_written}")
                try:
                    os.remove(save_path)
                except Exception:
                    pass
                raise IOError("size mismatch")

            # 哈希校验（如果提供）
            if sha1 is not None:
                calculated_sha1 = hasher.hexdigest()
                if calculated_sha1 != sha1:
                    prints.prints("warning", f"SHA1 mismatch for {url}: expected {sha1}, got {calculated_sha1}")
                    try:
                        os.remove(save_path)
                    except Exception:
                        pass
                    raise IOError("sha1 mismatch")

            return ["success", f"Download complete: {url}"]
        
        except Exception as e:
            if attempt == max_retries:
                prints.prints("error", f"Download failed after {max_retries} attempts: {url} - {e}")
                return ["error", f"Max retries exceeded: {url} - {e}"]
            else:
                if "timed out" in str(e):
                    error_type = "Timed out"
                else:
                    error_type = "Error"
                prints.prints("warning", f"{error_type}, retrying... (Attempt {attempt + 1}/{max_retries}) - {e}")
                # 指数退避，最多等待10秒
                time.sleep(min(2 ** attempt, 10))
    
    # 不会执行到这里，但保留返回语句以防万一
    return ["error", f"Max retries exceeded: {url}"]


def main(url_list, threads=1, PassCheck=False):
    results = []
    global _TOML_CONFIG
    if _TOML_CONFIG is None:
        _TOML_CONFIG = load_config()
    toml_config = _TOML_CONFIG

    # 自动调整线程数
    if toml_config["launcher"]["auto_set_thread"] and threads > len(url_list):
        threads = len(url_list)
    
    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = []
        for i in url_list:
            futures.append(
                executor.submit(
                    download, i, url_list[i].get("save"), url_list[i].get("size"),
                    url_list[i].get("sha1"), PassCheck, toml_config
                )
            )
        
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
    
    return results
