import os
import io
import json
import zipfile
import pathlib
import requests
from typing import Optional, Dict, Any, List, Tuple
from config_loader import load_config
import prints
from realtime import fetch_json, fetch_text
import xml.etree.ElementTree as ET


def _save_profile(profile: Dict[str, Any], game_path: pathlib.Path, name: Optional[str] = None) -> pathlib.Path:
    cfg = load_config()
    persist = bool(cfg.get('launcher', {}).get('persist_profiles', False))
    version_id = name or profile.get("id")
    if not version_id:
        raise ValueError("Profile JSON missing 'id' and no name provided")
    install_path = game_path / "versions" / version_id
    profile_path = install_path / f"{version_id}.json"
    if not persist:
        # If not persisting, ensure no stale file remains
        try:
            if profile_path.exists():
                os.remove(profile_path)
        except Exception:
            pass
        return profile_path
    os.makedirs(install_path, exist_ok=True)
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


def _parse_maven_metadata_versions(xml_text: str) -> List[str]:
    try:
        root = ET.fromstring(xml_text)
        versions = [v.text for v in root.findall('.//version') if v is not None and v.text]
        return versions
    except Exception:
        return []


def _fetch_maven_versions(url: str) -> List[str]:
    status, text = fetch_text(url, timeout=15)
    if status != "success":
        return []
    return _parse_maven_metadata_versions(text)


def list_fabric_versions(game_version: Optional[str] = None) -> List[str]:
    # Try Fabric Meta API
    if game_version:
        status, data = fetch_json(f"https://meta.fabricmc.net/v2/versions/loader/{game_version}", timeout=15)
        if status == "success" and isinstance(data, list):
            # data items have 'loader' with 'version'
            versions = []
            for item in data:
                loader = item.get('loader') or {}
                v = loader.get('version')
                if v:
                    versions.append(v)
            return sorted(set(versions))
    # Fallback: return all loader versions
    status, data = fetch_json("https://meta.fabricmc.net/v2/versions/loader", timeout=15)
    if status == "success" and isinstance(data, list):
        return [i.get('version') for i in data if isinstance(i, dict) and i.get('version')]
    return []


def list_quilt_versions(game_version: Optional[str] = None) -> List[str]:
    if game_version:
        status, data = fetch_json(f"https://meta.quiltmc.org/v3/versions/loader/{game_version}", timeout=15)
        if status == "success" and isinstance(data, list):
            versions = []
            for item in data:
                loader = item.get('loader') or {}
                v = loader.get('version')
                if v:
                    versions.append(v)
            return sorted(set(versions))
    status, data = fetch_json("https://meta.quiltmc.org/v3/versions/loader", timeout=15)
    if status == "success" and isinstance(data, list):
        return [i.get('version') for i in data if isinstance(i, dict) and i.get('version')]
    return []


def list_forge_versions(game_version: Optional[str] = None) -> List[str]:
    # Prefer Maven metadata since it is authoritative
    meta_url = "https://maven.minecraftforge.net/net/minecraftforge/forge/maven-metadata.xml"
    versions = _fetch_maven_versions(meta_url)
    if not versions:
        return []
    if game_version:
        prefix = f"{game_version}-"
        versions = [v.split('-')[-1] for v in versions if v.startswith(prefix)]
    else:
        versions = [v.split('-')[-1] for v in versions if '-' in v]
    # Deduplicate while keeping order (latest at end)
    dedup: List[str] = []
    for v in versions:
        if v not in dedup:
            dedup.append(v)
    return dedup


def list_neoforge_versions(game_version: Optional[str] = None) -> List[str]:
    meta_url = "https://maven.neoforged.net/releases/net/neoforged/forge/maven-metadata.xml"
    versions = _fetch_maven_versions(meta_url)
    if not versions:
        return []
    if game_version:
        prefix = f"{game_version}-"
        versions = [v.split('-')[-1] for v in versions if v.startswith(prefix)]
    else:
        versions = [v.split('-')[-1] for v in versions if '-' in v]
    dedup: List[str] = []
    for v in versions:
        if v not in dedup:
            dedup.append(v)
    return dedup


def list_optifine_versions(game_version: Optional[str] = None) -> List[str]:
    # BMCLAPI often exposes optifine listing per game version: /optifine/{mc}
    base = "https://bmclapi2.bangbang93.com/optifine"
    url = f"{base}/{game_version}" if game_version else base
    status, data = fetch_json(url, timeout=15)
    if status == "success":
        if isinstance(data, list):
            # Items could be strings or dicts; normalize to strings if possible
            out: List[str] = []
            for item in data:
                if isinstance(item, str):
                    out.append(item)
                elif isinstance(item, dict):
                    # try fields like 'patch' or 'type+patch'
                    patch = item.get('patch')
                    of_type = item.get('type') or item.get('branch')
                    if of_type and patch:
                        out.append(f"{of_type}_{patch}")
                    elif patch:
                        out.append(str(patch))
            return out
    return []


def resolve_latest(loader: str, game_version: str) -> Optional[str]:
    loader = loader.lower()
    if loader == 'fabric':
        versions = list_fabric_versions(game_version)
        return versions[-1] if versions else None
    if loader == 'quilt':
        versions = list_quilt_versions(game_version)
        return versions[-1] if versions else None
    if loader == 'forge':
        versions = list_forge_versions(game_version)
        return versions[-1] if versions else None
    if loader == 'neoforge':
        versions = list_neoforge_versions(game_version)
        return versions[-1] if versions else None
    if loader == 'optifine':
        versions = list_optifine_versions(game_version)
        return versions[-1] if versions else None
    return None


def install_loader(loader: str, game_version: str, loader_version: Optional[str] = None, name: Optional[str] = None) -> pathlib.Path:
    loader = loader.lower()
    cfg = load_config()
    game_path = pathlib.Path(cfg["launcher"]["game_path"][cfg["launcher"]["latest_game_path_used"]])
    # Auto-resolve latest version if not provided
    if not loader_version:
        loader_version = resolve_latest(loader, game_version)
        if not loader_version:
            raise ValueError(f"Unable to resolve latest version for {loader} {game_version}")

    if loader == "fabric":
        return install_fabric(game_version, loader_version, name, game_path)
    if loader == "quilt":
        return install_quilt(game_version, loader_version, name, game_path)
    if loader == "forge":
        template = cfg["modloader"]["forge_installer_template"]
        return install_from_installer(game_version, loader_version, name, game_path, template)
    if loader == "neoforge":
        template = cfg["modloader"]["neoforge_installer_template"]
        return install_from_installer(game_version, loader_version, name, game_path, template)
    if loader == "optifine":
        of_type = "HD_U"
        template = cfg["modloader"]["optifine_installer_template"].replace("{type}", of_type)
        return install_from_installer(game_version, loader_version, name, game_path, template)
    raise ValueError(f"Unsupported loader: {loader}")