from xqsim.base.module_base import *
from xqsim.base.alpha_base import AlphaBase
from xqsim.base.operation_base import OperationBase
from xqsim.base.stats_base import StatsBase
from xqsim.data.data_manager import DataManager
from collections.abc import Callable
import pandas as pd

MODULE_TYPE = {"stats"}

def load_cls(file_path: str, cls_name: str) -> Callable[..., ModuleBase]:
    cls = common_utils.getattr_fromfile(file_path, cls_name)
    if cls is None:
        cls = common_utils.getattr_fromfile(file_path, "create")
        if cls is None:
            abort("No class %s or create func in file %s", cls_name, file_path)
    return cls


class AlphaTask(object):
    def __init__(self, dr: DataRepository, local_config: dict):
        self.__dr = dr
        self.__meta = dr.meta
        self.__local_config = local_config

        self.__alpha: AlphaBase

        self.op_list: list[OperationBase] = []
        self.stats_list: list[StatsBase] = []

        self._save_alpha_dict = {}

        self.__shape = (1, self.__meta.interval_ti_size, self.__meta.ii_size) if self.__meta.interval != "day" else (1, self.__meta.ii_size)
        self.__id = None
        self.__save_init = False

        self.__save_csv_list = []

        self.path_list: set[str] = set()

    def set_meta(self, meta: Meta):
        self.__meta = meta

    def add_alpha(self, alpha_id: str, file_path: str, temp_config: dict | None = None):
        config = self.__local_config.copy()
        if temp_config:
            config.update(temp_config)
        for k in MODULE_TYPE:
            if k in config:
                config.pop(k)
        config["id"] = alpha_id
        config["file_path"] = os.path.abspath(file_path)

        cls: Callable = load_cls(config["file_path"], "Alpha")
        self.add_alpha_cls(cls, config)

        log_info("AlphaManager add alpha: %s, file_path: %s", config["id"], config["file_path"])
        self.path_list.add(config["file_path"])

    def add_alpha_cls(self, cls: Callable[..., AlphaBase], temp_config: dict | None = None):
        config = self.__local_config.copy()
        if temp_config:
            config.update(temp_config)

        obj = cls(self.__dr, config)
        # if self.__meta.check_load_di is not None:
        #     if obj.id not in self.__meta.check_file_list:
        #         abort("cannot find %s in checkpoint files", obj.id)
        #     obj = common_utils.pickle_dynamic_import(config["file_path"], os.path.join(self.__meta.checkpoint_dir, obj.id))
        #     obj.dr = self.__dr

        self.__alpha = obj
        self.__id = self.__alpha.id

    def add_module(self, temp_config: dict, cls_type: str, cls_list: list):
        config = self.__local_config.copy()
        if temp_config:
            config.update(temp_config)
        config["file_path"] = os.path.abspath(config["file_path"])
        cls = load_cls(config["file_path"], cls_type)

        config["alpha_id"] = self.__alpha.id
        obj: ModuleBase = cls(self.__dr, config)
        # if self.__meta.check_load_di is not None:
        #     if obj.id not in self.__meta.check_file_list:
        #         abort("cannot find %s in checkpoint files", obj.id)
        #     obj = common_utils.pickle_dynamic_import(config["file_path"], os.path.join(self.__meta.checkpoint_dir, obj.id))
        #     obj.dr = self.__dr

        obj.parent_module = self.__alpha
        # self.__alpha.children_module.append(obj)
        cls_list.append(obj)
        log_info("AlphaManager Alpha %s add %s: %s", self.__alpha.id, cls_type, config["id"])
        self.path_list.add(config["file_path"])

    def add_op(self, temp_config: dict):
        self.add_module(temp_config, "Operation", self.op_list)

    def add_stats(self, temp_config: dict):
        self.add_module(temp_config, "Stats", self.stats_list)

    def add_save_alpha(self, ti):
        if not self.__alpha.save_flag:
            return
        if not self.__save_init:
            self.__save_init = True
            self._save_alpha_dict[self.__id] = np.full(self.__shape, nan, np.float64)

            if self.__alpha.save_flag:
                if self.__alpha.overwrite == "no":
                    for name, save_alpha in self._save_alpha_dict.items():
                        abort_if(self.__dr.data_exist(self.__alpha.output_dir, name, save_alpha, DataManager.TYPE_FACTOR), "alpha file exist: %s", name)
                elif self.__alpha.overwrite == "append":
                    pass
                elif self.__alpha.overwrite == "force":
                    for name, save_alpha in self._save_alpha_dict.items():
                        self.__dr.remove_data(self.__alpha.output_dir, name, save_alpha, DataManager.TYPE_FACTOR)
                elif self.__alpha.overwrite == "auto":
                    pass
        save_alpha = self._save_alpha_dict[self.__id]
        if self.__meta.interval == "day":
            save_alpha[0] = self.__alpha.alpha.copy()
        else:
            save_alpha[0][ti] = self.__alpha.alpha

    def calculate_stats(self, di: int):
        if len(self.stats_list) == 0:
            return
        value = None
        for stats in self.stats_list:
            value = stats.calculate_di(di, 0, alpha=self.__alpha.alpha)
        return value

    def run_before(self, di: int):
        self.__alpha.reset_alpha()
        self.__alpha.before_generate(di)

    def run(self, di: int):
        univbase.instruments = self.__meta.instrument_index[di]
        self.__save_csv_list.append([di - self.__alpha.delay, None, None, None])

        self.__alpha.generate(di)
        if self.__alpha.save_csv_dir:
            self.__save_csv_list[-1][1] = self.__alpha.alpha.copy()

        for op_obj in self.op_list:
            op_obj.apply(di, self.__alpha.alpha)

        if self.__alpha.save_csv_dir:
            self.__save_csv_list[-1][2] = self.__alpha.alpha.copy()

        self.add_save_alpha(0)
        value = self.calculate_stats(di)
        if self.__alpha.save_csv_dir:
            self.__save_csv_list[-1][3] = value

    def run_portfolio(self, di: int, alpha_list):
        univbase.instruments = self.__meta.instrument_index[di]
        self.__save_csv_list.append([di - self.__alpha.delay, None, None, None])

        self.__alpha.generate_portfolio(di, alpha_list)
        if self.__alpha.save_csv_dir:
            self.__save_csv_list[-1][1] = self.__alpha.alpha.copy()

        for op_obj in self.op_list:
            op_obj.apply(di, self.__alpha.alpha)

        if self.__alpha.save_csv_dir:
            self.__save_csv_list[-1][2] = self.__alpha.alpha.copy()

        self.add_save_alpha(0)
        value = self.calculate_stats(di)
        if self.__alpha.save_csv_dir:
            self.__save_csv_list[-1][3] = value

    def run_after(self, di: int):
        self.__alpha.after_generate(di)

    def save(self, di: int):
        # if di == self.__meta.check_save_di:
        #     # log_info("check point save")
        #     f = open(os.path.join(self.__meta.checkpoint_dir, self.__alpha.id), "wb")
        #     pickle.dump(self.__alpha, f, 1)
        #     f.close()
        #     for obj in self.op_list:
        #         f = open(os.path.join(self.__meta.checkpoint_dir, obj.id), "wb")
        #         pickle.dump(obj, f, 1)
        #         f.close()
        #     for obj in self.stats_list:
        #         f = open(os.path.join(self.__meta.checkpoint_dir, obj.id), "wb")
        #         pickle.dump(obj, f, 1)
        #         f.close()

        if not self.__alpha.save_flag:
            return
        trading_day = self.__meta.total_date_index[di]
        for name, save_alpha in self._save_alpha_dict.items():
            self.__dr.append_data(self.__alpha.output_dir, name, save_alpha, trading_day, trading_day, DataManager.TYPE_FACTOR,
                                  part_overwrite=self.__alpha.overwrite in {"auto", "force"})

    def save_stats(self):
        for stats in self.stats_list:
            stats.save_pnl()
        self.save_csv()

    def save_csv(self):
        save_csv_dir = self.__meta.get_para_default("dynamic_save_csv", self.__alpha.save_csv_dir)
        if not save_csv_dir or save_csv_dir == "":
            return
        log_info("%s save csv start", self.__alpha.id)
        for data in self.__save_csv_list:
            di = data[0]
            # print(di, self.__meta.begin_di, self.__meta.end_di)
            if not self.__alpha.save_csv_total and (di < self.__meta.begin_di - self.__alpha.delay or di > self.__meta.end_di):
                continue
            date = self.__meta.date_index[di]
            date = str(date)
            file_path = os.path.join(save_csv_dir, self.__alpha.id, date[0:4], date[4:6], "%s.%s" % (self.__alpha.id, date))
            common_utils.ensure_dir(file_path)
            index = self.__meta.instrument_index[di]
            df = pd.DataFrame(index=index)
            df["code"] = index
            df["v1"] = data[1]
            df["v2"] = data[2]
            df["v3"] = data[3]
            # df.drop(axis=0, index=df.loc[df['code'] == ''].index, inplace=True)
            # print(df)
            df.to_csv(file_path, sep="|", na_rep="nan", header=False, index=False)
            # log_info("%s save csv finish: %s", self.__alpha.id, file_path)

    def alpha_module(self):
        return self.__alpha


