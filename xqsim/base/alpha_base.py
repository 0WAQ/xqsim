import os
from xqsim.common_module import *
from .module_base import ModuleBase
from .utils import simcfg, empty_alpha, FACTOR_DIR

class AlphaBase(ModuleBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.alpha: np.ndarray = empty_alpha(self.meta.ii_size)
        self.output_cache_dir = common_utils.realpath(self.cfg["output_cache_dir"])
        self.dir_name: str = simcfg.get(self.cfg, "dir_name", self.id)  # type: ignore
        self.overwrite = simcfg.get(self.cfg, "overwrite", self.meta.get_para("overwrite"))
        self.save_flag = simcfg.get(self.cfg, "save", self.meta.get_para("save"))
        self.save_csv_dir = simcfg.get(self.cfg, "save_csv", self.meta.get_para("save_csv"))
        self.save_csv_total = simcfg.get(self.cfg, "save_csv_total", self.meta.get_para("save_csv_total"))
        self.output_dir = os.path.join(self.output_cache_dir, FACTOR_DIR, self.dir_name)

        self.delay: int = simcfg.get(self.cfg, "delay", 1)  # type: ignore
        # Optional state warmup driven by Simulator before the configured begin_di.
        # A factor's generate(di) still processes exactly one target day; historical
        # replay must not be hidden inside the factor implementation.
        self.warmup_days: int = int(simcfg.get(self.cfg, "warmup_days", 0))  # type: ignore
        if self.warmup_days < 0:
            raise ValueError("warmup_days must be non-negative")
        valid_name = simcfg.get(self.cfg, "universeId", None)
        if valid_name is not None:
            self.valid = self.dr.get_data(valid_name)

    def reset_alpha(self):
        self.alpha = empty_alpha(self.meta.ii_size)

    def before_generate(self, di: int):
        pass

    def generate(self, di: int):
        pass

    def after_generate(self, di: int):
        pass

    def generate_portfolio(self, di: int, alpha_list: list):
        pass


PortfolioBase = AlphaBase