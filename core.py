import json,time
import prints
import os
import pathlib
import urllib
import platform
from config_loader import load_config
import download
import zipfile
import random
import subprocess
import findjava
import requests
#config = toml.load('config.toml')
class core:
	def __init__(self):
		self.config = load_config()
		self.source_link = self.config["source_link"][self.config["launcher"]["source_link_used"]]["version_json"]
		self.game_path = self.config["launcher"]["game_path"][self.config["launcher"]["latest_game_path_used"]]
		self.threads = self.config["launcher"]["download_threads"]
		self.system_type = platform.system().lower()
	def show_all_version(self):
		try:
			resp = requests.get(self.source_link, timeout=10)
			resp.raise_for_status()
			_source_get_json = resp.json()
		except Exception as e:
			prints.prints("error", f"Failed to fetch version manifest: {e}")
			return {"status": "error"}
		all_version = _source_get_json["versions"]
		all_release_version = []
		all_snapshot_version = []
		all_old_version = []
		for version in all_version:
			if version["type"] == "release":
				all_release_version.append(version)
			elif version["type"] == "snapshot":
				all_snapshot_version.append(version)
			elif "old" in version["type"]:
				all_old_version.append(version)
		return {
		"status": "success",
		"all_release_version":  all_release_version,
		"all_snapshot_version": all_snapshot_version,
		"all_old_version": all_old_version
		}
	def download(self,game_type,game_version,game_rename=None,game_path=None):
		if game_path is None:
			game_path = self.game_path
		if game_rename is None:
			game_rename = game_version
		game_path = pathlib.Path(game_path)
		create_folder = self._Createfolders(game_path,game_rename)
		all_version = self.show_all_version()
		if all_version["status"] == "error":
			return ["error","Unable to get version list"]
		for version in all_version[f"all_{game_type}_version"]:
			if game_version == version["id"]:
				prints.prints("info",f"Find the game version: {game_version}")
				install_path = game_path / "versions" / game_rename
				#temp_response = try_requests.try_requests(version["url"])
				if create_folder[0] == "error":
					return create_folder
				#if temp_response[0] == "error":
				#	return temp_response
				if game_rename is not None:
					_version_json = install_path / str(game_rename+pathlib.Path(version["url"]).suffix)
				else:
					_version_json = install_path / os.path.basename(urllib.parse.urlparse(version["url"]).path)# 主要是获取游戏JSON文件在url中的文件名
				if download.main({version["url"]:{"save":_version_json}}, 1, True)[0][0] == "success":
					with open(_version_json,"r") as f:
						_game_json = json.load(f)
					prints.prints("info",f"reading {_version_json}")
					library_url = {}
					natives_url = {}
					# Normalize OS key for natives mapping
					current_os_key = self.system_type
					if current_os_key == "darwin":
						current_os_key = "osx"
					# Collect library artifacts and native classifiers for download first
					for library in _game_json["libraries"]:
						downloads = library.get("downloads", {})
						artifact = downloads.get("artifact")
						if artifact:
							lib_artifact_path = artifact.get("path")
							lib_artifact_url = artifact.get("url")
							# 替换链接的默认源为bmclapi源
							if self.config["launcher"]["source_link_used"] != "mojang" and lib_artifact_url:
								lib_artifact_url = lib_artifact_url.replace("https://libraries.minecraft.net/",self.config["source_link"][self.config["launcher"]["source_link_used"]]["libraries"])
							if lib_artifact_url and lib_artifact_path:
								library_url[lib_artifact_url] = {"save": game_path / "libraries" / lib_artifact_path,
									"size": artifact.get("size"),
									"sha1": artifact.get("sha1")}
								os.makedirs(os.path.dirname(game_path / "libraries" / lib_artifact_path), exist_ok=True)
						# Handle native classifiers
						if "natives" in library and "classifiers" in downloads:
							classifier_key = library["natives"].get(current_os_key)
							if classifier_key:
								classifier = downloads["classifiers"].get(classifier_key)
								if classifier:
									native_path = classifier.get("path")
									native_url = classifier.get("url")
									if self.config["launcher"]["source_link_used"] != "mojang" and native_url:
										native_url = native_url.replace("https://libraries.minecraft.net/", self.config["source_link"][self.config["launcher"]["source_link_used"]]["libraries"])
									if native_url and native_path:
										natives_url[native_url] = {"save": game_path / "libraries" / native_path,
											"size": classifier.get("size"),
											"sha1": classifier.get("sha1")}
										os.makedirs(os.path.dirname(game_path / "libraries" / native_path), exist_ok=True)
					# Download libraries and natives
					download.main(library_url, self.threads, True)
					if natives_url:
						download.main(natives_url, self.threads, True)
						# Extract natives after download
						natives_dir = install_path / (game_rename+"-natives")
						for save_info in natives_url.values():
							self._extract_libraries(save_info["save"], natives_dir)
					# 下载assets的json文件
					_assetsIndex = _game_json["assetIndex"]
					assetsJsonSavePath = game_path / "assets" / "indexes" / urllib.parse.urlparse(_assetsIndex["url"]).path.split('/')[-1]
					download.main({_assetsIndex["url"]:{"save":assetsJsonSavePath,"size":_assetsIndex.get("size"),"sha1":_assetsIndex.get("sha1")}}, 1, True)
					self.download_assets(assetsJsonSavePath)
					return ["success",f"{game_rename} installation is complete"]
				return ["error",f"Download Failure: {_version_json}"]
		# 如果循环结束仍未找到对应版本
		prints.prints("error",f"No game version found: {game_version}")
		return ["error",f"No game version found: {game_version}"]
	def _Createfolders(self,game_path,game_rename):
		install_path = game_path / "versions" / game_rename
		try:
			os.makedirs(install_path, exist_ok=True) # 创建版本文件夹
			libraries_path = game_path / "libraries"
			natvies_folder = install_path / (game_rename+"-natives")
			os.makedirs(libraries_path,exist_ok=True)# 创建libraries文件夹
			os.makedirs(natvies_folder,exist_ok=True)# 创建natives文件夹
			os.makedirs("./temp",exist_ok=True)# 创建临时文件夹
			os.makedirs(game_path / "assets" / "indexes",exist_ok=True)# 创建assets文件夹
			prints.prints("info","The file directory was successfully created")
			return ["success","The file directory was successfully created"]
		except IOError as e:
			prints.prints("error",e)
			return ["error",e]
		except Exception as e:
			prints.prints("error",e)
			return ["error",e]
	def download_assets(self,assets_json):
		assets_json = json.loads(open(assets_json,"r").read())["objects"]
		assets_download = {}
		assets_download_link = self.config["source_link"][self.config["launcher"]["source_link_used"]]["assets"]
		for i in assets_json:
			temp_hash = assets_json[i]["hash"]
			_size = assets_json[i]["size"]
			_save_path = pathlib.Path(self.game_path )/ "assets" / "objects" / temp_hash[:2] / temp_hash
			if not os.path.exists(_save_path):
				os.makedirs(os.path.dirname(_save_path),exist_ok=True)
				assets_download[assets_download_link+temp_hash[:2]+"/"+temp_hash] = {"save":_save_path,"sha1":temp_hash,"size":_size}
		download.main(assets_download,self.threads)
		return ["success","Assets download ok"]
	def _extract_libraries(self, zip_path, output_dir):
	    try:
	        prints.prints("info", f"Extracting library: {zip_path} to {output_dir}")
	        with zipfile.ZipFile(zip_path, "r") as zf:
	            for member in zf.infolist():
	                filename = member.filename
	                # 严格匹配三种目标文件类型
	                if filename.endswith((".dylib", ".dll", ".so")):
	                    # 直接使用文件名（去除路径部分）
	                    base_filename = os.path.basename(filename)
	                    target_path = os.path.join(output_dir, base_filename)
	                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
	                    with zf.open(member) as source, open(target_path, 'wb') as dest:
	                        dest.write(source.read())
	        prints.prints("success", f"Extract ok: {zip_path}")
	        return ["success", f"Extract ok: {zip_path}"]
	    except FileNotFoundError as e:
	        prints.prints("error", e)
	        return ["error", e]
	    except zipfile.BadZipFile as e:
	        prints.prints("error", e)
	        return ["error", e]
	    except IOError as e:
	        prints.prints("error", e)
	        return ["error", e]
	    except Exception as e:
	        prints.prints("error", e)
	        return ["error", e]
	def runMC(self):
	    game_name = input("version name:")
	    _game_version_path = pathlib.Path(self.game_path) / "versions" / game_name
	    print(findjava.main())
	    java_path = findjava.main()[int(input("Select:"))][0]
	    # 加载游戏JSON配置
	    game_json_path = _game_version_path / f"{game_name}.json"
	    with open(game_json_path, "r") as f:
	        _game_json = json.load(f)
	    
	    # 1. 构建正确的类路径
	    class_path_parts = []
	    
	    # 获取当前系统类型（处理Mac的特殊情况）
	    current_os = self.system_type
	    if current_os == "darwin":
	        current_os = "osx"
	    
	    for lib in _game_json.get("libraries", []):
	        # 处理库规则
	        rules = lib.get("rules", [])
	        include_lib = True
	        
	        if rules:
	            for rule in rules:
	                os_condition = rule.get("os", {})
	                os_name = os_condition.get("name", "")
	                
	                if os_name:
	                    # 检查规则是否匹配当前系统
	                    if os_name == current_os:
	                        if rule.get("action") == "disallow":
	                            include_lib = False
	                        break
	                    else:
	                        # 规则针对其他系统，跳过
	                        if rule.get("action") == "allow":
	                            include_lib = False
	                        continue
	        
	        # 如果库应该包含且是普通库（非原生库）
	        if include_lib and "natives" not in lib:
	            if "downloads" in lib and "artifact" in lib["downloads"]:
	                lib_path = pathlib.Path(self.game_path) / "libraries" / lib["downloads"]["artifact"]["path"]
	                if lib_path.exists():
	                    class_path_parts.append(str(lib_path))
	                else:
	                    prints.prints("warning", f"Library not found: {lib_path}")
	    
	    # 添加主游戏JAR
	    main_jar = _game_version_path / f"{game_name}.jar"
	    if not main_jar.exists():
	        # 如果主JAR不存在，尝试下载
	        if "downloads" in _game_json and "client" in _game_json["downloads"]:
	            client_url = _game_json["downloads"]["client"]["url"]
	            download.main({client_url: {"save": main_jar}}, 1, True)
	    
	    class_path_parts.append(str(main_jar))
	    
	    # 构建类路径字符串
	    class_path_separator = ";" if os.name == "nt" else ":"
	    class_path = class_path_separator.join(class_path_parts)
		
	    # 2. 下载日志配置文件
	    log_config_path = None
	    log_sha1 = None
	    if "logging" in _game_json and "client" in _game_json["logging"]:
	        log_file = _game_json["logging"]["client"]["file"]
	        log_id = log_file["id"]
	        log_url = log_file["url"]
	        log_sha1 = log_file.get("sha1")
	        log_config_path = _game_version_path / log_id
	        
	        # 确保目录存在
	        os.makedirs(_game_version_path, exist_ok=True)
	        
	        # 下载日志配置
	        if not os.path.exists(log_config_path):
	            download.main({log_url: {"save": log_config_path}}, 1, True)
	        # 校验日志配置（如果提供了sha1）
	        if log_sha1 is not None:
	            if download.get_sha1(log_config_path) != log_sha1:
	                return ["error",f"The {log_config_path}'s SHA1 fails the check"]
	    # 3. 准备natives目录
	    natives_dir = _game_version_path / f"{game_name}-natives"
	    os.makedirs(natives_dir, exist_ok=True)
	    
	    # 4. 构建启动命令（使用安全的列表形式，不使用shell=True）
	    assets_dir = pathlib.Path(self.game_path) / "assets" / "objects"
	    asset_index_id = _game_json["assetIndex"]["id"]
	    classpath_file = _game_version_path / "classpath.txt"
	    with open(classpath_file, "w", encoding="utf-8") as f:
	    	f.write(class_path)
	    command = [
	        java_path,
	        "-Xmx2G",
	        "-XX:+UseG1GC",
	        "-XX:-UseAdaptiveSizePolicy",
	        "-XX:-OmitStackTraceInFastThrow",
	        f"-Dos.name={platform.system()}",
	        f"-Dos.version={platform.release()}",
	        "-Dminecraft.launcher.brand=WNLauncher",
	        "-Dminecraft.launcher.version=1.0.0",
	    ]
	    if log_config_path is not None:
	        command.append(f"-Dlog4j.configurationFile={log_config_path}")
	    command.extend([
	        f"-Djava.library.path={natives_dir}",
	        "-Dorg.lwjgl.util.DebugLoader=true",
	        "-Dorg.lwjgl.util.Debug=true",
	        "-Dstderr.encoding=UTF-8",
	        "-Dstdout.encoding=UTF-8",
	        "-Djdk.lang.Process.allowAmbiguousCommands=true",
	        "-Dfml.ignoreInvalidMinecraftCertificates=True",
	        "-Dfml.ignorePatchDiscrepancies=True",
	        "-Dlog4j2.formatMsgNoLookups=true",
	        f"-Dio.netty.native.workdir={natives_dir}",
	        "-cp",
	        class_path,
	        _game_json["mainClass"],
	        "--version",
	        game_name,
	        "--gameDir",
	        str(_game_version_path),
	        "--assetsDir",
	        str(assets_dir),
	        "--assetsIndex",
	        asset_index_id,
	        "--uuid",
	        "00000000-0000-0000-0000-000000000000",
	        "--accessToken",
	        "1241258925",
	        "--userType",
	        "Legacy",
	        "--username",
	        "O_Huangyu",
	        "--versionType",
	        "WNLauncher"
	    ])
	    try:
	        subprocess.run(command, check=True)
	    except subprocess.CalledProcessError as e:
	        prints.prints("error", f"Game failed to start: {e}")
	    except Exception as e:
	        prints.prints("error", f"Unexpected error: {e}")
	def install_loader(self, loader: str, game_version: str, loader_version: str, name: str = None):
		from modloaders import install_loader as _install
		try:
			profile_path = _install(loader, game_version, loader_version, name)
			prints.prints("success", f"Installed {loader} {loader_version} for {game_version}: {profile_path}")
			return ["success", str(profile_path)]
		except Exception as e:
			prints.prints("error", f"Install loader failed: {e}")
			return ["error", str(e)]
	def fetch_realtime(self, url: str, *, parse: str = "json", timeout: float = 10.0):
		try:
			import realtime
			if parse == "json":
				return realtime.fetch_json(url, timeout=timeout)
			else:
				return realtime.fetch_text(url, timeout=timeout)
		except Exception as e:
			prints.prints("error", f"Realtime fetch failed: {e}")
			return ("error", str(e))