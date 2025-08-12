import os
import datetime
import inspect
import threading
import time

_DEFAULT_LOG_DIR = None


def _get_default_log_dir():
    """Lazily load log directory from config.toml with a safe fallback."""
    global _DEFAULT_LOG_DIR
    if _DEFAULT_LOG_DIR is not None:
        return _DEFAULT_LOG_DIR
    try:
        import toml
        config = toml.load('config.toml')
        _DEFAULT_LOG_DIR = config["launcher"]["log_path"]
    except Exception:
        _DEFAULT_LOG_DIR = "log/launcher/"
    return _DEFAULT_LOG_DIR


def prints(level, message, filepath=None):
    """
    输出格式化日志信息到指定文件。

    参数:
        level (str): 日志级别，如 'info', 'warn', 'error' 等。
        filepath (str): 日志文件路径前缀，如 'log/launcher/'.
        message (str): 要记录的日志内容。
    """
    # 获取当前时间
    timestamp = datetime.date.today()
    if filepath is None:
        filepath = _get_default_log_dir()
    filepath = os.path.join(filepath, str(timestamp) + ".log")

    # 获取调用者的信息
    frame = inspect.currentframe()
    caller = frame.f_back if frame else None
    filename = os.path.basename(caller.f_code.co_filename) if caller else "<unknown>"
    lineno = caller.f_lineno if caller else 0
    local_time = time.localtime(time.time())
    formatted_time = time.strftime('%Y-%m-%d %H:%M:%S', local_time)
    # 获取当前线程名称
    thread_name = threading.current_thread().name

    # 构造日志条目
    log_entry = f"{formatted_time} - [ {filename}:{lineno}/{thread_name}/{level.upper()} ]: {message}\n"
    # 确保目录存在
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    # 写入日志文件
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(log_entry)
    print(log_entry)