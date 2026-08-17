import os
import sys
import bisect
import yaml
import json
import importlib
import decimal
import shutil
import hashlib
import importlib.util
import pickle
import xmltodict
from types import ModuleType
from .dbg import *


def load_csv_file(file_path, token=',') -> list:
    lines = []
    with open(file_path, "r", encoding="utf-8") as reader:
        for line in reader.readlines()[1:]:
            words = [word.strip() for word in line.split(token)]
            lines.append(words)
    return lines


def ensure_dir(file_path):
    dir_path = os.path.dirname(file_path)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)


# def get_current_dir(frame=1):
#     return os.path.realpath(os.path.split(sys._getframe(frame).f_code.co_filename)[0])
#     use: os.path.abspath(os.path.dirname(__file__))
#

# def get_current_file(frame=1):
#     return os.path.realpath(os.path.split(sys._getframe(frame).f_code.co_filename)[1])
#     use: os.path.abspath(os.path.basename(__file__))

def realpath(path: str):
    return os.path.realpath(os.path.expanduser(path))


def equal_or_first_greater(lst, ele):
    return bisect.bisect_left(lst, ele)


def equal_or_first_less(lst, ele):
    return bisect.bisect_right(lst, ele) - 1


def first_greater(lst, ele):
    return bisect.bisect_right(lst, ele)


def first_less(lst, ele):
    return bisect.bisect_left(lst, ele) - 1


def load_yaml(config_path, macro=False, append_macro_dict=None):
    reader = open(config_path, "r", encoding="utf-8")
    data = reader.read()
    reader.close()

    config_dict = yaml.load(data, Loader=yaml.FullLoader)
    if macro:
        macro_dict = config_dict.get("macro", {})
        if append_macro_dict:
            macro_dict.update(append_macro_dict)
        for k, v in macro_dict.items():
            macro_key = "${%s}" % k
            macro_value = v
            data = data.replace(macro_key, macro_value)
        config_dict = yaml.load(data, Loader=yaml.FullLoader)
    return config_dict

def load_xml(config_path, append_macro_dict=None):
    append_macro_dict = append_macro_dict or dict()
    with open(config_path) as reader:
        data = reader.read()
        # root = ET.fromstring(data)
        # xml_dict = dictify(root)
        xml_dict = json.loads(json.dumps(xmltodict.parse(data)).replace("@", ""))["QSim"]
        macro_dict = {}
        if "Macros" in xml_dict:
            macro_dict.update(xml_dict["Macros"])
            xml_dict.pop("Macros")
        macro_dict.update(append_macro_dict)
        data = str(xml_dict)
        for k, v in macro_dict.items():
            data = data.replace("${%s}" % k, v)
        xml_dict = eval(data)
        # print(xml_dict)
        config_dict = {"global": {}, "module": {}, "alpha": {}}
        config_dict["global"]["begin_date"] = xml_dict["Universe"]["startdate"]
        config_dict["global"]["end_date"] = xml_dict["Universe"]["enddate"]
        for k, v in xml_dict["Constants"].items():
            if k == "niodatapath":
                config_dict["global"]["meta_dir"] = xml_dict["Constants"]["niodatapath"]
            elif k == "backdays":
                config_dict["global"]["back_days"] = int(xml_dict["Constants"]["backdays"])
            else:
                config_dict["global"][k] = v

        if "Caches" in xml_dict:
            if isinstance(xml_dict["Caches"]["Cache"], dict):
                cache_list = [xml_dict["Caches"]["Cache"]]
            else:
                cache_list = xml_dict["Caches"]["Cache"]
            config_dict["global"]["cache_list"] = []
            for cache_dict in cache_list:
                config_dict["global"]["cache_list"].append(cache_dict["path"])
            # print(config_dict["global"]["cache_list"])

        for module_dict in xml_dict["Modules"]["Module"]:
            if module_dict["handler"] == "AlphaHandler":
                config_dict["module"].setdefault("alpha", {})[module_dict["id"]] = module_dict["path"]
            elif module_dict["handler"] == "AlphaOpsHandler":
                config_dict["module"].setdefault("operation", {})[module_dict["id"]] = module_dict["path"]
            elif module_dict["handler"] == "StatsRegistry":
                config_dict["module"].setdefault("stats", {})[module_dict["id"]] = module_dict["path"]
            elif module_dict["handler"] == "PortfolioHandler":
                config_dict["module"].setdefault("portfolio", {})[module_dict["id"]] = module_dict["path"]

        portfolio_dict = xml_dict["Portfolio"]
        alpha_dict_list = portfolio_dict.get("Alpha", [])
        if isinstance(alpha_dict_list, dict):
            alpha_dict_list = [alpha_dict_list]
        alpha_dict_list.append(portfolio_dict)

        stats_dict = None
        if "Stats" in portfolio_dict:
            stats_dict = portfolio_dict["Stats"]

        alpha_id_set = set()
        for alpha_dict in alpha_dict_list:
            alpha_id = alpha_dict["id"]
            if alpha_id in alpha_id_set:
                abort("Alpha id replicated: %s", alpha_id)
            alpha_id_set.add(alpha_id)
            dic = config_dict["alpha"].setdefault(alpha_dict["id"], {})

            for k, v in alpha_dict.items():
                if k == "id":
                    continue
                if k == "moduleId":
                    dic["module_id"] = v
                    continue
                if k == "Operations":
                    if v is None:
                        continue
                    elif isinstance(v["Operation"], list):
                        for v2 in v["Operation"]:
                            op_list = dic.setdefault("operation", [])
                            v2["module_id"] = v2["moduleId"]
                            v2["id"] = alpha_id + "_op_" + str(len(op_list))
                            op_list.append(v2)
                    elif isinstance(v["Operation"], dict):
                        v2 = v["Operation"]
                        op_list = dic.setdefault("operation", [])
                        v2["module_id"] = v2["moduleId"]
                        v2["id"] = alpha_id + "_op_" + str(len(op_list))
                        op_list.append(v2)
                if k == "Stats":
                    stats_list = dic.setdefault("stats", [])
                    v["id"] = alpha_id + "_stats_" + str(len(stats_list))
                    v["module_id"] = v["moduleId"]
                    stats_list.append(v)
                dic[k] = v
            if "Stats" not in alpha_dict and stats_dict is not None:
                stats_list = dic.setdefault("stats", [])
                v = stats_dict.copy()
                v["id"] = alpha_id + "_stats_" + str(len(stats_list))
                v["module_id"] = v["moduleId"]
                stats_list.append(v)

        return config_dict


