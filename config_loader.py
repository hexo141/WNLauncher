_CONFIG_CACHE = None


def load_config():
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE
    # Try stdlib tomllib first (Python 3.11+)
    try:
        import tomllib  # type: ignore
        with open('config.toml', 'rb') as f:
            _CONFIG_CACHE = tomllib.load(f)
            return _CONFIG_CACHE
    except Exception:
        pass
    # Fallback to third-party toml
    import toml  # lazy import; only if tomllib unavailable
    _CONFIG_CACHE = toml.load('config.toml')
    return _CONFIG_CACHE