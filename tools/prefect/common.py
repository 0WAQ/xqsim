import os
import sys
import shutil
import datetime

from prefect import flow, task, get_run_logger
from prefect.deployments import run_deployment

from qsim import common_utils
from qsim.qsim_run import init_simulator, init_simulator_with_config_dict
from qsim_data_tools.prefect_task import (
    load_config,
    update_meta,
    init_simulator_and_config,
    run_check,
    run_merge,
    get_date_with_meta,
)
from qsim_data_tools.update_tools import Tools
from qsim_data_tools.utils import run_shell, get_debug_and_ip


@task
def run_all_provider(config_dict, mysql_config):
    logger = get_run_logger()
    output_cache_dir = config_dict["global"]["output_cache_dir"]
    if os.path.exists(output_cache_dir):
        os.rename(output_cache_dir, output_cache_dir + "_" + datetime.datetime.now().strftime('%Y%m%d%H%M%S'))

    logger.info("=== Run all provider task start")
    for task_name, provider_config_path in config_dict.get("build", {}).items():
        provider_config_dicts = common_utils.load_yaml(provider_config_path, macro=True).get("provider", {})
        provider_config_dicts.setdefault("local", {})["mysql_config"] = mysql_config
        total_config = {"global": config_dict["global"], "provider": provider_config_dicts}
        logger.info("Task build %s with %s start, total config %s", task_name, provider_config_path, total_config)
        simulator = init_simulator_with_config_dict(total_config)
        simulator.run()
        logger.info("Task build %s finish" % task_name)
    logger.info("=== Run all provider task finish")


@task
def copy_meta(config_dict):
    logger = get_run_logger()
    src_dir = os.path.join(config_dict["global"]["meta_dir"], "meta")
    dst_dir = os.path.join(config_dict["global"]["output_cache_dir"], "meta")
    if os.path.exists(dst_dir):
        shutil.rmtree(dst_dir)
    shutil.copytree(src_dir, dst_dir)
    logger.info("Copy meta: from %s to %s", src_dir, dst_dir)


@task
def ut_run(config_dict):
    logger = get_run_logger()
    command = config_dict["ut"]["command"]
    logger.info("ut run: %s", command)
    run_shell(command, check_stderr=False, abort=False)


@task
def check_ut(today_date, config_dict):
    logger = get_run_logger()
    result_file_path = config_dict["ut"]["result_path"]
    with open(result_file_path, "r") as reader:
        result_dict = eval(reader.read())
        ut_date = result_dict["start_date"]
    pass_flag = True
    if result_dict["errors"] > 0:
        logger.error("Check ut error: errors: %s", result_dict["errors"])
        pass_flag = False
    failed_count = result_dict["failures"]
    if ut_date != today_date:
        current_hour = datetime.datetime.now().hour
        if (current_hour < 17 and failed_count > 7) or (current_hour >= 17 and failed_count > 1):
            logger.error("Check ut error: failures: %s", failed_count)
            pass_flag = False
    else:
        if failed_count > 0:
            logger.error("Check ut error: failures: %s", failed_count)
            pass_flag = False
    if not pass_flag:
        raise Exception("Check ut failed")
    else:
        logger.info("Check ut ok")


@flow(name="Build Common")
def build_common(
    begin_date: str = "TODAY-1",
    end_date: str = "TODAY",
    config_path: str = None,
    check: bool = True,
    merge: bool = True,
    build: bool = True,
    ut: bool = True,
    force: int = 0,
    mysql_config: str = "mysql.json",
):
    if config_path is None:
        config_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), "config/update_production.yml")

    config_dict = load_config(config_path)
    update_meta(config_dict)
    config_dict, meta = init_simulator_and_config(config_dict, begin_date, end_date, None)

    if build:
        run_all_provider(config_dict, mysql_config)

    copy_meta(config_dict)

    if check:
        run_check(config_dict, meta)

    if merge:
        run_merge(config_dict, meta, force)

    if ut:
        ut_run(config_dict)
        today_date = get_date_with_meta("TODAY", meta)
        check_ut(today_date, config_dict)

    ip_list = common_utils.load_yaml(
        os.path.join(os.path.abspath(os.path.dirname(__file__)), "config/update_production.yml"),
        macro=True,
    ).get("client", [])
    for ip in ip_list:
        run_deployment(
            name=f"{ip}-build-csv/default",
            parameters={"begin_date": begin_date, "end_date": end_date},
            timeout=1080,
        )


def main():
    debug, ipaddr = get_debug_and_ip()
    if debug:
        build_common(config_path="./config/update_debug.yml")
    else:
        build_common.serve(
            name="default",
            cron=["10 7,16,19 * * 1-5", "30 17 * * 1-5"],
            timezone="Asia/Shanghai",
        )


if __name__ == "__main__":
    main()
