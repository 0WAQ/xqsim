import os
from xqsim.common_module import *
from .module_base import ModuleBase
from .utils import simcfg

class StatsBase(ModuleBase):
    def __init__(self, *args):
        super().__init__(*args)

        self.booksize: float = float(simcfg.get(self.cfg, "booksize", 20e6))    # type: ignore
        self.print_pnl: bool = bool(simcfg.get(self.cfg, "print", False))       # type: ignore
        self.dump_pnl: bool = bool(simcfg.get(self.cfg, "dumpPnl", False))      # type: ignore
        self.pnl_dir: str = simcfg.get(self.cfg, "pnlDir", "./pnl")             # type: ignore
        self.pnl_file: str

        if self.dump_pnl:
            if not os.path.exists(self.pnl_dir):
                os.makedirs(self.pnl_dir)
            self.pnl_file = os.path.join(self.pnl_dir, self.id)

        log_info(f"Stats {self.id} created, pnl dir {self.pnl_dir}, "
                 f"book size {self.booksize}, interval {self.meta.interval}")

    def save_pnl(self):
        log_error("Need override")

    def calculate_di(self, di: int, alpha: np.ndarray):
        log_error("Need override")

    def calculate_ti(self, di: int, ti: int, alpha: np.ndarray):
        log_error("Need override")