"""Explicit module boundary for the binary xqsim distribution.

Every Python module under xqsim/ must appear in exactly one list. The build
fails when a new module is not classified, so adding code cannot silently
change the public/source boundary of the released wheel.
"""

# Researcher-facing contracts, entry points, and file-path-loaded built-ins
# stay as Python source. These modules are intentionally easy to inspect and
# extend.
SOURCE_MODULES = (
    "xqsim",
    "xqsim.alpha_base",
    "xqsim.api",
    "xqsim.base",
    "xqsim.base.alpha_base",
    "xqsim.base.module_base",
    "xqsim.base.operation_base",
    "xqsim.base.provider_base",
    "xqsim.base.stats_base",
    "xqsim.data",
    "xqsim.data.data_repository",
    "xqsim.data.meta",
    "xqsim.manager",
    "xqsim.modules",
    "xqsim.modules.stats_futures",
    "xqsim.modules.stats_general",
    "xqsim.version",
    "xqsim.xqsim_run",
)

# Internal runtime implementation. These modules become CPython extension
# modules (.so on Linux, .pyd on Windows) inside the platform wheel.
COMPILED_MODULES = (
    "xqsim.base.utils",
    "xqsim.common_module",
    "xqsim.common_utils",
    "xqsim.data.data_manager",
    "xqsim.data.data_repository_impl",
    "xqsim.data.meta_loader",
    "xqsim.dbg",
    "xqsim.manager.alpha_manager",
    "xqsim.manager.provider_manager",
    "xqsim.simulator",
    "xqsim.utils",
)

# The legacy module imports the removed ksim package and is not referenced by
# any current configuration. Keeping the exclusion explicit prevents it from
# silently returning to a release without a compatibility decision.
EXCLUDED_MODULES = {
    "xqsim.modules.stats_simple": "legacy ksim dependency",
}

# Versions are pinned because they affect generated C code and wheel contents.
BUILD_REQUIRES = (
    "setuptools==84.0.0",
    "cython==3.2.9",
)

PYINSTALLER_REQUIREMENT = "pyinstaller==6.21.0"

# Imports performed inside Cython extensions are not all visible to
# PyInstaller's static analysis. Keep the frozen boundary explicit as well.
FROZEN_HIDDEN_IMPORTS = tuple(
    sorted(
        {
            *SOURCE_MODULES,
            *COMPILED_MODULES,
            "click",
            "lz4",
            "lz4.frame",
            "numcodecs",
            "numpy",
            "pandas",
            "sortedcollections",
            "sortedcontainers",
            "xmltodict",
            "yaml",
        }
    )
)

SUPPORTED_PYTHON = (3, 12)
SUPPORTED_PLATFORMS = (("Linux", "x86_64"),)
