import os
import platform
from setuptools import find_packages, setup

NAME = 'qsim'
DESCRIPTION = 'Simulation'
URL = ''
EMAIL = ''
AUTHOR = ''
REQUIRES_PYTHON = '>=3.6.0'

EXTRAS = {

}

platform_python = platform.python_version_tuple()[0] + platform.python_version_tuple()[1]
platform_machine = platform.uname().machine.lower()
platform_system = platform.uname().system
if platform_system == "Linux":
    runtime_platform = "*%s*%s*linux*so" % (platform_python, platform_machine)
elif platform_system == "Windows":
    runtime_platform = "*%s*win*%s*pyd" % (platform_python, platform_machine)
else:
    raise "System not support: %s" % platform_system
print("Runtime platform:", runtime_platform)

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, "requirements.txt")) as f:
    REQUIRED = f.readlines()

try:
    with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
        long_description = '\n' + f.read()
except FileNotFoundError:
    long_description = DESCRIPTION

about = {}
with open(os.path.join(here, 'src', NAME, 'version.py')) as f:
    exec(f.read(), about)

setup(
    name=NAME,
    version=about['__version__'],
    description=DESCRIPTION,
    long_description=long_description,
    long_description_content_type='text/markdown',
    author=AUTHOR,
    author_email=EMAIL,
    python_requires=REQUIRES_PYTHON,
    url=URL,
    packages=find_packages('src'),
    package_dir={'': 'src'},
    entry_points={
        'console_scripts': ['qsim=qsim.qsim_run:main', 'stats_general=qsim.modules.stats_general:main'],
    },
    package_data={'': ['libmd_subscriber.so', runtime_platform]},
    install_requires=REQUIRED,
    extras_require=EXTRAS,
    include_package_data=False,
    license='MIT',
    classifiers=[
        # Trove classifiers
        # Full list: https://pypi.python.org/pypi?%3Aaction=list_classifiers
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6'
    ],
)
