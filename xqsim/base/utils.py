import numpy as np

FACTOR_DIR = "Alpha"
DATA_DIR = "Data"

class simcfg(object):
    @staticmethod
    def get(cfg: dict, key, default_value):
        if default_value is None:
            return cfg.get(key, default_value)
        if isinstance(default_value, bool):
            if key in cfg:
                return cfg[key] == "true"
        return type(default_value)(cfg.get(key, default_value))


def empty_alpha(ii_size, default_value=np.nan) -> np.ndarray:
    return np.full(ii_size, default_value, dtype=np.float64)