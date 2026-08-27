from qsim.common_module import *
from qsim.meta import Meta
from qsim.meta_loader import load_meta
from qsim.data_repository_impl import DataRepositoryImpl, DataViewImpl
from qsim.provider_manager import ProviderManager
from qsim.alpha_manager import AlphaManager, simcfg
import xml.etree.cElementTree as ET
import xmltodict
import json
from copy import copy
# import pickle
# import bz2
import _pickle as cPickle
import lz4.frame
from qsim.module_base import univbase


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


def load_xml(config_path, append_macro_dict=None):
    append_macro_dict = append_macro_dict or dict()
    with open(config_path) as reader:
        data = reader.read()
        # root = ET.fromstring(data)
        # xml_dict = dictify(root)
        xml_dict = json.loads(json.dumps(xmltodict.parse(data)).replace("@", ""))["QSim"]
        if "Macros" in xml_dict:
            macro_dict: dict = xml_dict["Macros"]
            macro_dict.update(append_macro_dict)
            xml_dict.pop("Macros")
            data = str(xml_dict)
            for k, v in macro_dict.items():
                data = data.replace("${%s}" % k, v)
            xml_dict = eval(data)
        # print(xml_dict)
        config_dict = {"global": {}, "provider": {}, "module": {}, "alpha": {}}

        def ensure_list(value):
            if value is None:
                return []
            if isinstance(value, list):
                return value
            return [value]

        config_dict["global"]["begin_date"] = xml_dict["Universe"]["startdate"]
        config_dict["global"]["end_date"] = xml_dict["Universe"]["enddate"]
        for k, v in xml_dict["Constants"].items():
            if k == "niodatapath":
                config_dict["global"]["meta_dir"] = xml_dict["Constants"]["niodatapath"]
            elif k == "backdays":
                config_dict["global"]["back_days"] = int(xml_dict["Constants"]["backdays"])
            else:
                config_dict["global"][k] = v

        if "Caches" in xml_dict:
            if isinstance(xml_dict["Caches"]["Cache"], dict):
                cache_list = [xml_dict["Caches"]["Cache"]]
            else:
                cache_list = xml_dict["Caches"]["Cache"]
            config_dict["global"]["cache_list"] = []
            for cache_dict in cache_list:
                config_dict["global"]["cache_list"].append(cache_dict["path"])
            # print(config_dict["global"]["cache_list"])

        providers_dict = xml_dict.get("Providers", None)
        if providers_dict is not None:
            if providers_dict.get("Local", None) is not None:
                config_dict["provider"]["local"] = providers_dict["Local"]
            for provider_dict in ensure_list(providers_dict.get("Provider", [])):
                provider_id = provider_dict["id"]
                provider_cfg = provider_dict.copy()
                provider_cfg.pop("id")
                config_dict["provider"][provider_id] = provider_cfg

        for module_dict in ensure_list(xml_dict["Modules"]["Module"]):
            if module_dict["handler"] == "AlphaHandler":
                config_dict["module"].setdefault("alpha", {})[module_dict["id"]] = module_dict["path"]
            elif module_dict["handler"] == "AlphaOpsHandler":
                config_dict["module"].setdefault("operation", {})[module_dict["id"]] = module_dict["path"]
            elif module_dict["handler"] == "StatsRegistry":
                config_dict["module"].setdefault("stats", {})[module_dict["id"]] = module_dict["path"]
            elif module_dict["handler"] == "PortfolioHandler":
                config_dict["module"].setdefault("portfolio", {})[module_dict["id"]] = module_dict["path"]

        portfolio_dict = xml_dict["Portfolio"]
        alpha_dict_list = portfolio_dict.get("Alpha", [])
        if isinstance(alpha_dict_list, dict):
            alpha_dict_list = [alpha_dict_list]
        alpha_dict_list.append(portfolio_dict)

        stats_dict = None
        if "Stats" in portfolio_dict:
            stats_dict = portfolio_dict["Stats"]

        alpha_id_set = set()
        for alpha_dict in alpha_dict_list:
            alpha_id = alpha_dict["id"]
            if alpha_id in alpha_id_set:
                abort("Alpha id replicated: %s", alpha_id)
            alpha_id_set.add(alpha_id)
            dic = config_dict["alpha"].setdefault(alpha_dict["id"], {})

            for k, v in alpha_dict.items():
                if k == "id":
                    continue
                if k == "moduleId":
                    dic["module_id"] = v
                    continue
                if k == "Operations":
                    if v is None:
                        continue
                    elif isinstance(v["Operation"], list):
                        for v2 in v["Operation"]:
                            op_list = dic.setdefault("operation", [])
                            v2["module_id"] = v2["moduleId"]
                            v2["id"] = alpha_id + "_op_" + str(len(op_list))
                            op_list.append(v2)
                    elif isinstance(v["Operation"], dict):
                        v2 = v["Operation"]
                        op_list = dic.setdefault("operation", [])
                        v2["module_id"] = v2["moduleId"]
                        v2["id"] = alpha_id + "_op_" + str(len(op_list))
                        op_list.append(v2)
                if k == "Stats":
                    stats_list = dic.setdefault("stats", [])
                    v["id"] = alpha_id + "_stats_" + str(len(stats_list))
                    v["module_id"] = v["moduleId"]
                    stats_list.append(v)
                dic[k] = v
            if "Stats" not in alpha_dict and stats_dict is not None:
                stats_list = dic.setdefault("stats", [])
                v = stats_dict.copy()
                v["id"] = alpha_id + "_stats_" + str(len(stats_list))
                v["module_id"] = v["moduleId"]
                stats_list.append(v)

        return config_dict


