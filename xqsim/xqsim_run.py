import os
import getopt
from xqsim.version import VERSION
from xqsim.dbg import *
from xqsim.simulator import Simulator
import xqsim.common_utils as common_utils

def builder_run(**kwargs):
    simulator = init_simulator(build=True, **kwargs)

    module = sys.modules['__main__']
    if kwargs.get("file_path", None) is None:
        file_path = common_utils.realpath(module.__file__)
        module_id = common_utils.get_module_dir_and_name(file_path)[1]
        kwargs["file_path"] = file_path
    else:
        file_path = kwargs["file_path"]
        module_id = kwargs.get("module_id", common_utils.get_module_dir_and_name(file_path)[1])
    simulator.add_provider(module_id, file_path, kwargs)

    simulator.run()


def init_simulator(**kwargs):
    simulator = Simulator()
    simulator.init_base_with_cmd(**kwargs)
    return simulator


def init_simulator_with_config_dict(config_dict):
    simulator = Simulator()
    simulator.init_with_config_dict(config_dict)
    return simulator


def init_dr(**kwargs):
    # init dr disable data limit default
    if "data_limit" not in kwargs:
        kwargs["data_limit"] = 0
    simulator = init_simulator(build=True, **kwargs)
    return simulator.dr


def show_menu():
    print("Usage: xxxx.py -c config.config")


def get_config_path():
    opts, args = getopt.getopt(sys.argv[1:], "-v-c:", ["version", "config="])

    config_path = None

    for o, a in opts:
        if o in ("-v", "--version"):
            print("version is", VERSION)
            sys.exit()
        if o in ("-c", "--config"):
            config_path = a

    if config_path is None:
        show_menu()
        exit(1)
    log_info("Current work dir is %s", os.getcwd())
    config_path = common_utils.realpath(config_path)
    log_info("Config path is %s", config_path)
    return config_path


def main():
    config_path = get_config_path()

    simulator = Simulator()
    simulator.init_with_config_path(config_path)
    simulator.run()


if __name__ == '__main__':
    main()
