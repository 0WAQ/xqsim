from xqsim.common_module import *
from ctypes import *
from numcodecs import Blosc

# Notice: str must be bytes!

DATA_HEADER_LENGTH = 1024

DATA_TYPE_FILE_DICT = {"float64": "f", "int64": "i", "bool": "b"}

DATA_FILE_TYPE_DICT = {"f": (np.float64, 8), "i": (np.int64, 8), "b": (np.bool_, 1)}


class DataHeader(Structure):
    ADJ_NONE = "adj_none"
    ADJ_PRICE = "adj_p"
    ADJ_VOLUME = "adj_v"

    _fields_ = [
        ("begin_trading_day", c_char * 8),
        ("end_trading_day", c_char * 8),
        ("di_size", c_char * 8),
        ("last_trading_day", c_char * 8),
        ("last_ti", c_char * 8),
        ("ti_size", c_char * 8),
        ("ii_size", c_char * 8),
        ("type_size", c_char * 8),
        ("adj_mode", c_char * 8)
    ]

    def encode(self):
        return string_at(addressof(self), sizeof(self))

    def decode(self, data):
        memmove(addressof(self), data, sizeof(self))
        return len(data)

    def __str__(self):
        return str({"begin_trading_day": self.begin_trading_day, "end_trading_day": self.end_trading_day, "di_size": self.di_size,
                    "last_trading_day": self.last_trading_day, "last_ti": self.last_ti, "ti_size": self.ti_size,
                    "ii_size": self.ii_size, "type_size": self.type_size, "adj_mode": self.adj_mode})

    def __repr__(self):
        return self.__str__()


