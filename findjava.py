import os
import subprocess
import re
import platform
import sys
if platform.system() == "Windows":
	import winreg  # 新增注册表模块

def find_java_executables():
    system = platform.system()
    exe_name = 'java.exe' if system == 'Windows' else 'java'
    java_paths = set()

    # 1. 检查PATH环境变量中的路径
    path_dirs = os.environ.get('PATH', '').split(os.pathsep)
    for path_dir in path_dirs:
        if not os.path.isdir(path_dir):
            continue
        candidate = os.path.join(path_dir, exe_name)
        if os.path.isfile(candidate):
            java_paths.add(os.path.abspath(candidate))

    # 2. 如果是Windows系统，添加注册表查找
    if system == 'Windows':
        # 扫描常见安装目录
        common_paths = [
            os.path.join(os.environ.get('ProgramFiles', 'C:\\Program Files'), 'Java'),
            os.path.join(os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)'), 'Java')
        ]
        
        for base_path in common_paths:
            if not os.path.isdir(base_path):
                continue
            for entry in os.listdir(base_path):
                jdk_path = os.path.join(base_path, entry, 'bin', exe_name)
                if os.path.isfile(jdk_path):
                    java_paths.add(os.path.abspath(jdk_path))

        # 检查注册表中的安装路径
        reg_keys = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\JavaSoft\Java Development Kit"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\JavaSoft\Java Runtime Environment")
        ]
        
        for root, key_path in reg_keys:
            try:
                with winreg.OpenKey(root, key_path) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        subkey_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, subkey_name) as subkey:
                            try:
                                java_home = winreg.QueryValueEx(subkey, 'JavaHome')[0]
                                java_path = os.path.join(java_home, 'bin', exe_name)
                                if os.path.isfile(java_path):
                                    java_paths.add(os.path.abspath(java_path))
                            except FileNotFoundError:
                                continue
            except FileNotFoundError:
                continue

    return list(java_paths)

def get_java_info(java_path):
    """获取Java版本和架构信息"""
    try:
        result = subprocess.run(
            [java_path, '-version'],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == 'Windows' else 0
        )
        
        output = result.stderr or result.stdout
        
        # 提取版本号
        version_match = re.search(r'version\s+"([^"]+)"', output)
        version = version_match.group(1) if version_match else "Unknown"
        
        # 提取架构信息
        arch = "Unknown"
        if '64-Bit' in output or '64 bit' in output.lower():
            arch = 'x86_64' if 'arm' not in output.lower() else 'arm64'
        elif '32-Bit' in output or '32 bit' in output.lower():
            arch = 'x86'
        
        # macOS特殊处理
        if platform.system() == 'Darwin':
            result_props = subprocess.run(
                [java_path, '-XshowSettings:properties', '-version'],
                capture_output=True,
                text=True,
                timeout=5,
                check=False
            )
            props_output = result_props.stderr or result_props.stdout
            arch_match = re.search(r'os\.arch\s*=\s*(\S+)', props_output)
            if arch_match:
                arch = arch_match.group(1)
        
        return [java_path, version, arch]
    
    except (subprocess.TimeoutExpired, OSError, subprocess.SubprocessError):
        return None

def main():
    results = []
    java_paths = find_java_executables()
    
    for path in java_paths:
        java_info = get_java_info(path)
        if java_info:
            results.append(java_info)
    
    results.sort(key=lambda x: x[0])
    return results

if __name__ == "__main__":
    java_versions = main()
    for info in java_versions:
        print(f"Path: {info[0]}, Version: {info[1]}, Architecture: {info[2]}")