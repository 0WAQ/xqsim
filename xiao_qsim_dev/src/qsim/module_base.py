from qsim.common_module import *
from qsim.data_repository import DataRepository, DataView, DataManager, ADJ_PRICE, ADJ_VOLUME

FACTOR_DIR = "Alpha"


class simcfg(object):
    @staticmethod
    def get(cfg: dict, key, default_value):
        if default_value is None:
            return cfg.get(key, default_value)
        if isinstance(default_value, bool):
            if key in cfg:
                return cfg[key] == "true"
        return type(default_value)(cfg.get(key, default_value))


class univbase(object):
    dates = []
    instruments = []


def empty_alpha(ii_size, default_value=nan):
    return np.full(ii_size, default_value, dtype=np.float64)


class ModuleBase(object):
    def __init__(self, *args):  # dr, cfg, meta
        self.dr: DataRepository = args[0]
        self.cfg: dict = args[1]
        self.meta: Meta = self.dr.meta
        self.id = simcfg.get(self.cfg, "id", "unknown_id")
        self.module_name = simcfg.get(self.cfg, "module_name", "unknown_module")

        self.parent_module = None
        self.children_module = []


class AlphaBase(ModuleBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.alpha = empty_alpha(self.meta.ii_size)
        self.output_cache_dir = common_utils.realpath(self.cfg["output_cache_dir"])
        self.dir_name = simcfg.get(self.cfg, "dir_name", self.id)
        self.overwrite = simcfg.get(self.cfg, "overwrite", self.meta.get_para("overwrite"))
        self.save_flag = simcfg.get(self.cfg, "save", self.meta.get_para("save"))
        self.save_csv_dir = simcfg.get(self.cfg, "save_csv", self.meta.get_para("save_csv"))
        self.save_csv_total = simcfg.get(self.cfg, "save_csv_total", self.meta.get_para("save_csv_total"))
        self.output_dir = os.path.join(self.output_cache_dir, FACTOR_DIR, self.dir_name)

        self.delay = simcfg.get(self.cfg, "delay", 1)
        valid_name = simcfg.get(self.cfg, "universeId", None)
        if valid_name is not None:
            self.valid = self.dr.get_data(valid_name)

    def reset_alpha(self):
        self.alpha = empty_alpha(self.meta.ii_size)

    def before_generate(self, di):
        pass

    def generate(self, di):
        pass

    def after_generate(self, di):
        pass

    def generate_portfolio(self, di, alpha_list: list):
        pass


class OperationBase(ModuleBase):
    def __init__(self, *args):
        super().__init__(*args)

    def apply(self, di, alpha):
        pass


class StatsBase(ModuleBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.book_size = simcfg.get(self.cfg, "book_size", 2e8)

        self.pnl_dir = simcfg.get(self.cfg, "pnl_dir", "./pnl")
        if self.pnl_dir:
            if not os.path.exists(self.pnl_dir):
                os.makedirs(self.pnl_dir)
            self.pnl_file = os.path.join(self.pnl_dir, self.id)
        else:
            self.pnl_file = None

        log_info("Stats %s created, pnl dir %s, book size %s, interval %s",
                 self.id, self.pnl_dir, self.book_size, self.meta.interval)

    def calculate(self, alpha_array):
        log_error("Need override")

    def calculate_di(self, di, ti, alpha):
        log_error("Need override")
