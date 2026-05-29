import os
import sys
import bisect
import yaml
import importlib
import decimal
import shutil
import hashlib
import pickle


def load_csv_file(file_path, token=',') -> []:
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


def get_module_dir_and_name(file_path):
    module_dir, module_name = os.path.split(file_path)
    module_name = os.path.splitext(module_name)[0]
    return module_dir, module_name


def dynamic_import(file_path, remove=True):
    module_dir, module_name = get_module_dir_and_name(file_path)
    remove_flag = False
    if module_dir not in sys.path:
        remove_flag = True
        sys.path.append(module_dir)
    module = importlib.import_module(module_name)
    if remove and remove_flag:
        sys.path.pop()
    return module


def getattr_fromfile(file_path, name):
    try:
        return getattr(dynamic_import(file_path), name)
    except:
        return None


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
                raise "Copy from %s to %s but md5 not same" % (src, dst)
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