def get_module_dir_and_name(file_path):
    module_dir, module_name = os.path.split(file_path)
    module_name = os.path.splitext(module_name)[0]
    return module_dir, module_name


def file_sha256(file_path: str) -> str:
    digest = hashlib.sha256()
    with open(file_path, "rb") as reader:
        for block in iter(lambda: reader.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def external_module_name(file_path: str) -> str:
    path_hash = hashlib.sha256(file_path.encode("utf-8")).hexdigest()
    return "_xqsim_external_" + path_hash


def prepend_sys_path(path: str) -> str:
    """Place one trusted external-module root first on ``sys.path``."""

    path = realpath(path)
    if path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)
    return path


def dynamic_import(file_path: str, remove=True) -> ModuleType:
    file_path = realpath(file_path)
    if not os.path.isfile(file_path):
        raise FileNotFoundError(file_path)

    module_dir = os.path.dirname(file_path)
    module_name = external_module_name(file_path)
    loaded_module = sys.modules.get(module_name)
    if loaded_module is not None:
        return loaded_module

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot create module spec for %s" % file_path)

    module = importlib.util.module_from_spec(spec)
    module.__xqsim_source_path__ = file_path
    module.__xqsim_source_sha256__ = file_sha256(file_path)
    sys.modules[module_name] = module

    inserted_path = False
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
        inserted_path = True
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    finally:
        if remove and inserted_path:
            sys.path.remove(module_dir)
    log_info(
        "Loaded external module %s as %s sha256=%s",
        file_path,
        module_name,
        module.__xqsim_source_sha256__,
    )
    return module


def getattr_fromfile(file_path: str, name: str):
    return getattr(dynamic_import(file_path), name, None)


def pickle_dynamic_import(file_path, pickle_file_path):
    module_dir, module_name = get_module_dir_and_name(file_path)
    remove_flag = False
    if module_dir not in sys.path:
        remove_flag = True
        sys.path.append(module_dir)
    with open(pickle_file_path, "rb") as reader:
        obj = pickle.load(reader)
    if remove_flag:
        sys.path.pop()
    return obj


# def getattr_from_current_dir(file_name, name):
#     current_dir = get_current_dir(2)
#     file_path = os.path.join(current_dir, file_name)
#     return getattr_fromfile(file_path, name)


def round_right(number, i: int):
    return float(decimal.Decimal(str(number)).quantize(decimal.Decimal("1." + "0" * i), rounding=decimal.ROUND_HALF_UP))


def md5sum(src):
    with open(src, 'rb') as f:
        md5code = hashlib.md5(f.read()).hexdigest()
    return md5code


def copy_with_check(src, dst, retry=1):
    while True:
        ret = shutil.copy2(src, dst)
        if md5sum(src) == md5sum(dst):
            break
        else:
            if retry > 0:
                retry -= 1
                continue
            else:
                raise ValueError("Copy from %s to %s but md5 not same" % (src, dst))
    return ret


def copy_dir(source, target):
    if not os.path.exists(target):
        os.makedirs(target)
    if not os.path.isdir(target):
        raise Exception("target not dir: %s" % target)
    if not os.path.exists(source):
        raise Exception("source not found: %s" % source)
    if not os.path.isdir(source):
        raise Exception("source not dir: %s" % source)

    for a in os.walk(source):
        # create dir
        for d in a[1]:
            dir_path = os.path.join(a[0].replace(source, target), d)
            if not os.path.isdir(dir_path):
                os.makedirs(dir_path)
        # copy file
        for f in a[2]:
            dep_path = os.path.join(a[0], f)
            arr_path = os.path.join(a[0].replace(source, target), f)
            copy_with_check(dep_path, arr_path)
