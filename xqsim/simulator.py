from xqsim.common_module import *
from xqsim.data.meta import Meta
from xqsim.data.meta_loader import load_meta
from xqsim.data.data_repository_impl import DataRepositoryImpl, DataViewImpl
from xqsim.manager.provider_manager import ProviderManager
from xqsim.manager.alpha_manager import AlphaManager, simcfg
import xml.etree.cElementTree as ET
from copy import copy
# import pickle
# import bz2
import _pickle as cPickle
import lz4.frame
from xqsim.base.module_base import univbase

def dictify(r, root=True):
    if root:
        return {r.tag: dictify(r, False)}
    d = copy(r.attrib)
    if r.text and r.text.strip() != "":
        d["_text"] = r.text.strip()
    for x in r.findall("./*"):
        if x.tag not in d:
            d[x.tag] = dictify(x, False)
        else:
            if not isinstance(d[x.tag], list):
                d[x.tag] = [d[x.tag]]
            d[x.tag].append(dictify(x, False))
    return d


class Simulator(object):
    def __init__(self):
        self.__xqsim_path = os.path.abspath(os.path.dirname(__file__))
        self.__macro_dict = {
            "xqsim_modules": os.path.join(self.__xqsim_path, "modules").replace("\\", "/")
        }

        self.__base_config: dict
        self.__dr: DataRepositoryImpl
        self.__provider_manager: ProviderManager
        self.__meta: Meta
        self.__alpha_manager: AlphaManager

        self.__module_config = {}

    @property
    def meta(self) -> Meta:
        return self.__meta

    @property
    def dr(self) -> DataRepositoryImpl:
        return self.__dr

    def __init_base(self, base_config):
        if "level" in base_config:
            set_log_level(base_config["level"])

        log_info("Simulator created with version %s, pid is %s", VERSION, os.getpid())
        log_info("QSim path %s", self.__xqsim_path)

        self.__base_config = base_config

        self.__chdir = simcfg.get(self.__base_config, "chdir", None)
        if self.__chdir is not None:
            os.chdir(self.__chdir)
        log_info("Working path %s", os.getcwd())

        self.__meta = load_meta(self.__base_config)
        self.__meta.set_para("output_cache_dir", simcfg.get(self.__base_config, "output_cache_dir", "./cc_temp"))
        # 数据目录层名: 默认 "Data" (嵌套布局); 配 "" 则数据目录直接挂在 output_cache_dir 下 (扁平布局, 期货用)
        self.__meta.set_para("data_dir", simcfg.get(self.__base_config, "data_dir", "Data"))
        self.__meta.set_para("overwrite", simcfg.get(self.__base_config, "overwrite", "append"))
        self.__meta.set_para("save", simcfg.get(self.__base_config, "save", False))
        self.__meta.set_para("save_csv", simcfg.get(self.__base_config, "save_csv", None))
        self.__meta.set_para("dynamic_save_csv", simcfg.get(self.__base_config, "dynamic_save_csv", None))
        self.__meta.set_para("save_csv_total", simcfg.get(self.__base_config, "save_csv_total", False))
        self.__meta.set_para("fillna", simcfg.get(self.__base_config, "fillna", False))
        self.__meta.set_para("save_memory", simcfg.get(self.__base_config, "save_memory", False))
        adj_window: int = simcfg.get(self.__base_config, "adj_window", -1)  # type: ignore
        if adj_window > self.__meta.back_days:
            abort("adj window(%s) should <= back days(%s)", adj_window, self.__meta.back_days)
        self.__meta.set_para("adj_window", adj_window)

        data_limit_size_m = simcfg.get(self.__base_config, "data_limit", -1)  # default data limit is 250M

        self.__dr = DataRepositoryImpl(self.__meta, data_limit_size_m)
        self.__provider_manager = ProviderManager(self.__dr)

        univbase.dates = self.__meta.date_index
        univbase.instruments = self.__meta.all_instrument_index

        if self.__meta.check_load_di is None:
            self.__alpha_manager = AlphaManager(self.__dr)
            self.__scan_cache()
            # self.__dr.prepare()
        else:
            log_info("checkpoint load start")
            with open(os.path.join(self.__meta.checkpoint_dir, ".list"), "r") as reader:
                content = reader.read()
                path_list = eval(content)
            for path in path_list:
                common_utils.dynamic_import(path)
            # with open(os.path.join(self.__meta.checkpoint_dir, "save.bin"), "rb") as reader:
            #     data = lz4.block.decompress(reader.read())
            #     self.__alpha_manager = cPickle.loads(data)
            with lz4.frame.LZ4FrameFile(os.path.join(self.__meta.checkpoint_dir, "save.bin"), "rb") as reader:
                self.__alpha_manager = cPickle.load(reader)
            self.__alpha_manager.set_meta(self.__meta)
            self.__dr = self.__alpha_manager.dr
            self.__dr.set_meta(self.__meta)

        log_info("Simulator init base finish")

    def __init_provider(self, provider_config):
        local_config = self.__meta.global_cfg.copy()
        local_config.update(provider_config.get("local", {}))
        for module_id, config in provider_config.items():
            if module_id == "local":
                continue
            config.update(local_config)
            self.__provider_manager.add_provider(module_id, config["file_path"], config)
        log_info("Simulator init provider finish")

    def __init_module(self, module_config):
        self.__module_config = module_config
        log_info("Simulator init module finish")

    def __init_alpha(self, alpha_config: dict[str, dict]):
        if self.__meta.check_load_di is not None:
            return
        local_config = self.__meta.global_cfg.copy()
        local_config.update(alpha_config.get("local", {}))

        for alpha_id, config in alpha_config.items():
            if alpha_id == "local":
                continue
            if "Alpha" in config:
                # portfolio
                if config.get("module_id", "") != "":
                    alpha_task = self.__alpha_manager.create_portfolio_task(local_config)
                    alpha_task.add_alpha(alpha_id, self.__module_config["portfolio"][config["module_id"]], config)
            else:
                # alpha
                alpha_task = self.__alpha_manager.create_alpha_task(local_config)
                alpha_task.add_alpha(alpha_id, self.__module_config["alpha"][config["module_id"]], config)

            # op
            op_config_list = config.get("operation", [])
            for i in range(len(op_config_list)):
                op_config_list[i]["file_path"] = self.__module_config["operation"][op_config_list[i]["module_id"]]
                alpha_task.add_op(op_config_list[i])

            # stats
            stats_config_list = config.get("stats", [])
            for i in range(len(stats_config_list)):
                stats_config_list[i]["file_path"] = self.__module_config["stats"][stats_config_list[i]["module_id"]]
                alpha_task.add_stats(stats_config_list[i])

        log_info("Simulator init alpha finish")

    def __init(self, config_dict: dict):
        # init base
        base_config: dict = config_dict["global"]
        self.__init_base(base_config)

        # init provider
        provider_config: dict = config_dict.get("provider", {})
        self.__init_provider(provider_config)

        # init module
        module_config: dict = config_dict.get("module", {})
        self.__init_module(module_config)

        # init alpha
        alpha_config: dict[str, dict] = config_dict.get("alpha", {})
        self.__init_alpha(alpha_config)

    def init_base_with_cmd(self, **kwargs):
        kwargs.update(dict(arg.split('=') for arg in sys.argv[1:] if "=" in arg))
        self.__init_base(kwargs)
   
    def init_with_config_path(self, config_path: str):
        self.__macro_dict["config"] = os.path.split(config_path)[0].replace("\\", "/")
        if config_path.endswith(".yml"):
            config_dict = common_utils.load_yaml(config_path, macro=True, append_macro_dict=self.__macro_dict)
        elif config_path.endswith(".xml"):
            config_dict = common_utils.load_xml(config_path, append_macro_dict=self.__macro_dict)
        else:
            raise Exception("config file name invalid")
        self.__init(config_dict)

    def init_with_config_dict(self, config_dict):
        self.__init(config_dict)

    def add_provider(self, module_id, file_path, config):
        self.__provider_manager.add_provider(module_id, file_path, config)

    def add_single_alpha(self, alpha_id, file_path, config):
        alpha_task = self.__alpha_manager.create_alpha_task()
        alpha_task.add_alpha(alpha_id, file_path, config)

    def add_alpha_module(self, cls, config):
        alpha_task = self.__alpha_manager.create_alpha_task()
        alpha_task.add_alpha_cls(cls, config)

    def clear(self):
        log_info("Simulator clear all task")
        self.__provider_manager.clear()
        self.__alpha_manager.clear()

    def __scan_cache(self):
        self.__dr.scan_cache_path(self.__meta.meta_dir)
        for cache_path in simcfg.get(self.__base_config, "cache_list", []): # type: ignore
            self.__dr.scan_cache_path(cache_path)
        shm_cache = simcfg.get(self.__base_config, "shm_cache", None)
        self.__dr.set_shm_cache(shm_cache)

    def __build(self):
        log_info("Builder start")
        self.__provider_manager.run()
        log_info("Builder finish")

    def __simulate(self):
        log_info("Simulator start")
        # print(self.__base_config)

        for di in range(self.__meta.begin_di, self.__meta.end_di + 1):
            self.__meta.current_di = di
            self.__dr.prepare(di)

            self.__alpha_manager.run_before_di(di)
            self.__alpha_manager.run(di)
            self.__alpha_manager.run_after_di(di)

            self.__alpha_manager.save(di)
            if di == self.__meta.check_save_di:
                # exit(0)
                log_info("checkpoint save start")
                os.makedirs(self.__meta.checkpoint_dir, exist_ok=True)
                # with open(os.path.join(self.__meta.checkpoint_dir, "save.bin"), "wb") as writer:
                #     pickle.dump(self.__alpha_manager, writer)
                with lz4.frame.LZ4FrameFile(os.path.join(self.__meta.checkpoint_dir, "save.bin"), "wb") as writer:
                    cPickle.dump(self.__alpha_manager, writer)
                with open(os.path.join(self.__meta.checkpoint_dir, ".date"), "w") as writer:
                    writer.write(str(self.__meta.date_index[self.__meta.check_save_di]))
                # log_info("module info %s", self.__alpha_manager.module_path_list())
                with open(os.path.join(self.__meta.checkpoint_dir, ".list"), "w") as writer:
                    writer.write(str(self.__alpha_manager.module_path_list()))

        self.__alpha_manager.save_stats()

        log_info("Simulator finish")

    def run(self):
        self.__build()
        if simcfg.get(self.__base_config, "build", False):
            log_info("Build mode, exit now")
            return
        self.__dr.scan_all()
        self.__simulate()
