import shutil
import datetime
import os
import time

from prefect import task, flow, get_run_logger

from qsim import common_utils
from qsim.qsim_run import init_simulator, init_simulator_with_config_dict
from qsim_data_tools.update_tools import Tools
from qsim_data_tools.ssh import Host
from qsim_data_tools.utils import *


@task
def load_config(config_path):
    return common_utils.load_yaml(config_path, macro=True)


@task
def update_meta(config_dict):
    logger = get_run_logger()
    meta_updater_path = config_dict.get("meta_updater", None)
    if meta_updater_path is None:
        logger.warning("Update meta ignore")
        return
    meta_updater_run_func = common_utils.getattr_fromfile(meta_updater_path, "run")
    meta_dir = config_dict["global"]["meta_dir"]
    logger.info("Update meta dir %s", meta_dir)
    meta_updater_run_func(meta_dir)


@task
def init_simulator_and_config(config_dict, begin_date, end_date, output_cache_dir):
    global_config_dict = config_dict["global"]
    if output_cache_dir is None:
        tmp_output_cache_dir = global_config_dict["output_cache_dir"]
    else:
        tmp_output_cache_dir = output_cache_dir

    global_config_dict["begin_date"] = begin_date
    global_config_dict["end_date"] = end_date

    global_config_dict["output_cache_dir"] = os.path.join(
        os.path.abspath(tmp_output_cache_dir),
        "CC_update_%s_%s" % (begin_date, end_date),
    )
    simulator = init_simulator(**global_config_dict)

    global_config_dict["begin_date"] = simulator.meta.begin_trading_day
    global_config_dict["end_date"] = simulator.meta.end_trading_day
    global_config_dict["output_cache_dir"] = os.path.join(
        os.path.abspath(tmp_output_cache_dir),
        "CC_update_%s_%s" % (global_config_dict["begin_date"], global_config_dict["end_date"]),
    )

    logger = get_run_logger()
    logger.info("=== Init simulator finish, global config is %s", config_dict["global"])

    return config_dict, simulator.meta


@task
def run_check(config_dict, meta):
    logger = get_run_logger()

    begin_date = config_dict["global"]["begin_date"]
    end_date = config_dict["global"]["end_date"]
    output_cache_dir = config_dict["global"]["output_cache_dir"]

    logger.info("Check start: %s", output_cache_dir)
    if not Tools(meta).check_cc(output_cache_dir, begin_date, end_date):
        raise Exception()
    logger.info("Check finish")


@task
def run_merge(config_dict, meta, force):
    logger = get_run_logger()
    dst_cache_dir = config_dict["global"]["dst_cache_dir"]
    if type(dst_cache_dir) is list:
        dst_cache_dir_list = dst_cache_dir
    else:
        dst_cache_dir_list = [dst_cache_dir]
    output_cache_dir = config_dict["global"]["output_cache_dir"]

    for dst_cache_dir in dst_cache_dir_list:
        logger.info("Merge Start: %s -> %s", output_cache_dir, dst_cache_dir)
        if not Tools(meta).merge_cc(dst_cache_dir, output_cache_dir, force):
            raise Exception()
    logger.info("Merge finish")


@task
def download_cc_update(config_dict):
    logger = get_run_logger()
    host = Host(
        "data server",
        config_dict["remote"]["ip"],
        config_dict["remote"]["port"],
        config_dict["remote"]["username"],
        config_dict["remote"]["password"],
    )

    remote_dir = (
        config_dict["remote"]["cc_update_dir"]
        + "/"
        + "CC_update_%s_%s" % (config_dict["global"]["begin_date"], config_dict["global"]["end_date"])
    )
    logger.info("Remote dir is %s", remote_dir)

    local_dir = config_dict["global"]["output_cache_dir"]
    logger.info("Local dir is %s", local_dir)

    if os.path.exists(local_dir):
        logger.info("Local dir exist, remove !!!")
        shutil.rmtree(local_dir)

    host.ssh.get_dir(remote_dir, local_dir)
    logger.info("Download finish")


@task
def run_shell_task(command, check_stderr=True):
    return run_shell(command, check_stderr)


@task
def get_date(date, config_dict):
    logger = get_run_logger()
    new_config_dict = {"meta_dir": config_dict["meta_dir"], "begin_date": date, "end_date": date}
    meta = init_simulator(**new_config_dict).meta
    final_date = meta.begin_trading_day
    logger.info("get date, input %s, output %s", date, final_date)
    return final_date


@task
def get_date_with_meta(date, meta):
    logger = get_run_logger()
    new_config_dict = {"meta_dir": meta.meta_dir, "begin_date": date, "end_date": date}
    meta = init_simulator(**new_config_dict).meta
    final_date = meta.begin_trading_day
    logger.info("get date, input %s, output %s", date, final_date)
    return final_date


@task
def get_date_list(begin_date, end_date, config_dict):
    logger = get_run_logger()
    new_config_dict = {"meta_dir": config_dict["meta_dir"], "begin_date": begin_date, "end_date": end_date}
    meta = init_simulator(**new_config_dict).meta
    final_date_list = [meta.date_index[di] for di in meta.di_list]
    logger.info("get date, input %s---%s, output %s", begin_date, end_date, final_date_list)
    return final_date_list
