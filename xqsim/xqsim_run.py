import os
import argparse
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


MODULE_EXPORTS = {
    "alpha": "Alpha",
    "operation": "Operation",
    "stats": "Stats",
    "provider": "Provider",
}


def _check_external_modules(module_specs):
    for module_type, file_path in module_specs:
        export_name = MODULE_EXPORTS.get(module_type.lower())
        if export_name is None:
            raise ValueError(
                "unsupported module type %r; expected one of %s"
                % (module_type, ", ".join(sorted(MODULE_EXPORTS)))
            )
        file_path = common_utils.realpath(file_path)
        module = common_utils.dynamic_import(file_path)
        exported = getattr(module, export_name, None)
        if exported is None:
            exported = getattr(module, "create", None)
        if exported is None:
            raise AttributeError(
                "%s must export %s or create" % (file_path, export_name)
            )
        print(
            "checked %s module %s sha256=%s"
            % (module_type.lower(), file_path, module.__xqsim_source_sha256__)
        )


def get_config_path():
    parser = argparse.ArgumentParser(prog="xqsim")
    parser.add_argument("-v", "--version", action="store_true")
    parser.add_argument("-c", "--config")
    parser.add_argument(
        "--check-module",
        nargs=2,
        action="append",
        metavar=("TYPE", "FILE"),
        help="validate an external alpha/operation/stats/provider module",
    )
    args = parser.parse_args()

    if args.version:
        print("version is", VERSION)
        sys.exit()
    if args.check_module:
        _check_external_modules(args.check_module)
        sys.exit()
    if args.config is None:
        parser.error("-c/--config is required")

    log_info("Current work dir is %s", os.getcwd())
    config_path = common_utils.realpath(args.config)
    log_info("Config path is %s", config_path)
    return config_path


def main():
    config_path = get_config_path()

    simulator = Simulator()
    simulator.init_with_config_path(config_path)
    simulator.run()


if __name__ == '__main__':
    main()