class AlphaManager(object):
    def __init__(self, dr: DataRepository):
        self.__dr: DataRepository = dr
        self.__meta: Meta = dr.meta
        self.__alpha_task_list: list[AlphaTask] = []
        self.__portfolio_task: AlphaTask | None = None
        self.__all_task: list[AlphaTask] = []

    @property
    def dr(self):
        return self.__dr

    def set_meta(self, meta: Meta):
        self.__meta = meta
        for task in self.__all_task:
            task.set_meta(meta)

    def create_alpha_task(self, config: dict | None = None) -> AlphaTask:
        local_config = self.__meta.global_cfg.copy()
        if config is not None:
            local_config.update(config)

        alpha_task = AlphaTask(self.__dr, local_config)
        self.__alpha_task_list.append(alpha_task)
        self.__all_task.append(alpha_task)
        return alpha_task

    def create_portfolio_task(self, config: dict | None = None) -> AlphaTask:
        local_config = self.__meta.global_cfg.copy()
        if config is not None:
            local_config.update(config)

        alpha_task = AlphaTask(self.__dr, local_config)
        self.__portfolio_task = alpha_task
        self.__all_task.append(alpha_task)
        return alpha_task

    def run_before_di(self, di: int):
        for alpha_task in self.__all_task:
            alpha_task.run_before(di)

    def run(self, di: int):
        print_flag = False
        alpha_list = []
        for alpha_task in self.__alpha_task_list:
            # print stats
            if not print_flag and len(alpha_task.stats_list) > 0 and simcfg.get(alpha_task.stats_list[0].cfg, "print", True):
                print_flag = True
                print()
                print("%8s %20s %11s %10s  x %10s %10s %10s %10s %6s  x %5s" %
                      ("", "", "PNL", "LONG", "SHORT", "RET", "HLDVAL", "TRDVAL", "LC", "SC"))
            alpha_task.run(di)
            alpha_list.append(alpha_task.alpha_module().alpha)
        if self.__portfolio_task is not None:
            self.__portfolio_task.run_portfolio(di, alpha_list)

    def run_after_di(self, di: int):
        for alpha_task in self.__all_task:
            alpha_task.run_after(di)

    def save(self, di: int):
        for alpha_task in self.__all_task:
            alpha_task.save(di)

    def save_stats(self):
        for alpha_task in self.__all_task:
            alpha_task.save_stats()

    def clear(self):
        self.__all_task.clear()

    def module_path_list(self):
        path_list = set()
        for alpha_task in self.__all_task:
            path_list |= alpha_task.path_list
        return path_list
