import os
import datetime
import inspect
import threading
import toml
import time
config = toml.load('config.toml')
def prints(level, message,filepath=config["launcher"]["log_path"]):
    """
    输出格式化日志信息到指定文件。

    参数:
        level (str): 日志级别，如 'info', 'warn', 'error' 等。
        filepath (str): 日志文件路径，如 'log/launcher/2025-07-10.log'。
        message (str): 要记录的日志内容。
    """
    # 获取当前时间
    timestamp = datetime.date.today()
    filepath += str(timestamp) + ".log"
    # 获取调用者的信息
    frame = inspect.stack()[1]  # 获取调用者栈帧
    filename = os.path.basename(frame.filename)  # 获取文件名
    lineno = frame.lineno  # 获取行号
    local_time = time.localtime(time.time())
    formatted_time = time.strftime('%Y-%m-%d %H:%M:%S', local_time)
    # 获取当前线程名称
    thread_name = threading.current_thread().name

    # 构造日志条目
    log_entry = f"{formatted_time} - [ {filename}:{lineno}/{thread_name}/{level.upper()} ]: {message}\n"
    # 确保目录存在
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    try:
    	os.mknod(filepath)
    except:
    	pass
    # 写入日志文件
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(log_entry)
    print(log_entry)