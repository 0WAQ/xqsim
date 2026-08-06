from fnmatch import fnmatch
import itertools
import datetime
from qsim.common_module import *
from qsim.data_repository import *

SEGMENT_CUBE_SIZE = 8


class DataViewImpl(DataView):
    def __init__(self, array_list, offset_di_list, name, dr, last_ti_list=None):
        self.array_list = array_list
        self.__array = self.array_list[0]
        self.__origin_shape = self.array_list[0].shape
        self.__offset_di_list = offset_di_list
        self.__name = name
        self.__reshape_2d: int = 1
        if last_ti_list is None:
            self.__end_ti_list = [-1, -1]
        else:
            self.__end_ti_list = last_ti_list
        self.dr = dr

    def __check_di(self, item):
        if isinstance(item, slice):
            if item.start is None or item.stop is None:
                abort("di slice invalid: %s, start and stop must not be None", item)
            if item.stop < item.start:
                abort("di slice invalid: %s, start should >= stop", item)
            start_di = int(item.start / self.__reshape_2d)
            stop_di = int(item.stop / self.__reshape_2d) - 1
        else:
            start_di = int(item / self.__reshape_2d)
            stop_di = int(item / self.__reshape_2d)
        di_size = int(self.__array.shape[0] / self.__reshape_2d)
        if stop_di - start_di > di_size:
            abort("di slice invalid: %s, stop di(%s) - start di(%s) should <= di_size(%s)", item, stop_di, start_di, di_size)
        if stop_di < self.__offset_di_list[0] or stop_di - self.__offset_di_list[0] >= di_size:
            # log_info("Need reload, name %s, stop di %s", self.__name, stop_di)
            self.dr.reload(self.__name, stop_di)
            # if data is not None:
            #     shape = self.__array.shape
            #     self.__array = data.view()
            #     self.__array.setflags(write=False)
            #     self.__offset_di_list[0] = offset_di
            #     if len(shape) == 2 and len(self.__array.shape) == 3:
            #         self.reshape_matrix()
            #     if len(shape) == 3 and len(self.__array.shape) == 2:
            #         self.reshape_cube()
        if stop_di < self.__offset_di_list[0] or stop_di - self.__offset_di_list[0] >= di_size:
            abort("Out of range: name %s, start di %s, end di %s, offset %s, di size %s", self.__name, start_di, stop_di, self.offset, di_size)
        if isinstance(item, slice):
            return slice(item.start - self.offset, item.stop - self.offset, item.step)
        else:
            return item - self.offset

    def __getitem__(self, item):
        if isinstance(item, tuple):
            array = self.__getitem__(item[0])
            return array[item[1:]]
        new_slice = self.__check_di(item)
        return self.__array[new_slice]

    def __repr__(self):
        return str(self.__dict__)

    def __str__(self):
        return str(self.__dict__)

    @property
    def shape(self):
        return self.__array.shape

    @property
    def dtype(self):
        return self.__array.dtype

    @property
    def offset(self):
        return self.__offset_di_list[0] * self.__reshape_2d

    @property
    def offset_di(self):
        return self.__offset_di_list[0]

    @property
    def data(self) -> np.ndarray:
        return self.__array

    @property
    def size(self):
        return self.__array.shape[0]

    @property
    def name(self):
        return self.__name

    def enable_write(self):
        self.__array.setflags(write=True)


class DataInfo(object):
    TYPE_FILE = "file"
    TYPE_DIR = "dir"

    def __init__(self, name, data_path, data_type, child_name=None):
        self.name = name
        self.data_path = data_path
        self.type = data_type
        self.file_name = child_name

        self.shape = None
        self.dtype = None


class DataHolder(object):
    def __init__(self, array: np.ndarray, offset_di, name, dr, data_info, header):
        self.offset_di_list = [offset_di]
        self.name = name
        self.array = array
        self.dr = dr
        self.data_info: DataInfo = data_info
        self.header: DataHeader = header

        self.segment_size = None
        self.next_reload_di = None
        self.pre_load_di = None
        self.back_days = 0
        self.last_ti_list = [None, -1]

    def update_offset(self, offset):
        self.offset_di_list[0] = offset

    def update_header(self, header):
        self.header: DataHeader = header
        self.last_ti_list[0] = int(header.last_trading_day)
        self.last_ti_list[1] = int(header.last_ti)

    def data_view(self):
        return DataViewImpl([self.array], self.offset_di_list, self.name, self.dr, self.last_ti_list)


