import requests
import prints
from concurrent.futures import ThreadPoolExecutor, as_completed
import toml
import os
import hashlib

def get_sha1(file_path):
    """计算文件的SHA1哈希值"""
    #prints.prints("info",f"Verify SHA1 of {file_path}")
    sha1_hash = hashlib.sha1()
    with open(file_path, 'rb') as f:
        while chunk := f.read(4096):
            sha1_hash.update(chunk)
    return sha1_hash.hexdigest()
def download(url, save_path, size, sha1,PassCheck, config):
    max_retries = config["launcher"]["download_max_retries"]
    timeout = config["launcher"]["download_time_out"]
    if os.path.exists(save_path) and PassCheck:
        if (os.path.getsize(save_path) == size) and get_sha1(save_path) == sha1:
            return ["success", f"Download complete: {url}"]
    for attempt in range(max_retries + 1):
        try:
            # 使用 requests 下载文件
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()  # 检查请求是否成功
            prints.prints("info", f"Downloading: {url} to {save_path} Size: {size} (Attempt {attempt + 1})")
            with open(save_path, "wb") as f:
                f.write(response.content)
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
    
    # 不会执行到这里，但保留返回语句以防万一
    return ["error", f"Max retries exceeded: {url}"]

def main(url_list, threads=1,PassCheck=False):
    results = []
    toml_config = toml.load("config.toml")
    # 自动调整线程数
    if toml_config["launcher"]["auto_set_thread"] and threads > len(url_list):
        threads = len(url_list)
    
    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = []
        for i in url_list:
            futures.append(
                executor.submit(
                    download, i, url_list[i].get("save"), url_list[i].get("size"),
                    url_list[i].get("sha1"),PassCheck, toml_config
                )
            )
        
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
    
    return results
