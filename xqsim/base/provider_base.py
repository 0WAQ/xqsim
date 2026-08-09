import os
from .module_base import ModuleBase
from .utils import DATA_DIR
from xqsim.common_module import *


class ProviderBase(ModuleBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.output_cache_dir = self.cfg["output_cache_dir"]
        self.dir_name = self.cfg.get("dir_name", self.id)

        # data_dir 为空时数据目录直接挂在 output_cache_dir 下 (扁平布局, 期货用)
        data_dir = self.meta.get_para_default("data_dir", DATA_DIR)
        if data_dir:
            self.output_dir = os.path.join(self.output_cache_dir, data_dir, self.dir_name)
        else:
            self.output_dir = os.path.join(self.output_cache_dir, self.dir_name)

        self.modify_mode = False
        self.overwrite = False

    def enable_modify(self):
        log_info("Provider %s enable modify", self.id)
        self.modify_mode = True

    def enable_part_overwrite(self):
        log_info("Provider %s enable overwrite", self.id)
        self.overwrite = True

    def do_generate(self):
        if not self.modify_mode and os.path.exists(self.output_dir):
            log_warn("Provider %s ignore", self.id)
            return
        self.generate()

    def generate(self):
        log_error("Need override")

    def write_data(self, data_name: str, data: np.ndarray, compress=False):
        self.dr.write_data(self.dir_name, data_name, data, compress=compress)

    def append_data(self, data_name: str, data: np.ndarray, 
                    begin_trading_day: int | None = None, 
                    end_trading_day: int | None = None):
        self.dr.append_data(self.dir_name, data_name, data, begin_trading_day, end_trading_day, part_overwrite=self.overwrite)

    def write_compress_data(self, data_name: str, data: np.ndarray, 
                            begin_trading_day: int | None = None, 
                            end_trading_day: int | None = None):
        self.dr.write_compress_data(self.dir_name, data_name, data, begin_trading_day, end_trading_day, overwrite=self.overwrite)

    def append_compress_data(self, data_name: str, data: np.ndarray, 
                             begin_trading_day: int | None = None, 
                             end_trading_day: int | None = None):
        self.write_compress_data(data_name, data, begin_trading_day, end_trading_day)