class DataRepositoryImpl(DataRepository):
    FACTOR_PREFIX = "__alpha__"
    fields_name = ["open", "high", "low", "close", "preclose", "vwap", "volume", "value", "ret"]
    abbr_interval = {"km15": "minute15", "km5": "minute5", "km1": "minute1"}

    def __init__(self, meta: Meta, data_size_limit_m):
        self.__meta = meta
        self.__data_manager = DataManager(meta)
        self.__calendar: Calendar = Calendar(self.__meta)

        self.__loaded_data_dict = {}
        self.__data_path_dict = {}
        self.__index_dict = {}
        self.__scanned_cache_path = set()

        self.__adj_data_dict = {}
        self.__adj_data_manager = None

        self.__shm_cache_list = None
        self.__shm_data_path_dict = {}

        self.__scanned_data_dir_path = set()

        self.save_memory = self.__meta.get_para("save_memory")

        self.__data_size_limit = data_size_limit_m * 1024 * 1024
        log_info("DataRepository created, data size limit %sM, save memory %s", data_size_limit_m, self.save_memory)

    @staticmethod
    def get_name(file_path):
        file_name = os.path.basename(file_path)
        elements = file_name.split(".")
        if len(elements) < 4:
            log_warn("Scan invalid data, file name invalid: %s", file_name)
            return None
        data_name = ".".join(elements[0:-3])
        data_type = elements[-1]

        if data_type.startswith(DataManager.TYPE_FACTOR):
            data_name = DataRepositoryImpl.FACTOR_PREFIX + data_name
        return data_name

    def set_meta(self, meta):
        self.__meta = meta

    @property
    def meta(self) -> Meta:
        return self.__meta

    @property
    def inner_data_manager(self) -> DataManager:
        return self.__data_manager

    @property
    def calendar(self) -> Calendar:
        return self.__calendar

    def __get_data_holder(self, name: str) -> DataHolder:
        if name in self.__loaded_data_dict:
            data_holder = self.__loaded_data_dict[name]
        else:
            name = self.__check_and_load_data(name)
            if name not in self.__loaded_data_dict:
                abort("DataRepository cannot find data name: %s", name)
            data_holder = self.__loaded_data_dict[name]
            if self.save_memory:
                self.__loaded_data_dict.pop(name)
        return data_holder

    def __get_adj_data_holder(self, name: str) -> DataHolder:
        name = self.__check_and_load_data(name)
        if name not in self.__loaded_data_dict:
            abort("DataRepository cannot find data name: %s", name)
        return self.__loaded_data_dict[name]

    def create_data_view(self, data: np.ndarray, offset_di: int = -1, name: str = None) -> DataView:
        if offset_di == -1:
            offset_di = self.__meta.begin_di - self.__meta.max_back_days
        return DataViewImpl([data], [offset_di], name, self)

    def apply_function(self, *args) -> DataView:
        np_func = args[0]
        new_args = []
        for i in range(1, len(args)):
            if isinstance(args[i], DataViewImpl) or isinstance(args[i], DataView):
                new_args.append(args[i].data)
            else:
                new_args.append(args[i])
        data = np_func(*new_args)
        return self.create_data_view(data)

    def get_name_list(self) -> list:
        return list(self.__data_path_dict.keys())

    def get_data(self, *args):
        multi_data = {}
        for arg in args:
            if "*" in arg or "?" in arg:
                for name in self.__data_path_dict.keys():
                    if fnmatch(name, arg):
                        multi_data[name] = self.__get_data_holder(name).data_view()
            else:
                multi_data[arg] = self.__get_data_holder(arg).data_view()
                # log_info("finish: " + arg)
        if len(multi_data) == 1:
            return multi_data[list(multi_data.keys())[0]]
        else:
            return multi_data

    def get_alpha(self, name: str) -> DataView:
        return self.__get_data_holder(DataRepositoryImpl.FACTOR_PREFIX + name).data_view()

    def __load_segment_data(self, name, header, data_info) -> DataHolder:
        ti_size = int(header.ti_size)
        ii_size = int(header.ii_size)
        type_size = int(header.type_size)
        back_days = self.__meta.back_days
        segment_size = int(self.__data_size_limit / ti_size / ii_size / type_size)
        if segment_size < back_days * 1 + 1:
            segment_size = back_days * 1 + 1
            log_warn("Data %s segment size equals to back days * 1 + 1(%d), MAY BE VERY SLOW!!!", name, segment_size)
        if segment_size > self.__meta.di_size + back_days:
            segment_size = self.__meta.di_size + back_days

        next_reload_di = self.__meta.begin_di + segment_size - back_days
        pre_load_di = self.__meta.begin_di - back_days

        log_info("Data %s use segment load, segment size %s, back days %s, next reload di is %s", name, segment_size, back_days, next_reload_di)

        new_header_list = [header]
        data = self.__load_data(data_info, header, pre_load_di, next_reload_di - 1, new_header_list)
        data_holder = DataHolder(data, pre_load_di, name, self, data_info, new_header_list[0])
        data_holder.segment_size = segment_size
        data_holder.next_reload_di = next_reload_di
        data_holder.pre_load_di = pre_load_di
        data_holder.back_days = back_days
        return data_holder

    def __load_dat_data(self, data_info: DataInfo) -> DataHolder:
        name: str = data_info.name
        file_path: str = data_info.data_path

        header = DataManager.load_header(file_path)
        ti_size = int(header.ti_size)
        ii_size = int(header.ii_size)
        if ti_size * ii_size <= SEGMENT_CUBE_SIZE * self.__meta.ii_size or self.__data_size_limit <= 0 or file_path.endswith(DataManager.TYPE_LZ4):
            back_days = self.__meta.max_back_days
            valid_begin_di = self.__meta.begin_di - back_days
            data = self.__load_data(data_info, header, valid_begin_di, self.__meta.end_di, None)
            data_holder = DataHolder(data, valid_begin_di, name, self, data_info, header)
            data_holder.back_days = back_days
            data_holder.segment_size = self.__meta.di_size + self.__meta.back_days
            data_holder.next_reload_di = self.__meta.begin_di + data_holder.segment_size - back_days
            data_holder.pre_load_di = self.__meta.begin_di - back_days
            return data_holder
        elif ti_size * ii_size > SEGMENT_CUBE_SIZE * self.__meta.ii_size:
            return self.__load_segment_data(name, header, data_info)
        else:
            abort("size error, ti size %s, ii size %s", ti_size, ii_size)

    def __load_dir_data(self, data_info: DataInfo) -> DataHolder:
        name = data_info.name
        shm_path = None
        if name in self.__shm_data_path_dict:
            shm_path = self.__shm_data_path_dict[name].data_path
        header = DataManager.load_dir_header(data_info.data_path, str(self.meta.begin_trading_day), data_info.file_name, shm_path)
        if self.__data_size_limit > 0:
            return self.__load_segment_data(name, header, data_info)
        else:
            back_days = self.__meta.max_back_days
            valid_begin_di = self.__meta.begin_di - back_days
            new_header_list = [header]
            data = self.__load_data(data_info, header, valid_begin_di, self.__meta.end_di, new_header_list)
            return DataHolder(data, valid_begin_di, name, self, data_info, new_header_list[0])

    def __check_and_load_data(self, name: str):
        if name not in self.__data_path_dict:
            abort("DataRepository load data failed, data not found: %s", name)

        return_name: str
        return_name = name
        if name in self.__loaded_data_dict:
            return return_name
        data_info: DataInfo = self.__data_path_dict[name]
        if data_info.type == DataInfo.TYPE_FILE:
            data_holder = self.__load_dat_data(data_info)
        elif data_info.type == DataInfo.TYPE_DIR:
            data_holder = self.__load_dir_data(data_info)
        else:
            abort("Type error: %s", data_info.type)
            return
        data_holder.name = return_name  # name changed to adj name
        self.__loaded_data_dict[return_name] = data_holder

        # try load shm only end di
        # self.__load_shm_end_di(data_holder)

        return return_name

    def __load_data(self, data_info: DataInfo, header: DataHeader, begin_di, end_di,
                    new_header_list=None, begin_ti: int = None, end_ti: int = None, only_refresh=False) -> np.ndarray:
        data = None
        shm_path = None
        if self.__shm_cache_list is not None:
            if data_info.name in self.__shm_data_path_dict:
                shm_path = self.__shm_data_path_dict[data_info.name].data_path
        if only_refresh is True and shm_path is None:
            return np.array([None])
        if data_info.type == DataInfo.TYPE_FILE:
            shape, dtype_tuple = self.__data_manager.get_file_shape(data_info.data_path, header, end_di - begin_di + 1)
            if begin_ti is not None and end_ti is not None and len(shape) > 2:
                shape = (1, end_ti - begin_ti + 1, shape[2])
            data = np.zeros(shape, dtype_tuple[0])
            data = self.__data_manager.load_file_data(data_info.data_path,
                                                      self.__meta.total_date_index[begin_di],
                                                      self.__meta.total_date_index[end_di],
                                                      out=data,
                                                      shm_path=shm_path,
                                                      fillna=self.__meta.get_para("fillna"),
                                                      header_list=new_header_list,
                                                      begin_ti=begin_ti,
                                                      end_ti=end_ti)
        elif data_info.type == DataInfo.TYPE_DIR:
            data_path = os.path.join(data_info.data_path, str(self.meta.begin_trading_day), data_info.file_name)
            shape, dtype_tuple = self.__data_manager.get_file_shape(data_path, header, end_di - begin_di + 1)
            if begin_ti is not None and end_ti is not None and len(shape) > 2:
                shape = (1, end_ti - begin_ti + 1, shape[2])
            data = np.zeros(shape, dtype_tuple[0])
            data = self.__data_manager.load_dir_data(data_info.data_path,
                                                     data_info.file_name,
                                                     data,
                                                     self.__meta.date_index[begin_di],
                                                     self.__meta.date_index[end_di],
                                                     shm_path=shm_path,
                                                     fillna=self.__meta.get_para("fillna"),
                                                     header_list=new_header_list,
                                                     begin_ti=begin_ti,
                                                     end_ti=end_ti)

        else:
            abort("Data type error: %s", data_info.type)

        return data

    def scan_cache_path(self, cache_path: str):
        cache_path = common_utils.realpath(cache_path)
        if cache_path in self.__scanned_cache_path:
            return
        self.__scanned_cache_path.add(cache_path)
        log_info("Scan cache path %s", cache_path)
        self.__scan_path(cache_path)

    def reload(self, name, di):
        if name not in self.__loaded_data_dict:
            abort("DataRepository reload failed, data not loaded: %s", name)
        data_holder: DataHolder = self.__loaded_data_dict[name]
        if data_holder.segment_size is None:
            # segment size not found
            return

        if di >= data_holder.offset_di_list[0] and di - data_holder.offset_di_list[0] < data_holder.array.shape[0]:
            return

        data_info = data_holder.data_info
        header = data_holder.header

        if di + data_holder.segment_size - data_holder.back_days - 1 > self.__meta.end_di:
            # log_warn("load last")
            di = self.__meta.end_di + 1 + data_holder.back_days - data_holder.segment_size
        begin_load_di = di - data_holder.back_days
        end_load_di = begin_load_di + data_holder.segment_size - 1
        # current data and new data has same part
        if data_holder.pre_load_di <= begin_load_di <= data_holder.pre_load_di + data_holder.segment_size:
            same_begin_di_offset = begin_load_di - data_holder.pre_load_di
            same_di_size = data_holder.pre_load_di + data_holder.segment_size - begin_load_di
            data_holder.array[0: same_di_size] = data_holder.array[same_begin_di_offset: same_begin_di_offset + same_di_size]
            data = self.__load_data(data_info, header, begin_load_di + same_di_size, end_load_di)
            # log_warn("%s", data.shape)
            data_holder.array[same_di_size:] = data
        else:
            data = self.__load_data(data_info, header, begin_load_di, end_load_di)
            # log_warn("%s", data.shape)
            data_holder.array[:] = data
        data_holder.update_offset(begin_load_di)
        # data_holder.update_header(new_header_list[0])
        data_holder.pre_load_di = begin_load_di
        data_holder.next_reload_di = di + data_holder.segment_size - data_holder.back_days

    def __scan_shm_path(self):
        if self.__shm_cache_list is None:
            return
        self.__shm_data_path_dict.clear()
        for cache_path in self.__shm_cache_list:
            self.__scan_path(cache_path, shm=True)

    def __scan_path(self, cache_path: str, shm=False):
        if not os.path.exists(cache_path):
            # log_warn("Cache path %s not exist", cache_path)
            return
        for dir_name in os.listdir(cache_path):
            if dir_name == "meta":
                continue
            base_dir_path = os.path.join(cache_path, dir_name)
            if not shm:
                log_info("Find base dir %s", base_dir_path)
            for data_dir_name in os.listdir(base_dir_path):
                data_dir_path = os.path.join(base_dir_path, data_dir_name)
                if not os.path.isdir(data_dir_path):
                    continue
                for file_name in os.listdir(data_dir_path):
                    data_path = os.path.join(data_dir_path, file_name)
                    if os.path.isfile(data_path):
                        # file
                        data_name = DataRepositoryImpl.get_name(data_path)
                        if not data_name:
                            continue

                        if not shm:
                            if data_name in self.__data_path_dict:
                                log_warn("Scan duplicated data, data name: %s, use %s", data_name, data_path)
                            self.__data_path_dict[data_name] = DataInfo(data_name, data_path, DataInfo.TYPE_FILE)
                        else:
                            if data_name not in self.__data_path_dict:
                                self.__data_path_dict[data_name] = DataInfo(data_name, data_path, DataInfo.TYPE_FILE)
                            if data_name in self.__shm_data_path_dict:
                                continue
                            self.__shm_data_path_dict[data_name] = DataInfo(data_name, data_path, DataInfo.TYPE_FILE)
                        log_debug("Scan file data, name %s, path %s", data_name, data_path)
                    else:
                        # for performance, but shm cannot ignore, because shm will refresh each time
                        if not shm and data_dir_path in self.__scanned_data_dir_path:
                            continue

                        # dir YYYYMMDD
                        if len(file_name) != 8 or not file_name.isdigit():
                            continue

                        # for performance, if not shm, find begin trading day name dir
                        if not shm:
                            tmp_data_path = os.path.join(data_dir_path, str(self.__meta.begin_trading_day))
                            if os.path.isdir(tmp_data_path):
                                data_path = tmp_data_path
                            else:
                                log_debug("Cannot find data path %s", tmp_data_path)

                        # ignore invalid trading day
                        # trading_day = int(file_name)
                        # if trading_day not in self.__meta.di_mapping:   # avoid holiday but have
                        #     continue
                        # if not self.__meta.date_index[self.__meta.end_di] >= trading_day >= self.__meta.date_index[self.__meta.begin_di - self.__meta.max_back_days]:
                        #     continue

                        for child_file_name in os.listdir(data_path):
                            child_data_path = os.path.join(data_path, child_file_name)
                            data_name = DataRepositoryImpl.get_name(child_data_path)
                            if not data_name:
                                continue

                            if not shm:
                                if data_name in self.__data_path_dict:
                                    log_warn("Scan duplicated data, data name: %s, use %s", data_name, data_dir_path)
                                self.__data_path_dict[data_name] = DataInfo(data_name, data_dir_path, DataInfo.TYPE_DIR, child_file_name)
                            else:
                                if data_name not in self.__data_path_dict:
                                    self.__data_path_dict[data_name] = DataInfo(data_name, data_dir_path, DataInfo.TYPE_DIR, child_file_name)
                                if data_name in self.__shm_data_path_dict:
                                    continue
                                self.__shm_data_path_dict[data_name] = DataInfo(data_name, data_dir_path, DataInfo.TYPE_DIR, child_file_name)

                            log_debug("Scan dir data, name %s, path %s %s", data_name, data_path, child_file_name)
                        self.__scanned_data_dir_path.add(data_dir_path)

    def scan_all(self):
        log_info("Scan all")
        self.__data_path_dict.clear()
        self.__scanned_data_dir_path.clear()
        for cache_path in self.__scanned_cache_path:
            self.__scan_path(cache_path)

        self.__shm_data_path_dict.clear()
        self.set_shm_cache(self.__shm_cache_list)

    def set_shm_cache(self, shm_cache):
        if shm_cache is None:
            return
        if type(shm_cache) is list:
            shm_cache_list = shm_cache
        else:
            shm_cache_list = [shm_cache]
        for shm_cache in shm_cache_list:
            if not os.path.exists(shm_cache):
                log_warn("Set shm cache warning, path %s not exist", shm_cache)
                # return
        self.__shm_cache_list = shm_cache_list
        log_info("Set shm cache %s", self.__shm_cache_list)
        self.__scan_shm_path()

    def refresh(self, di=None, ti=None, names: list = None):
        return

    def __prepare_adj(self, di):
        adj_window = self.__meta.get_para("adj_window")
        price_list = ["close", "high", "low", "open", "vwap"]
        volume_list = ["volume"]
        if di is None:
            for name in price_list + volume_list:
                data_view = self.get_data("k." + name)
                data_holder = DataHolder(np.ndarray(shape=(adj_window + 1, self.__meta.ii_size), dtype=np.float64), data_view.offset_di, "k.adj_" + name, self, None, None)
                self.__loaded_data_dict[data_holder.name] = data_holder
            return

        adj = self.get_data("k.adj")
        if di == self.__meta.today_di:
            adj_data = adj[di - 1]
        else:
            adj_data = adj[di]
        for name in price_list:
            data_holder: DataHolder = self.__loaded_data_dict["k.adj_" + name]
            data_holder.array[:] = self.get_data("k." + name)[di - adj_window: di + 1] * adj[di - adj_window: di + 1] / adj_data
            data_holder.update_offset(di - adj_window)
        for name in volume_list:
            data_holder: DataHolder = self.__loaded_data_dict["k.adj_" + name]
            data_holder.array[:] = self.get_data("k." + name)[di - adj_window: di + 1] / adj[di - adj_window: di + 1] * adj_data
            data_holder.update_offset(di - adj_window)

    def prepare(self, di=None):
        if self.__meta.get_para("adj_window") > 0:
            self.__prepare_adj(di)

    # ====================== data manager proxy ======================

    def __get_output_dir(self, dir_name, data_type):
        output_dir = os.path.join(self.meta.get_para("output_cache_dir"), "Data" if data_type == DataManager.TYPE_DATA else "Alpha", dir_name)
        return output_dir

    def write_data(self, dir_name: str, data_name: str, data: np.ndarray, begin_trading_day: int = None, end_trading_day: int = None,
                   data_type: str = DataManager.TYPE_DATA, dimension: str = "", dtype: np.dtype = None, overwrite=False, compress=False):
        output_dir = self.__get_output_dir(dir_name, data_type)
        self.__data_manager.write_data(output_dir, data_name, data, begin_trading_day, end_trading_day, data_type, dimension, dtype, overwrite, compress)

    def write_compress_data(self, dir_name: str, data_name: str, data: np.ndarray, begin_trading_day: int = None, end_trading_day: int = None,
                            data_type: str = DataManager.TYPE_DATA, dimension: str = "", dtype: np.dtype = None, overwrite=False):

        output_dir = self.__get_output_dir(dir_name, data_type)
        self.__data_manager.write_compress_data(output_dir, data_name, data, begin_trading_day, end_trading_day, data_type, dimension, dtype, overwrite)

    def write_data_header_to_file(self, *args, **kwargs):
        self.__data_manager.write_data_header_to_file(*args, **kwargs)

    def append_data(self, dir_name: str, data_name: str, data: np.ndarray, begin_trading_day: int = None, end_trading_day: int = None,
                    data_type: str = DataManager.TYPE_DATA, dimension: str = "", dtype: np.dtype = None, part_overwrite=False):
        output_dir = self.__get_output_dir(dir_name, data_type)
        self.__data_manager.append_data(output_dir, data_name, data, begin_trading_day, end_trading_day, data_type, dimension, dtype, part_overwrite)

    def data_exist(self, *args, **kwargs) -> bool:
        return self.__data_manager.data_exist(*args, **kwargs)

    def remove_data(self, *args, **kwargs):
        return self.__data_manager.remove_data(*args, **kwargs)

    def load_data_from_file(self, *args, **kwargs) -> np.ndarray:
        return self.__data_manager.load_data_from_file(*args, **kwargs)

    def load_data_header_from_file(self, *args, **kwargs) -> (np.ndarray, DataHeader):
        return self.__data_manager.load_data_with_header(*args, **kwargs)

    def reindex_numpy(self, data: np.ndarray, index: list, default_value=np.nan, strict_match=True) -> np.ndarray:
        shape = data.shape
        if shape[-1] != len(index):
            abort("Data shape not match, %s != %s", shape, len(index))
        new_index = {}
        for i in range(len(index)):
            if index[i] not in self.__meta.ii_mapping:
                if strict_match is True:
                    abort("ii mapping cannot find %s", index[i])
                else:
                    continue
            new_index[self.__meta.ii_mapping[index[i]]] = i
        if len(new_index) == 0:
            abort("New index is empty, src index is %s", index)

        new_shape = list(shape)
        new_shape[-1] = self.__meta.ii_size
        new_data = np.full(shape=new_shape, fill_value=default_value, dtype=np.float64)
        if len(new_shape) == 1:
            new_data[list(new_index.keys())] = data[list(new_index.values())]
        elif len(new_shape) == 2:
            new_data[:, list(new_index.keys())] = data[:, list(new_index.values())]
        elif len(new_shape) == 3:
            new_data[:, :, list(new_index.keys())] = data[:, :, list(new_index.values())]
        else:
            abort("Data shape error: %s", shape)
        return new_data
