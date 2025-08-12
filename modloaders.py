import os
import io
import json
import zipfile
import pathlib
import requests
from typing import Optional, Dict, Any
from config_loader import load_config
import prints


def _save_profile(profile: Dict[str, Any], game_path: pathlib.Path, name: Optional[str] = None) -> pathlib.Path:
    version_id = name or profile.get("id")
    if not version_id:
        raise ValueError("Profile JSON missing 'id' and no name provided")
    install_path = game_path / "versions" / version_id
    os.makedirs(install_path, exist_ok=True)
    profile_path = install_path / f"{version_id}.json"
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
    return profile_path


def install_fabric(game_version: str, loader_version: str, name: Optional[str], game_path: pathlib.Path) -> pathlib.Path:
    cfg = load_config()
    url = cfg["modloader"]["fabric_profile_template"].format(game_version=game_version, loader_version=loader_version)
    prints.prints("info", f"Fetching Fabric profile: {url}")
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    profile = resp.json()
    if name:
        profile["id"] = name
    return _save_profile(profile, game_path, name)


def install_quilt(game_version: str, loader_version: str, name: Optional[str], game_path: pathlib.Path) -> pathlib.Path:
    cfg = load_config()
    url = cfg["modloader"]["quilt_profile_template"].format(game_version=game_version, loader_version=loader_version)
    prints.prints("info", f"Fetching Quilt profile: {url}")
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    profile = resp.json()
    if name:
        profile["id"] = name
    return _save_profile(profile, game_path, name)


def _fetch_installer(url: str) -> bytes:
    prints.prints("info", f"Downloading installer: {url}")
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.content


def _extract_version_json_from_installer(installer_bytes: bytes) -> Dict[str, Any]:
    with zipfile.ZipFile(io.BytesIO(installer_bytes)) as zf:
        # Heuristics: try common paths first
        candidate_names = [
            "version.json",
            "install_profile.json",
            "data/client_profile.json",
            "data/profile.json",
            "profile.json",
        ]
        for name in candidate_names:
            try:
                with zf.open(name) as f:
                    text = f.read().decode("utf-8", errors="ignore")
                    data = json.loads(text)
                    # install_profile.json may wrap version info under 'versionInfo'
                    if name.endswith("install_profile.json") and isinstance(data, dict) and "versionInfo" in data:
                        return data["versionInfo"]
                    return data
            except KeyError:
                continue
            except Exception:
                continue
        # Fallback: search for a json file containing 'libraries' and 'mainClass'
        for info in zf.infolist():
            if not info.filename.endswith('.json'):
                continue
            try:
                with zf.open(info.filename) as f:
                    text = f.read().decode("utf-8", errors="ignore")
                    data = json.loads(text)
                    if isinstance(data, dict) and "libraries" in data and ("mainClass" in data or "main-class" in data):
                        return data
            except Exception:
                continue
    raise ValueError("Unable to find suitable version JSON in installer JAR")


def install_from_installer(game_version: str, loader_version: str, name: Optional[str], game_path: pathlib.Path, template: str) -> pathlib.Path:
    url = template.format(game_version=game_version, loader_version=loader_version)
    installer_bytes = _fetch_installer(url)
    profile = _extract_version_json_from_installer(installer_bytes)
    if name:
        profile["id"] = name
    # Ensure inheritsFrom set to base game if present in profile chain
    profile.setdefault("inheritsFrom", game_version)
    return _save_profile(profile, game_path, name)


def install_loader(loader: str, game_version: str, loader_version: Optional[str] = None, name: Optional[str] = None) -> pathlib.Path:
    loader = loader.lower()
    cfg = load_config()
    game_path = pathlib.Path(cfg["launcher"]["game_path"][cfg["launcher"]["latest_game_path_used"]])
    if loader == "fabric":
        if not loader_version:
            raise ValueError("fabric requires loader_version, e.g., 0.16.9")
        return install_fabric(game_version, loader_version, name, game_path)
    if loader == "quilt":
        if not loader_version:
            raise ValueError("quilt requires loader_version")
        return install_quilt(game_version, loader_version, name, game_path)
    if loader == "forge":
        if not loader_version:
            raise ValueError("forge requires loader_version")
        template = cfg["modloader"]["forge_installer_template"]
        return install_from_installer(game_version, loader_version, name, game_path, template)
    if loader == "neoforge":
        if not loader_version:
            raise ValueError("neoforge requires loader_version")
        template = cfg["modloader"]["neoforge_installer_template"]
        return install_from_installer(game_version, loader_version, name, game_path, template)
    if loader == "optifine":
        if not loader_version:
            raise ValueError("optifine requires loader_version, e.g., H9 or HD_U_I6")
        # For OptiFine, template also needs type, commonly 'HD_U'. Allow override via name or assume 'HD_U'
        of_type = "HD_U"
        template = cfg["modloader"]["optifine_installer_template"].replace("{type}", of_type)
        return install_from_installer(game_version, loader_version, name, game_path, template)
    raise ValueError(f"Unsupported loader: {loader}")