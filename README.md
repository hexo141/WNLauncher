## 项目简介

WNLauncher 是一个 Python 实现的 Minecraft 启动器与资源管理工具，支持：
- 自动获取 Mojang 版本列表与资源
- 并发下载、断点校验（大小/sha1）、连接池与重试
- 自动发现本机 Java、自动分配内存后启动
- 动态获取并安装主流模组加载器（Fabric、Forge、NeoForge、OptiFine，附带 Quilt）
- 可选是否将模组加载器 Profile JSON 落盘
- 实时从网站/API 获取信息的通用工具

## 环境与依赖

- Python 3.11+
- 依赖见 `requirements.txt`（requests、urllib3）

安装依赖（普通环境）：
```bash
python3 -m pip install -r requirements.txt
```
若遇到系统受管环境（PEP 668）限制，可使用：
```bash
python3 -m pip install --break-system-packages -r requirements.txt
```

## 目录结构（关键文件）

- `main.py`：示例入口
- `core.py`：核心逻辑（下载、安装、启动、自动 Java/内存、实时获取）
- `download.py`：并发下载与校验
- `modloaders.py`：模组加载器版本发现与安装
- `findjava.py`：本机 Java 扫描
- `prints.py`：轻量日志
- `realtime.py`：实时 HTTP 获取（连接池/重试）
- `config_loader.py`：配置加载（优先 `tomllib`，回退 `toml`）
- `config.toml`：配置文件

## 配置说明（config.toml）

### launcher
- `game_path`：游戏根目录，默认 `WNLauncher/.minecraft/`
- `latest_game_path_used`：选择使用哪个路径 key（如 `default`）
- `download_threads`：下载线程数
- `download_time_out`：下载超时（秒）
- `download_max_retries`：下载最大重试次数
- `persist_profiles`：是否将模组加载器 Profile JSON 写入磁盘（默认 false）

说明：
- 当 `persist_profiles=false` 时，安装 Fabric/Forge 等仅“返回应有的 JSON 路径”，不会实际写入文件；若该路径原本存在文件，会被删除。
- 若后续需要通过 `runMC()` 启动对应模组版，需要该版本目录下存在 `<name>.json`。因此建议：
  - 启动模组版前，将 `persist_profiles` 设为 `true`，再执行安装；或
  - 手动将从 API 获取到的 profile JSON 写入对应路径。

### modloader（模组加载器）
提供可覆盖的 API 模板：
- Fabric/Quilt：官方 Meta API 的 profile json
- Forge/NeoForge/OptiFine：安装器 JAR（从镜像 Maven 获取）

## 常用操作

### 1. 安装原版与资源
```python
from core import core
c = core()
# 下载原版（示例）
print(c.download('release', '1.21.1', '1.21.1'))
```

### 2. 自动安装模组加载器
无需知道 loader 版本号，自动解析最新：
```python
from core import core
c = core()
# Fabric（自动解析最新版本）
print(c.install_loader('fabric', '1.21.1', None, '1.21.1-fabric'))
# Forge（自动解析最新版本）
print(c.install_loader('forge', '1.20.1', None, '1.20.1-forge'))
# NeoForge/OptiFine 同理：'neoforge' / 'optifine'
```
指定 loader 版本：
```python
c.install_loader('fabric', '1.21.1', '0.16.9', '1.21.1-fabric-0.16.9')
```

> 注意：如需通过 `runMC()` 启动模组配置，请确保 `config.toml` 中 `persist_profiles=true`，或手动写入对应 `<name>.json`。

### 3. 启动游戏（自动 Java & 自动内存）
```python
from core import core
c = core()
# 交互输入版本名，例如：1.21.1 或 1.21.1-fabric
c.runMC()
```
启动前会：
- 自动寻找本机 Java（优先 64 位）
- 按系统内存自动分配 `-Xms/-Xmx`（默认占用 50%，范围 2G~8G）
- 自动下载缺失 client jar、日志配置并校验

### 4. 实时获取 API 数据
```python
from core import core
c = core()
status, data = c.fetch_realtime('https://meta.fabricmc.net/v2/versions', parse='json')
print(status, type(data))
```

## 性能优化点
- 并发下载 + 连接池 + 指数退避
- 流式写入 + 实时 SHA1 校验
- 懒加载配置、日志；避免频繁磁盘 IO
- 移除 numpy 等重量依赖

## 常见问题（FAQ）
- Q：为什么安装 Fabric 后没有生成 `versions/<name>/<name>.json`？
  - A：默认 `persist_profiles=false`。若要写入，请将其设为 `true` 后再安装，或手动保存 profile JSON。
- Q：PEP 668 导致无法安装依赖？
  - A：使用 `--break-system-packages`，或在虚拟环境内安装。
- Q：NeoForge 某些版本解析不到？
  - A：该游戏版本可能暂未在官方 Maven 发布对应版本，这是上游状态。

## 许可证

见 `LICENSE`（MIT）。