class Simulator(object):
    def __init__(self):
        self.__qsim_path = os.path.abspath(os.path.dirname(__file__))
        self.__macro_dict = {"qsim_modules": os.path.join(self.__qsim_path, "modules").replace("\\", "/")}

        self.__base_config: {}
        self.__dr: DataRepositoryImpl
        self.__provider_manager: ProviderManager
        self.__meta: Meta
        self.__alpha_manage: AlphaManager

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
        log_info("QSim path %s", self.__qsim_path)

        self.__base_config = base_config

        self.__chdir = simcfg.get(self.__base_config, "chdir", None)
        if self.__chdir is not None:
            os.chdir(self.__chdir)
        log_info("Working path %s", os.getcwd())

        self.__meta = load_meta(self.__base_config)
        self.__meta.set_para("output_cache_dir", simcfg.get(self.__base_config, "output_cache_dir", "./cc_temp"))
        self.__meta.set_para("overwrite", simcfg.get(self.__base_config, "overwrite", "append"))
        self.__meta.set_para("save", simcfg.get(self.__base_config, "save", False))
        self.__meta.set_para("save_csv", simcfg.get(self.__base_config, "save_csv", None))
        self.__meta.set_para("dynamic_save_csv", simcfg.get(self.__base_config, "dynamic_save_csv", None))
        self.__meta.set_para("save_csv_total", simcfg.get(self.__base_config, "save_csv_total", False))
        self.__meta.set_para("fillna", simcfg.get(self.__base_config, "fillna", False))
        self.__meta.set_para("save_memory", simcfg.get(self.__base_config, "save_memory", False))
        adj_window = simcfg.get(self.__base_config, "adj_window", -1)
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
            self.__dr.prepare()
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

    def __init_alpha(self, alpha_config):
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

    def __init(self, config_dict):
        # init base
        base_config = config_dict["global"]
        self.__init_base(base_config)

        # init provider
        provider_config = config_dict.get("provider", {})
        self.__init_provider(provider_config)

        # init module
        module_config = config_dict.get("module", {})
        self.__init_module(module_config)

        # init alpha
        alpha_config = config_dict.get("alpha", {})
        self.__init_alpha(alpha_config)

    def init_base_with_cmd(self, **kwargs):
        kwargs.update(dict(arg.split('=') for arg in sys.argv[1:] if "=" in arg))
        self.__init_base(kwargs)

    def init_with_config(self, config_path):
        self.__macro_dict["config"] = os.path.split(config_path)[0].replace("\\", "/")
        if config_path.endswith(".yml"):
            config_dict = common_utils.load_yaml(config_path, macro=True, append_macro_dict=self.__macro_dict)
        elif config_path.endswith(".xml"):
            config_dict = load_xml(config_path, append_macro_dict=self.__macro_dict)
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
        for cache_path in simcfg.get(self.__base_config, "cache_list", []):
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
