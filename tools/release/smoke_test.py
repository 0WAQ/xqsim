#!/usr/bin/env python3
"""Import smoke test intended to run from an installed binary wheel."""

from __future__ import annotations

import importlib
import importlib.metadata
import sys
from pathlib import Path

# Isolated mode deliberately omits the script directory. Add only this tooling
# directory so the test cannot accidentally import xqsim from the repository.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from release_manifest import COMPILED_MODULES  # noqa: E402


def main() -> None:
    import xqsim
    from xqsim.api import (
        AlphaBase,
        DataRepository,
        OperationBase,
        ProviderBase,
        StatsBase,
    )

    assert AlphaBase is not None
    assert DataRepository is not None
    assert OperationBase is not None
    assert ProviderBase is not None
    assert StatsBase is not None

    distribution_version = importlib.metadata.version("xqsim")
    assert xqsim.__version__ == distribution_version, (
        xqsim.__version__,
        distribution_version,
    )

    for module_name in COMPILED_MODULES:
        module = importlib.import_module(module_name)
        suffix = Path(module.__file__).suffix
        assert suffix in {".so", ".pyd"}, (module_name, module.__file__)

    # Built-ins remain file-path-loadable Python modules.
    importlib.import_module("xqsim.modules.StatsGeneral")
    importlib.import_module("xqsim.modules.StatsFutures")
    print(
        f"xqsim {distribution_version}: imported {len(COMPILED_MODULES)} "
        "binary modules successfully"
    )


if __name__ == "__main__":
    main()
