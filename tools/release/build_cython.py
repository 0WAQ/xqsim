import sys
import os
import shutil
from setuptools import setup
from Cython.Build import cythonize

if len(sys.argv) < 2:
    print("need output dir")
    exit(0)

release_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.abspath(os.path.join(release_dir, "..", ".."))
base_dir = os.path.join(repo_root, "qsim")

ignore_list = {os.path.basename(os.path.abspath(__file__))}
copy_only_list = {"__init__.py",
                  "version.py",
                  "qsim_run.py",
                  "common_utils.py",
                  "common_module.py",
                  "data_repository.py",
                  "dbg.py",
                  "meta.py",
                  "module_base.py",
                  "alpha_base.py",
                  "provider_base.py",
                  }
setup_dir = os.path.join(release_dir, "setup")
tmp_dir = os.path.join(release_dir, "build_tmp")
output_dir = sys.argv[1]
build_dir = os.path.join(output_dir, "src/qsim")

print("base:", base_dir)
print("setup:", setup_dir)
print("output:", output_dir)
print("build:", build_dir)

extra_dir_list = ["modules"]

if os.path.exists(tmp_dir):
    shutil.rmtree(tmp_dir)
os.makedirs(tmp_dir)

if not os.path.exists(output_dir):
    os.makedirs(output_dir)

if not (len(sys.argv) > 2 and sys.argv[2] == "append"):
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)

if not os.path.exists(build_dir):
    os.makedirs(build_dir)

try:
    # copy setup.py
    for filename in os.listdir(setup_dir):
        shutil.copy(os.path.join(setup_dir, filename), os.path.join(output_dir, filename))

    # copy extra
    for dir_name in extra_dir_list:
        shutil.copytree(os.path.join(base_dir, dir_name), os.path.join(build_dir, dir_name))
except:
    pass

file_list = []
for filename in os.listdir(base_dir):
    if filename in copy_only_list:
        try:
            shutil.copy(os.path.join(base_dir, filename), os.path.join(build_dir, filename))
        except:
            pass
        continue
    # try:
    #     shutil.copy(os.path.join(base_dir, filename), os.path.join(build_dir, filename))
    # except:
    #     pass
    # continue

    if filename.endswith(".py") and os.path.isfile(os.path.join(base_dir, filename)) and filename not in ignore_list:
        src_file_path = os.path.join(base_dir, filename)
        dst_file_path = os.path.join(tmp_dir, filename)
        shutil.copy(src_file_path, dst_file_path)
        with open(dst_file_path, 'r', encoding='utf8') as f:
            content = f.read()
            content = "# cython: language_level=3\n" + content
        with open(dst_file_path, 'w', encoding='utf8') as f:
            f.write(content)
        file_list.append(dst_file_path)
print(file_list)

setup(
    ext_modules=cythonize(file_list),
    script_args=["build_ext", "-b", build_dir, "-t", tmp_dir]
)
