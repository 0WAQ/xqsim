from xqsim.common_module import *
from xqsim.data.data_repository import DataRepository
from xqsim.data.meta import Meta
from .utils import simcfg

class univbase(object):
    dates = []
    instruments = []

class ModuleBase(object):
    def __init__(self, *args):  # dr, cfg, meta
        self.dr: DataRepository = args[0]
        self.cfg: dict = args[1]
        self.meta: Meta = self.dr.meta
        self.id: str = simcfg.get(self.cfg, "id", "unknown_id") # type: ignore
        self.module_name: str = simcfg.get(self.cfg, "module_name", "unknown_module")   # type:ignore

        self.parent_module: ModuleBase | None = None
        self.children_module: list[ModuleBase] = []
