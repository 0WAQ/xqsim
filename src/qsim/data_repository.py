import abc
import numpy as np
import pandas as pd
from qsim.data_manager import DataHeader, DataManager
from qsim.meta import Meta, Calendar

ADJ_NONE = DataHeader.ADJ_NONE
ADJ_PRICE = DataHeader.ADJ_PRICE
ADJ_VOLUME = DataHeader.ADJ_VOLUME


class DataView(abc.ABC):
    @abc.abstractmethod
    def __getitem__(self, item):
        return NotImplemented

    @property
    @abc.abstractmethod
    def shape(self):
        return NotImplemented

    @property
    @abc.abstractmethod
    def dtype(self):
        return NotImplemented

    @property
    @abc.abstractmethod
    def offset(self):
        return NotImplemented

    @property
    @abc.abstractmethod
    def offset_di(self):
        return NotImplemented

    @property
    @abc.abstractmethod
    def data(self) -> np.ndarray:
        return NotImplemented

    @property
    @abc.abstractmethod
    def size(self):
        return NotImplemented

    @property
    @abc.abstractmethod
    def name(self):
        return NotImplemented

    @abc.abstractmethod
    def enable_write(self):
        return NotImplemented


class DataRepository(abc.ABC):
    @property
    @abc.abstractmethod
    def meta(self) -> Meta:
        return NotImplemented

    @property
    @abc.abstractmethod
    def calendar(self) -> Calendar:
        return NotImplemented

    @abc.abstractmethod
    def create_data_view(self, data: np.ndarray, offset_di: int = -1, name: str = None) -> DataView:
        return NotImplemented

    @abc.abstractmethod
    def apply_function(self, *args) -> DataView:
        """
        :param args:
        args[0] is a function which return must be a ndarray.
        args[1:] is the params for the function.
        If DataView type found in args[1:], the arg will be converted to ndarray by calling DataView.data.
        :return: DataView
        created by the return of args[0] function by calling create_data_view.
        """
        return NotImplemented

    @abc.abstractmethod
    def get_name_list(self) -> list:
        return NotImplemented

    @abc.abstractmethod
    def get_data(self, *args):
        return NotImplemented

    def getdata(self, *args):
        return self.get_data(*args)

    @abc.abstractmethod
    def get_alpha(self, name: str) -> DataView:
        return NotImplemented

    @abc.abstractmethod
    def refresh(self, di=None, ti=None, names: list = None):
        return NotImplemented

    @abc.abstractmethod
    def prepare(self, di=None):
        return NotImplemented

    @abc.abstractmethod
    def write_data(self, dir_name: str, data_name: str, data: np.ndarray, begin_trading_day: int = None, end_trading_day: int = None,
                   data_type: str = DataManager.TYPE_DATA, dimension: str = "", dtype: np.dtype = None, overwrite=False, compress=False):
        return NotImplemented

    @abc.abstractmethod
    def write_compress_data(self, dir_name: str, data_name: str, data: np.ndarray, begin_trading_day: int = None, end_trading_day: int = None,
                            data_type: str = DataManager.TYPE_DATA, dimension: str = "", dtype: np.dtype = None, overwrite=False):
        return NotImplemented

    @abc.abstractmethod
    def write_data_header_to_file(self, *args, **kwargs):
        return NotImplemented

    @abc.abstractmethod
    def append_data(self, dir_name: str, data_name: str, data: np.ndarray, begin_trading_day: int = None, end_trading_day: int = None,
                    data_type: str = DataManager.TYPE_DATA, dimension: str = "", dtype: np.dtype = None, part_overwrite=False):
        return NotImplemented

    @abc.abstractmethod
    def data_exist(self, *args, **kwargs) -> bool:
        return NotImplemented

    @abc.abstractmethod
    def remove_data(self, *args, **kwargs):
        return NotImplemented

    @staticmethod
    def load_header_from_file(*args, **kwargs) -> DataHeader:
        return DataManager.load_header(*args, **kwargs)

    @abc.abstractmethod
    def load_data_from_file(self, *args, **kwargs) -> np.ndarray:
        return NotImplemented

    @abc.abstractmethod
    def load_data_header_from_file(self, *args, **kwargs) -> (np.ndarray, DataHeader):
        return NotImplemented

    @abc.abstractmethod
    def reindex_numpy(self, data: np.ndarray, index: list, default_value=np.nan, strict_match=True) -> np.ndarray:
        return NotImplemented
