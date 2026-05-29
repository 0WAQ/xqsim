from qsim.module_base import *
from qsim.qsim_run import init_simulator, init_dr

DATA_DIR = "Data"


def builder_run(**kwargs):
    simulator = init_simulator(build=True, **kwargs)

    module = sys.modules['__main__']
    if kwargs.get("file_path", None) is None:
        file_path = common_utils.realpath(module.__file__)
        module_id = common_utils.get_module_dir_and_name(file_path)[1]
        kwargs["file_path"] = file_path
    else:
        file_path = kwargs["file_path"]
        module_id = kwargs.get("module_id", common_utils.get_module_dir_and_name(file_path)[1])
    simulator.add_provider(module_id, file_path, kwargs)

    simulator.run()


class ProviderBase(ModuleBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.output_cache_dir = self.cfg["output_cache_dir"]
        self.dir_name = self.cfg.get("dir_name", self.id)

        self.output_dir = os.path.join(self.output_cache_dir, DATA_DIR, self.dir_name)

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

    def append_data(self, data_name: str, data: np.ndarray, begin_trading_day: int = None, end_trading_day: int = None):
        self.dr.append_data(self.dir_name, data_name, data, begin_trading_day, end_trading_day, part_overwrite=self.overwrite)

    def write_compress_data(self, data_name: str, data: np.ndarray, begin_trading_day: int = None, end_trading_day: int = None):
        self.dr.write_compress_data(self.dir_name, data_name, data, begin_trading_day, end_trading_day, overwrite=self.overwrite)

    def append_compress_data(self, data_name: str, data: np.ndarray, begin_trading_day: int = None, end_trading_day: int = None):
        self.write_compress_data(data_name, data, begin_trading_day, end_trading_day)
