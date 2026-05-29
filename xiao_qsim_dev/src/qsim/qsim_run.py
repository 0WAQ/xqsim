import getopt
from qsim.version import VERSION
from qsim.dbg import *
from qsim.simulator import Simulator
import qsim.common_utils as common_utils


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
    simulator.init_with_config(config_path)
    simulator.run()


if __name__ == '__main__':
    main()
