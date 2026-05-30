import os
import sys
import datetime

import pandas as pd
import numpy as np

from prefect import flow, task, get_run_logger

from qsim.simulator import load_xml
from qsim.api import init_dr, DataRepository, empty_alpha
from qsim.qsim_run import init_simulator_with_config_dict
from qsim import common_utils
from qsim_data_tools.prefect_task import load_config
from qsim_data_tools.update_tools import Tools
from qsim_data_tools.utils import get_debug_and_ip


@task
def parse_config(config_dict):
    logger = get_run_logger()
    parsed_config_dict = {}
    for task_name, task_config_path in config_dict.get("build", {}).items():
        xml_config_dict = load_xml(task_config_path["config"])
        xml_config_dict["global"]["begin_date"] = task_config_path["begin_date"]
        xml_config_dict["global"]["end_date"] = task_config_path["end_date"]
        simulator = init_simulator_with_config_dict(xml_config_dict)
        xml_config_dict["global"]["begin_date"] = simulator.meta.begin_trading_day
        xml_config_dict["global"]["end_date"] = simulator.meta.end_trading_day
        xml_config_dict["global"]["dynamic_save_csv"] = (
            task_config_path["save_csv"]
            + "_" + str(simulator.meta.begin_trading_day)
            + "_" + str(simulator.meta.end_trading_day)
            + "_" + datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        )
        xml_config_dict["global"]["output_cache_dir"] = os.path.join(
            os.path.abspath(task_config_path["output_cache_dir"]),
            "CC_update_%s_%s" % (simulator.meta.begin_trading_day, simulator.meta.end_trading_day),
        )
        xml_config_dict["global"]["dst_cache_dir"] = task_config_path["dst_cache_dir"]
        xml_config_dict["global"]["chdir"] = task_config_path.get("chdir", None)
        logger.info("Task build %s with %s ready", task_name, task_config_path["config"])
        parsed_config_dict[task_name] = xml_config_dict
    return parsed_config_dict


@task
def build(parsed_config_dict, dummy_flag, check_flag, merge_flag):
    logger = get_run_logger()
    for task_name, config_dict in parsed_config_dict.items():
        logger.info("Task build %s start", task_name)
        simulator = init_simulator_with_config_dict(config_dict)
        simulator.run()
        logger.info("Task build %s finish" % task_name)
        csv_to_cache(config_dict, dummy_flag)

        begin_date = config_dict["global"]["begin_date"]
        end_date = config_dict["global"]["end_date"]
        output_cache_dir = config_dict["global"]["output_cache_dir"]

        if check_flag:
            logger.info("Check start: %s", output_cache_dir)
            if not Tools(simulator.meta).check_cc(output_cache_dir, begin_date, end_date):
                raise Exception()
            logger.info("Check finish")

        if merge_flag:
            dst_cache_dir = config_dict["global"]["dst_cache_dir"]
            if type(dst_cache_dir) is list:
                dst_cache_dir_list = dst_cache_dir
            else:
                dst_cache_dir_list = [dst_cache_dir]
            output_cache_dir = config_dict["global"]["output_cache_dir"]

            for dst_cache_dir in dst_cache_dir_list:
                logger.info("Merge Start: %s -> %s", output_cache_dir, dst_cache_dir)
                if not Tools(simulator.meta).merge_cc(dst_cache_dir, output_cache_dir, 0):
                    raise Exception()
            logger.info("Merge finish")


def csv_to_cache(config_dict, dummy_flag):
    output_cache_dir = config_dict["global"]["output_cache_dir"]
    if os.path.exists(output_cache_dir):
        os.rename(output_cache_dir, output_cache_dir + "_" + datetime.datetime.now().strftime('%Y%m%d%H%M%S'))

    dr: DataRepository = init_dr(
        meta_dir=config_dict["global"]["meta_dir"],
        begin_date=config_dict["global"]["begin_date"],
        end_date=config_dict["global"]["end_date"],
        output_cache_dir=output_cache_dir,
    )
    csv_path = config_dict["global"]["dynamic_save_csv"]
    print(csv_path)
    for alpha in os.listdir(csv_path):
        path_list = []
        alpha_path = os.path.join(csv_path, alpha)
        alpha_name = os.path.split(os.path.abspath(alpha_path))[1]
        for year in os.listdir(alpha_path):
            for month in os.listdir(os.path.join(alpha_path, year)):
                for file_name in os.listdir(os.path.join(alpha_path, year, month)):
                    path_list.append(os.path.join(alpha_path, year, month, file_name))
        path_list.sort()
        numpy_list_dict = {}

        for path in path_list:
            df = pd.read_csv(path, sep="|", header=None)
            for index, row in df.items():
                if row.dtype == np.object_:
                    continue
                numpy_list_dict.setdefault(index, []).append(row)

        begin_trading_day = int(os.path.splitext(path_list[0])[1][1:])
        end_trading_day = int(os.path.splitext(path_list[-1])[1][1:])

        for name, result in numpy_list_dict.items():
            array = np.array(result)
            if dummy_flag:
                array = np.row_stack([array[1:], empty_alpha(dr.meta.ii_size)])
                end_trading_day = dr.meta.end_trading_day
                begin_trading_day = dr.meta.date_index[dr.meta.end_di - len(path_list) + 1]
                print(len(path_list))
                print(path_list)
                print(begin_trading_day, end_trading_day)
            dr.write_data(
                alpha_name,
                alpha_name + "_" + str(name),
                array,
                begin_trading_day=begin_trading_day,
                end_trading_day=end_trading_day,
                overwrite=True,
            )


@flow(name="Build Csv")
def build_csv(
    config_path: str = None,
    check: bool = True,
    merge: bool = True,
    build_flag: bool = True,
    dummy: bool = True,
):
    if config_path is None:
        config_path = os.path.join(
            os.path.abspath(os.path.dirname(__file__)),
            "config/update_csv.yml",
        )

    config_dict = load_config(config_path)

    if build_flag:
        parsed_config_dict = parse_config(config_dict)
        build(parsed_config_dict, dummy, check, merge)


def main():
    debug, ipaddr = get_debug_and_ip()
    if debug:
        build_csv(config_path="/home/prod/prod/build_debug.yml")
    else:
        build_csv.serve(
            name="default",
            cron=["10 7,16,19 * * 1-5", "30 17 * * 1-5"],
            timezone="Asia/Shanghai",
        )


if __name__ == "__main__":
    main()
