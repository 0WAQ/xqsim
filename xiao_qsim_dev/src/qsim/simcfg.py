def get(cfg: dict, key, default_value):
    if default_value is None:
        return cfg.get(key, default_value)
    if isinstance(default_value, bool):
        if key in cfg:
            return cfg[key] == "true"
    return type(default_value)(cfg.get(key, default_value))
