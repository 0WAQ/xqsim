from xqsim.common_module import *
from xqsim.base.provider_base import ProviderBase
from xqsim.data.data_repository import DataRepository

class ProviderManager(object):
    def __init__(self, dr: DataRepository):
        self.__dr = dr
        self.__meta = dr.meta
        self.__provider_list: list[ProviderBase] = []

    def add_provider(self, module_id, file_path, temp_config):
        config = self.__meta.global_cfg.copy()
        config.update(temp_config)
        config["id"] = module_id
        config["file_path"] = file_path

        cls = common_utils.getattr_fromfile(config["file_path"], "Provider")
        if cls is None:
            cls = common_utils.getattr_fromfile(config["file_path"], "create")
        if cls is None:
            abort(
                "No class Provider or create func in file %s",
                config["file_path"],
            )
        obj: ProviderBase = cls(self.__dr, config)
        self.__provider_list.append(obj)
        log_info("ProviderManager add provider: %s, file_path: %s", config["id"], config["file_path"])

    def run(self):
        for provider in self.__provider_list:
            provider.do_generate()

    def clear(self):
        self.__provider_list.clear()