class DataManager(object):
    TYPE_DATA = "dat"
    TYPE_FACTOR = "fac"
    TYPE_LZ4 = "lz4"

    def __init__(self, meta: Meta):
        self.__meta = meta
        self.__compressor = Blosc(cname='lz4hc', clevel=1, shuffle=Blosc.SHUFFLE)

    def get_path(self, dir_path: str, data_name: str, data: np.ndarray, 
                 data_type: str, dimension: str = "", dtype: np.dtype | None = None, 
                 trading_day: str | None = None, shape=None, compress=True):
        if shape is None:
            shape = data.shape
        if dimension == "":
            if len(shape) == 3:
                dimension += "C" + str(shape[2]) if shape[2] != self.__meta.ii_size else "C"
                dimension += "M" + str(shape[1]) if shape[1] != self.__meta.ii_size else "M"
            elif len(shape) == 2:
                dimension += "M" + str(shape[1]) if shape[1] != self.__meta.ii_size else "M"
            else:
                abort("dimension error: %s", shape)

        if dtype is None:
            dtype = data.dtype

        if trading_day is None:
            file_path = os.path.join(common_utils.realpath(dir_path), data_name + "." + dimension + "." + DATA_TYPE_FILE_DICT[str(dtype)] + "." + data_type)
        else:
            file_path = os.path.join(common_utils.realpath(dir_path),
                                     trading_day,
                                     data_name + "." + dimension + "." + DATA_TYPE_FILE_DICT[str(dtype)] + "." + data_type + (DataManager.TYPE_LZ4 if compress else ""))
        return file_path

    def check_date(self, begin_trading_day: int | None, end_trading_day: int | None):
        if begin_trading_day is None:
            begin_trading_day = self.__meta.begin_trading_day
        if end_trading_day is None:
            end_trading_day = self.__meta.end_trading_day
        abort_if(self.__meta.total_di_mapping.get(begin_trading_day, None) is None or self.__meta.total_di_mapping.get(end_trading_day, None) is None,
                 "date must be trading day")
        return begin_trading_day, end_trading_day, self.__meta.total_di_mapping[end_trading_day] - self.__meta.total_di_mapping[begin_trading_day] + 1

    def write_data(self, dir_path: str, data_name: str, data: np.ndarray, 
                   begin_trading_day: int | None = None, end_trading_day: int | None = None,
                   data_type: str = TYPE_DATA, dimension: str = "", 
                   dtype: np.dtype | None = None, overwrite=False, compress=False):
        file_path = self.get_path(dir_path, data_name, data, data_type, dimension, dtype)
        if compress is True:
            file_path += DataManager.TYPE_LZ4
        if not overwrite and os.path.exists(file_path):
            log_error("Write data failed, file exist: %s", file_path)
            return

        self.write_data_to_file(file_path, data, begin_trading_day, end_trading_day)

    def write_compress_data(self, dir_path: str, data_name: str, data: np.ndarray, 
                            begin_trading_day: int | None = None, end_trading_day: int | None = None,
                            data_type: str = TYPE_DATA, dimension: str = "", 
                            dtype: np.dtype | None = None, overwrite=False):
        if begin_trading_day is None:
            begin_trading_day = self.__meta.begin_trading_day
        if end_trading_day is None:
            end_trading_day = self.__meta.end_trading_day
        trading_day_list = list(self.__meta.di_mapping.irange(begin_trading_day, end_trading_day))
        for i in range(len(trading_day_list)):
            trading_day = trading_day_list[i]
            file_path = self.get_path(dir_path, data_name, data, data_type, dimension, dtype, str(trading_day))
            if not overwrite and os.path.exists(file_path):
                log_error("Write compress data failed, file exist: %s", file_path)
                return
            output_data = data[i].view()
            output_data.shape = (1,) + output_data.shape
            self.write_data_to_file(file_path, output_data, trading_day, trading_day)
        log_info("Write compress data (%s -- %s) finish: %s/%s", begin_trading_day, end_trading_day, dir_path, data_name)

    def append_data(self, dir_path: str, data_name: str, data: np.ndarray, 
                    begin_trading_day: int | None = None, end_trading_day: int | None = None,
                    data_type: str = TYPE_DATA, dimension: str = "", 
                    dtype: np.dtype | None = None, part_overwrite=False):
        file_path = self.get_path(dir_path, data_name, data, data_type, dimension, dtype)
        if not os.path.exists(file_path):
            self.write_data_to_file(file_path, data, begin_trading_day, end_trading_day)
            return
        self.append_data_to_file(file_path, data, begin_trading_day, end_trading_day, part_overwrite)

    def append_data_by_ti(self, dir_path: str, data_name: str, data: np.ndarray, trading_day: int, ti: int, ti_size: int, data_type: str = TYPE_DATA, date_dir=True):
        if len(data.shape) != 1:
            abort("Append by ti failed, shape error: %s", data.shape)
        ii_size = data.shape[0]

        file_path = self.get_path(dir_path,
                                  data_name,
                                  data,
                                  data_type,
                                  trading_day=str(trading_day) if date_dir is True else None,
                                  shape=(1, ti_size, ii_size),
                                  compress=False)
        if ti >= ti_size:
            abort("Append by ti failed, ti(%s) >= ti_size(%s)", ti, ti_size)
        # if file_path not in self.fp_dict:
        #     if not os.path.exists(file_path):
        #         fp: np.memmap = np.memmap(file_path, data.dtype, "w+", DATA_HEADER_LENGTH, (ti_size, shape))
        #         fp.fill(np.nan)
        #         fp[ti] = data
        #         fp.flush()
        #
        #         self.fp_dict[file_path] = fp
        #     else:
        #         pass
        # else:
        #     fp = self.fp_dict[file_path]
        # if file_path not in self.fp_dict:
        data_header = DataHeader()
        if not os.path.exists(file_path):
            common_utils.ensure_dir(file_path)
            with open(file_path, "wb") as writer:
                data_header.begin_trading_day = str(trading_day).encode("utf-8")
                data_header.end_trading_day = str(trading_day).encode("utf-8")
                data_header.di_size = str(1).encode("utf-8")
                data_header.ti_size = str(ti_size).encode("utf-8")
                data_header.last_trading_day = str(trading_day).encode("utf-8")
                data_header.last_ti = str(ti).encode("utf-8")
                data_header.ii_size = str(ii_size).encode("utf-8")
                data_header.type_size = str(DATA_FILE_TYPE_DICT[DATA_TYPE_FILE_DICT[str(data.dtype)]][1]).encode("utf-8")
                writer.write(data_header.encode())
                writer.seek(DATA_HEADER_LENGTH)
                nan_array = np.full((ti_size, ii_size), np.nan, np.float64)
                nan_array[ti] = data
                nan_array.tofile(writer)
            return
        else:
            with open(file_path, "r+b") as writer:
                data_header.decode(writer.read(DATA_HEADER_LENGTH))
                cur_begin_di, cur_end_di, new_begin_di, new_end_di = self.check_before_append(data_header, trading_day, trading_day, True)
                if int(data_header.ti_size) != ti_size:
                    abort("Append by ti failed, ti size not match, %s != %s", int(data_header.ti_size), ti_size)
                if int(data_header.ii_size) != ii_size:
                    abort("Append by ti failed, ii size not match, %s != %s", int(data_header.ii_size), ii_size)
                if new_end_di > cur_end_di:
                    # append di data
                    nan_array = np.full((ti_size, data.shape), np.nan, np.float64)  # type: ignore
                    nan_array[ti] = data

                    data_header.end_trading_day = str(trading_day).encode("utf-8")
                    data_header.di_size = str(int(data_header.di_size) + 1).encode("utf-8")
                    data_header.last_ti = str(ti).encode("utf-8")
                    writer.seek(DATA_HEADER_LENGTH + (new_begin_di - cur_begin_di) * int(data_header.ii_size) * int(data_header.ti_size) * int(data_header.type_size))
                    nan_array.tofile(writer)
                    writer.seek(0)
                    writer.write(data_header.encode())
                    writer.flush()
                else:
                    # no append di
                    data_header.last_ti = str(ti).encode("utf-8")
                    type_size = int(data_header.type_size)
                    offset = DATA_HEADER_LENGTH + (new_begin_di - cur_begin_di) * ii_size * ti_size * type_size
                    offset += ti * ii_size * type_size
                    writer.seek(offset)
                    data.tofile(writer)
                    writer.seek(0)
                    writer.write(data_header.encode())
                    writer.flush()
        # log_info("Append by ti(%s) to (%s -- %s) finish: %s", ti, data_header.begin_trading_day, data_header.end_trading_day, file_path)
        return file_path

    def data_exist(self, dir_path: str, data_name: str, data: np.ndarray, 
                   data_type: str, dimension: str = "", dtype: np.dtype | None = None):
        file_path = self.get_path(dir_path, data_name, data, data_type, dimension, dtype)
        return os.path.exists(file_path)

    def remove_data(self, dir_path: str, data_name: str, data: np.ndarray, data_type: str,
                    dimension: str = "", dtype: np.dtype | None = None):
        file_path = self.get_path(dir_path, data_name, data, data_type, dimension, dtype)
        if os.path.exists(file_path):
            os.remove(file_path)
            log_info("Remove data %s", file_path)

    def write_data_header_to_file(self, file_path: str, data: np.ndarray, data_header: DataHeader):
        compress_flag = True if file_path.endswith(DataManager.TYPE_LZ4) else False

        common_utils.ensure_dir(file_path)

        if not data.flags.c_contiguous:
            abort("data.flags.c_contiguous must be True, but given False")

        with open(file_path, "wb") as writer:
            writer.write(data_header.encode())
            writer.seek(DATA_HEADER_LENGTH)
            if compress_flag is False:
                data.tofile(writer)
            else:
                compressed = self.__compressor.encode(data.data)
                writer.write(compressed)

    def write_data_to_file(self, file_path: str, data: np.ndarray, begin_trading_day: int | None, end_trading_day: int | None):
        begin_trading_day, end_trading_day, di_size = self.check_date(begin_trading_day, end_trading_day)
        abort_if(di_size != data.shape[0],
                 "Write date failed, di size(%s) != data shape[0](%s)", di_size, data.shape[0])

        data_header = DataHeader()
        data_header.begin_trading_day = str(begin_trading_day).encode("utf-8")
        data_header.end_trading_day = str(end_trading_day).encode("utf-8")
        data_header.di_size = str(di_size).encode("utf-8")
        if len(data.shape) == 3:
            data_header.ti_size = str(data.shape[1]).encode("utf-8")
            data_header.last_trading_day = str(end_trading_day).encode("utf-8")
            data_header.last_ti = str(data.shape[1] - 1).encode("utf-8")
            data_header.ii_size = str(data.shape[2]).encode("utf-8")
        else:
            data_header.ti_size = str(1).encode("utf-8")
            data_header.last_trading_day = str(end_trading_day).encode("utf-8")
            data_header.last_ti = str(0).encode("utf-8")
            data_header.ii_size = str(data.shape[1]).encode("utf-8")
        data_header.type_size = str(DATA_FILE_TYPE_DICT[DATA_TYPE_FILE_DICT[str(data.dtype)]][1]).encode("utf-8")

        self.write_data_header_to_file(file_path, data, data_header)

        if file_path.endswith(DataManager.TYPE_DATA):
            log_info("Write data (%s -- %s) finish: %s", begin_trading_day, end_trading_day, file_path)

    def check_before_append(self, data_header, begin_trading_day: int, end_trading_day: int, part_overwrite: bool):
        cur_begin_di = self.__meta.total_di_mapping[int(data_header.begin_trading_day)]
        cur_end_di = self.__meta.total_di_mapping[int(data_header.end_trading_day)]
        new_begin_di = self.__meta.total_di_mapping[begin_trading_day]
        new_end_di = self.__meta.total_di_mapping[end_trading_day]

        if not part_overwrite:
            # must append after last
            abort_if(cur_end_di + 1 != new_begin_di,
                     "Append failed, trading day not match, data end day(%s) + 1 != begin day(%s)", data_header.end_trading_day, begin_trading_day)
        else:
            # can change data
            abort_if(cur_begin_di > new_begin_di,
                     "Append failed, trading day not match, data begin day(%s) > begin day(%s)", data_header.begin_trading_day, begin_trading_day)
            abort_if(cur_end_di + 1 < new_begin_di,
                     "Append failed, trading day not match, data end day(%s) + 1 < begin day(%s)", data_header.end_trading_day, begin_trading_day)
        return cur_begin_di, cur_end_di, new_begin_di, new_end_di

    def append_data_to_file(self, file_path: str, data: np.ndarray, begin_trading_day: int | None, end_trading_day: int | None, part_overwrite: bool):
        begin_trading_day, end_trading_day, di_size = self.check_date(begin_trading_day, end_trading_day)

        data_header = DataHeader()
        with open(file_path, "r+b") as writer:
            data_header.decode(writer.read(DATA_HEADER_LENGTH))
            cur_begin_di, cur_end_di, new_begin_di, new_end_di = self.check_before_append(data_header, begin_trading_day, end_trading_day, part_overwrite)
            writer.seek(DATA_HEADER_LENGTH + (new_begin_di - cur_begin_di) * int(data_header.ii_size) * int(data_header.ti_size) * int(data_header.type_size), 0)
            data.tofile(writer)

            src_end_trading_day = data_header.end_trading_day
            if new_end_di >= cur_end_di:
                # need change header
                data_header.end_trading_day = str(end_trading_day).encode("utf-8")
                data_header.di_size = str(int(data_header.di_size) + di_size).encode("utf-8")
                writer.seek(0)
                writer.write(data_header.encode())

            if file_path.endswith(DataManager.TYPE_DATA):
                log_info("Append data from (%s -- %s) to (%s -- %s) finish: %s",
                         data_header.begin_trading_day, src_end_trading_day, data_header.begin_trading_day, data_header.end_trading_day, file_path)

    # ====================== load ==================== #

    def load_data_from_file(self, file_path: str, begin_trading_day: int | None = None, 
                            end_trading_day: int | None = None, total=False, out=None, fillna=False,
                            begin_ti: int | None = None, end_ti: int | None = None) -> np.ndarray:
        return self.load_data_with_header(file_path, begin_trading_day, end_trading_day, total, out, fillna, begin_ti, end_ti)[0]

    def __get_range_list(self, shm_path, begin_trading_day, end_trading_day):
        begin_di = self.__meta.di_mapping[begin_trading_day]
        end_di = self.__meta.di_mapping[end_trading_day]
        if shm_path and os.path.exists(shm_path):
            header: DataHeader = DataManager.load_header(shm_path)
            shm_begin_di = self.__meta.di_mapping[int(header.begin_trading_day)]
            shm_end_di = self.__meta.di_mapping[int(header.end_trading_day)]
            if shm_begin_di > end_di or shm_end_di < begin_di:
                # shm cache miss
                return [(0, begin_di, end_di)]
            if shm_begin_di < begin_di:
                shm_begin_di = begin_di
            if shm_end_di > end_di:
                shm_end_di = end_di
            if shm_end_di < shm_begin_di:
                abort("something maybe wrong: %s %s %s %s", shm_begin_di, shm_end_di, begin_di, end_di)

            # add range into list
            # (type, begin_di, end_di), type 0 means file, type 1 means shm
            range_list = []
            if shm_begin_di > begin_di:
                range_list.append((0, begin_di, shm_begin_di - 1))
            range_list.append((1, shm_begin_di, shm_end_di))
            if shm_end_di < end_di:
                range_list.append((0, shm_end_di + 1, end_di))
            return range_list
        else:
            return [(0, begin_di, end_di)]

    def load_file_data(self, file_path: str, begin_trading_day: int | None = None, 
                       end_trading_day: int | None = None, out=None,
                       shm_path: str | None = None, fillna=False, header_list=None, 
                       begin_ti: int | None = None, end_ti: int | None = None) -> np.ndarray:
        data: np.ndarray = out  # type: ignore
        range_list = self.__get_range_list(shm_path, begin_trading_day, end_trading_day)
        begin_di = self.__meta.di_mapping[begin_trading_day]
        header = None
        for range_tuple in range_list:
            # (type, begin_di, end_di), type 0 means file, type 1 means shm
            if range_tuple[0] == 0:
                # file
                header = self.load_data_with_header(file_path,
                                                    self.__meta.date_index[range_tuple[1]],
                                                    self.__meta.date_index[range_tuple[2]],
                                                    total=False,
                                                    out=data[range_tuple[1] - begin_di: range_tuple[2] - begin_di + 1],
                                                    fillna=fillna,
                                                    begin_ti=begin_ti,
                                                    end_ti=end_ti)[1]

            elif range_tuple[0] == 1:
                # shm
                header = self.load_data_from_file(shm_path,
                                                  self.__meta.date_index[range_tuple[1]],
                                                  self.__meta.date_index[range_tuple[2]],
                                                  total=False,
                                                  out=data[range_tuple[1] - begin_di: range_tuple[2] - begin_di + 1],
                                                  fillna=False,
                                                  begin_ti=begin_ti,
                                                  end_ti=end_ti)[1]
        if header_list is not None:
            header_list[0] = header
        return data

    @staticmethod
    def get_dir_path(dir_path: str, date: str, file_name: str, shm_path: str | None) -> tuple[bool, str]:
        find_file_flag = False
        file_path = os.path.join(dir_path, date, file_name)
        if shm_path:
            if os.path.exists(os.path.join(shm_path, date, file_name)):
                file_path = os.path.join(shm_path, date, file_name)
                log_debug("File %s found in shm data path %s", file_name, shm_path)
                find_file_flag = True
            elif os.path.exists(os.path.join(shm_path, date, file_name[:-3])):  # remove lz4
                file_path = os.path.join(shm_path, date, file_name[:-3])
                log_debug("File %s found in shm data path %s", file_name, shm_path)
                find_file_flag = True

        if not find_file_flag:
            if os.path.exists(file_path):
                find_file_flag = True
            elif os.path.exists(file_path + DataManager.TYPE_LZ4):
                file_path += DataManager.TYPE_LZ4
                find_file_flag = True
        return find_file_flag, file_path

    def load_dir_data(self, dir_path: str, file_name: str, data: np.ndarray, 
                      begin_trading_day: int | None = None, end_trading_day: int | None = None, total=False,
                      shm_path=None, fillna=False, header_list=None, 
                      begin_ti: int | None = None, end_ti: int | None = None) -> np.ndarray:
        header = None
        if total is False:
            begin_di = self.__meta.di_mapping[begin_trading_day]
            end_di = self.__meta.di_mapping[end_trading_day]
            trading_day_list = [self.__meta.date_index[di] for di in range(begin_di, end_di + 1)]
        else:
            trading_day_list = [int(trading_day) for trading_day in os.listdir(dir_path)]
        for i in range(len(trading_day_list)):
            find_file_flag, file_path = DataManager.get_dir_path(dir_path, str(trading_day_list[i]), file_name, shm_path)
            if not find_file_flag:
                if fillna is False:
                    abort("File %s not found at trading day %s", file_name, trading_day_list[i])
                else:
                    log_warn("File %s not found at trading day %s", file_name, trading_day_list[i])
                    data[i].fill(np.nan)
                    continue

            header = self.load_data_with_header(file_path, trading_day_list[i], trading_day_list[i], 
                                                out=data[i], begin_ti=begin_ti, end_ti=end_ti)[1]
        # if len(data_list) and data_list[0] is not None:
        #     np.concatenate(data_list, out=data)
        if header_list is not None:
            header_list[0] = header
        return data

    @staticmethod
    def load_header(file_path: str) -> DataHeader:
        data_header = DataHeader()
        with open(file_path, "rb") as reader:
            data_header.decode(reader.read(DATA_HEADER_LENGTH))
            return data_header

    @staticmethod
    def load_dir_header(dir_path, date, file_name, shm_path: str | None = None) -> DataHeader:
        find_file_flag, file_path = DataManager.get_dir_path(dir_path, str(date), file_name, shm_path)
        if not find_file_flag:
            abort("Header path %s %s %s %s not exist", dir_path, date, file_name, shm_path)
        return DataManager.load_header(file_path)

    def get_file_shape(self, file_path: str, data_header, di_count: int):
        log_debug("get_file_shape %s", file_path)
        file_name = os.path.basename(file_path)
        elements = file_name.split(".")
        abort_if(len(elements) < 4, "Load data failed, file name invalid: %s", file_name)

        dimension = elements[-3]
        shape = [di_count]
        if dimension[0] == "M":
            if len(dimension) == 1:
                shape = (di_count, self.__meta.ii_size)
            else:
                shape = (di_count, int(dimension[1:]))
        elif dimension[0] == "C":
            if "M" in dimension:
                shape2 = self.__meta.ii_size if dimension[1] == "M" else int(dimension[1:dimension.index("M")])
                shape1 = self.__meta.ii_size if dimension[-1] == "M" else int(dimension[dimension.index("M") + 1:])
                shape = (di_count, shape1, shape2)
            else:
                # deprecated!!
                shape = (di_count, int(dimension[1:]), self.__meta.ii_size)
        else:
            abort("Load data failed, dimension invalid: %s", dimension)

        abort_if(int(data_header.ti_size) != (shape[1] if len(shape) == 3 else 1),
                 "Check ti size failed: %s != %s", int(data_header.ti_size), (shape[1] if len(shape) == 3 else 1))

        abort_if(int(data_header.ii_size) != (shape[2] if len(shape) == 3 else shape[1]),
                 "Check ii size failed: %s != %s", int(data_header.ii_size), (shape[2] if len(shape) == 3 else shape[1]))

        dtype_tuple = DATA_FILE_TYPE_DICT[elements[-2]]
        abort_if(int(data_header.type_size) != dtype_tuple[1],
                 "Check type size failed: %s != %s", int(data_header.type_size), dtype_tuple[1])

        return shape, dtype_tuple

    def load_data_with_header(self, file_path: str, begin_trading_day: int | None = None, 
                              end_trading_day: int | None = None, total=False, out=None,
                              fillna=False, begin_ti: int | None = None, end_ti: int | None = None) -> tuple[np.ndarray, DataHeader]:
        data_header = DataHeader()
        with open(file_path, "rb") as reader:
            data_header.decode(reader.read(DATA_HEADER_LENGTH))

            data_begin_trading_day = int(data_header.begin_trading_day)
            data_end_trading_day = int(data_header.end_trading_day)

            forward_fill_di_size = 0
            backward_fill_di_size = 0

            data_di_count = self.__meta.total_di_mapping[data_end_trading_day] - self.__meta.total_di_mapping[data_begin_trading_day] + 1

            if not total:
                if begin_trading_day is None:
                    begin_trading_day = self.__meta.begin_trading_day
                if end_trading_day is None:
                    end_trading_day = self.__meta.end_trading_day

                begin_di = self.__meta.total_di_mapping[begin_trading_day]
                end_di = self.__meta.total_di_mapping[end_trading_day]
                di_count = end_di - begin_di + 1
                load_di_offset = begin_di - self.__meta.total_di_mapping[data_begin_trading_day]
                if fillna is False:
                    if data_begin_trading_day > begin_trading_day:
                        abort("Load data warning, data begin trading day(%s) > begin trading day(%s), file path %s",
                              data_begin_trading_day, begin_trading_day, file_path)

                    if data_end_trading_day < end_trading_day:
                        abort("Load data warning, data end trading day(%s) < end trading day(%s), file path %s",
                              data_end_trading_day, end_trading_day, file_path)

                    load_di_count = di_count
                    if load_di_count > data_di_count:
                        abort("Load data %s, load_di_count(%s) > data_di_count(%s), load all", file_path, load_di_count, data_di_count)

                else:
                    if data_begin_trading_day > begin_trading_day:
                        log_warn("Load data warning, data begin trading day(%s) > begin trading day(%s), file path %s",
                                 data_begin_trading_day, begin_trading_day, file_path)
                        forward_fill_di_size = self.__meta.total_di_mapping[data_begin_trading_day] - begin_di
                        begin_load_di = self.__meta.total_di_mapping[data_begin_trading_day]
                    else:
                        begin_load_di = begin_di

                    if data_end_trading_day < end_trading_day:
                        log_warn("Load data warning, data end trading day(%s) < end trading day(%s), file path %s",
                                 data_end_trading_day, end_trading_day, file_path)
                        backward_fill_di_size = end_di - self.__meta.total_di_mapping[data_end_trading_day]
                        end_load_di = self.__meta.total_di_mapping[data_end_trading_day]
                    else:
                        end_load_di = end_di

                    load_di_count = end_load_di - begin_load_di + 1
                    if load_di_count < 0:
                        load_di_count = 0
                        load_di_offset = 0
                    if load_di_offset < 0:
                        load_di_offset = 0

            else:
                load_di_count = data_di_count
                load_di_offset = 0
                di_count = load_di_count

            shape, dtype_tuple = self.get_file_shape(file_path, data_header, di_count)

            each_di_size = 1
            for i in range(1, len(shape)):
                each_di_size *= shape[i]

            offset = load_di_offset * each_di_size * dtype_tuple[1]
            count = load_di_count * each_di_size

            if begin_ti is not None and end_ti is not None and len(shape) > 2:
                if begin_ti > end_ti or end_ti >= shape[1]:
                    abort("Load data %s failed, begin_ti %s, end_ti %s, shape %s", file_path, begin_ti, end_ti, shape)
                each_ti_size = 1
                for i in range(2, len(shape)):
                    each_ti_size *= shape[i]
                offset += begin_ti * each_ti_size * dtype_tuple[1]
                count = (end_ti - begin_ti + 1) * each_ti_size
                shape = (1, end_ti - begin_ti + 1, shape[2])

            if file_path.endswith(DataManager.TYPE_LZ4):
                # lz4 ignore fillna NOW
                buffer = reader.read()
                if out is None:
                    buffer = self.__compressor.decode(buffer)
                    data = np.frombuffer(buffer)
                    data = np.reshape(data, shape)
                else:
                    try:
                        self.__compressor.decode(buffer, out)
                        data = out
                    except ValueError as e:
                        if "destination buffer too small" not in e.args[0]:
                            raise e
                        buffer = self.__compressor.decode(buffer)
                        data = np.frombuffer(buffer)
                        buffer_offset = int(offset / dtype_tuple[1])
                        out[:] = np.reshape(data[buffer_offset: buffer_offset + count], out.shape)
                        data = out
                        data = np.reshape(data, shape)

            else:
                if out is None:
                    if forward_fill_di_size + backward_fill_di_size > 0:
                        # fill nan
                        data = np.full(shape, np.nan, np.float64).ravel()
                        data[forward_fill_di_size * each_di_size: (forward_fill_di_size + load_di_count) * each_di_size] = np.fromfile(reader, dtype=dtype_tuple[0],
                                                                                                                                       count=count, offset=offset)
                    else:
                        data = np.fromfile(reader, dtype=dtype_tuple[0], count=count, offset=offset)
                    data.shape = shape
                else:
                    data = out
                    shape = data.shape
                    data.shape = (data.size,)
                    if forward_fill_di_size + backward_fill_di_size > 0:
                        # fill nan
                        data.fill(np.nan)
                        data[forward_fill_di_size * each_di_size: (forward_fill_di_size + load_di_count) * each_di_size] = np.fromfile(reader, dtype=dtype_tuple[0],
                                                                                                                                       count=count, offset=offset)
                    else:
                        data[:] = np.fromfile(reader, dtype=dtype_tuple[0], count=count, offset=offset)
                    data.shape = shape

            return data, data_header
