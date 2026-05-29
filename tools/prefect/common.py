from qsim_data_tools.prefect_task import *


@task(log_stdout=True)
def run_all_provider(config_dict, mysql_config):
    logger = prefect.context.get("logger")
    # rename cc_update if exist
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


@task(log_stdout=True)
def copy_meta(config_dict):
    logger = prefect.context.get("logger")
    src_dir = os.path.join(config_dict["global"]["meta_dir"], "meta")
    dst_dir = os.path.join(config_dict["global"]["output_cache_dir"], "meta")
    if os.path.exists(dst_dir):
        shutil.rmtree(dst_dir)
    shutil.copytree(src_dir, dst_dir)
    logger.info("Copy meta: from %s to %s", src_dir, dst_dir)


@task(log_stdout=True)
def ut_run(config_dict):
    logger = prefect.context.get("logger")
    command = config_dict["ut"]["command"]
    logger.info("ut run: %s", command)
    run_shell(command, check_stderr=False, abort=False)


@task(log_stdout=True)
def check_ut(today_date, config_dict):
    logger = prefect.context.get("logger")
    result_file_path = config_dict["ut"]["result_path"]
    with open(result_file_path, "r") as reader:
        result_dict = eval(reader.read())
        ut_date = result_dict["start_date"]
    pass_flag = True
    if result_dict["errors"] > 0:
        logger.error("Check ut error: errors: %s", result_dict["errors"])
        pass_flag = False
    failed_count = result_dict["failures"]
    if ut_date != today_date:  # not same day
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


def main():
    debug, ipaddr = get_debug_and_ip()

    client_flows = []
    ip_list = common_utils.load_yaml(os.path.join(os.path.abspath(os.path.dirname(__file__)), "config/update_production.yml"), macro=True)["client"]
    for ip in ip_list:
        client_flows.append(StartFlowRun(flow_name="%s Build Csv" % ip, project_name="Qsim Data", wait=True, timeout=1080))

    with Flow(ipaddr + " Build Common",
              UnionSchedule([
                  CronSchedule("10 7,16,19 * * 1-5", start_date=datetime.datetime.now(tz=timezone("Asia/Shanghai"))),
                  CronSchedule("30 17 * * 1-5", start_date=datetime.datetime.now(tz=timezone("Asia/Shanghai"))),
              ]),
              on_failure=None) as flow:
        begin_date = Parameter("begin_date", default="TODAY-1")
        end_date = Parameter("end_date", default="TODAY")
        config_path = Parameter("config_path", default=os.path.join(os.path.abspath(os.path.dirname(__file__)), "config/update_production.yml"))
        check_flag = Parameter("check", True)
        merge_flag = Parameter("merge", True)
        build_flag = Parameter("build", True)
        ut_flag = Parameter("ut", True)
        force_flag = Parameter("force", 0)
        mysql_config = Parameter("mysql_config", "mysql.json")

        config_dict = load_config(config_path)

        upstream_task = update_meta(config_dict)

        config_dict, meta = init_simulator_and_config(config_dict, begin_date, end_date, None, upstream_tasks=[upstream_task])

        with case(build_flag, True):
            upstream_task = run_all_provider(config_dict, mysql_config)
        upstream_task = merge(upstream_task, empty())

        upstream_task = copy_meta(config_dict, upstream_tasks=[upstream_task])

        with case(check_flag, True):
            upstream_task = run_check(config_dict, meta, upstream_tasks=[upstream_task])
        upstream_task = merge(upstream_task, empty())

        with case(merge_flag, True):
            upstream_task = run_merge(config_dict, meta, force_flag, upstream_tasks=[upstream_task])
        upstream_task = merge(upstream_task, empty())

        with case(ut_flag, True):
            upstream_task = ut_run(config_dict, upstream_tasks=[upstream_task])
            today_date = get_date_with_meta("TODAY", meta, upstream_tasks=[upstream_task])
            upstream_task = check_ut(today_date, config_dict)
        upstream_task = merge(upstream_task, empty())

        client_tasks = []
        for client_flow in client_flows:
            client_tasks.append(client_flow(parameters={"begin_date": begin_date,
                                                        "end_date": end_date},
                                            upstream_tasks=[upstream_task]))
        upstream_task = wait_tasks_finish(client_tasks)

    if debug:
        flow.visualize(flow.run(parameters={"config_path": "./config/update_debug.yml"}))
    else:
        flow.register(project_name="Qsim Data")


if __name__ == '__main__':
    main()
