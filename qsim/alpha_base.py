from qsim.module_base import *
from qsim.qsim_run import init_simulator, init_dr, get_config_path, Simulator


def simulator_run(**kwargs):
    if "cls" not in kwargs:
        module = sys.modules['__main__']
        file_path = common_utils.realpath(module.__file__)
        module_id = common_utils.get_module_dir_and_name(file_path)[1]
        simulator = init_simulator(**kwargs)
        simulator.add_single_alpha(module_id, file_path, kwargs)
        simulator.run()
    else:
        log_warn("Find cls in config, use interactive shell?")
        kwargs["file_path"] = "."
        kwargs["id"] = "unknown_id"
        simulator = init_simulator(**kwargs)
        simulator.add_alpha_module(kwargs["cls"], kwargs)
        simulator.run()
