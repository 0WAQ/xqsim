import os
from xqsim.common_module import *
from .module_base import ModuleBase
from .utils import simcfg

class StatsBase(ModuleBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.book_size = simcfg.get(self.cfg, "book_size", 2e8)

        self.pnl_dir: str = simcfg.get(self.cfg, "pnl_dir", "./pnl")    # type: ignore
        if self.pnl_dir:
            if not os.path.exists(self.pnl_dir):
                os.makedirs(self.pnl_dir)
            self.pnl_file = os.path.join(self.pnl_dir, self.id)
        else:
            self.pnl_file = None

        log_info("Stats %s created, pnl dir %s, book size %s, interval %s",
                 self.id, self.pnl_dir, self.book_size, self.meta.interval)

    def save_pnl(self):
        log_error("Need override")

    def calculate(self, alpha_array: np.ndarray):
        log_error("Need override")

    def calculate_di(self, di: int, ti: int, alpha: np.ndarray):
        log_error("Need override")