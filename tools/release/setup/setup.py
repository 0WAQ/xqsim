"""PEP 517 build definition copied into the generated release staging tree."""

import json
from pathlib import Path

from Cython.Build import cythonize
from setuptools import Extension, find_packages, setup


ROOT = Path(__file__).resolve().parent
METADATA = json.loads((ROOT / "release_metadata.json").read_text(encoding="utf-8"))
COMPILED_MODULES = METADATA["compiled_modules"]


def module_source(module_name: str) -> str:
    return str(Path("cython_src", *module_name.split(".")).with_suffix(".py"))


extensions = [
    Extension(module_name, [module_source(module_name)])
    for module_name in COMPILED_MODULES
]

setup(
    name="xqsim",
    version=METADATA["version"],
    description=METADATA["description"],
    python_requires=METADATA["requires_python"],
    install_requires=METADATA["dependencies"],
    packages=find_packages("src"),
    package_dir={"": "src"},
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            "language_level": 3,
            "binding": True,
            "embedsignature": True,
        },
    ),
    entry_points={
        "console_scripts": [
            "xqsim=xqsim.xqsim_run:main",
            "stats_general=xqsim.modules.stats_general:main",
        ]
    },
    include_package_data=False,
    license="MIT",
)
