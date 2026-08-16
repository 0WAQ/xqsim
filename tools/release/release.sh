#!/usr/bin/env bash

# Build the binary wheel, freeze it into one executable, smoke-test it, and
# optionally publish it under /usr/local/xqsim (or another explicit root).
set -euo pipefail

release_dir=$(cd "$(dirname "$0")" && pwd)
repo_root=$(cd "${release_dir}/../.." && pwd)
python_bin=${PYTHON:-"${repo_root}/.venv/bin/python"}
uv_bin=${UV:-uv}

if [[ ! -x "${python_bin}" ]]; then
    echo "Python interpreter not found: ${python_bin}" >&2
    exit 1
fi

if [[ "${ALLOW_DIRTY:-0}" != "1" ]] && \
    [[ -n "$(git -C "${repo_root}" status --porcelain)" ]]; then
    echo "Refusing to release from a dirty worktree; set ALLOW_DIRTY=1 for a local test build." >&2
    exit 1
fi

base_version=$(
    "${python_bin}" -c \
        "import sys; sys.path.insert(0, '${repo_root}'); from xqsim.version import VERSION; print(VERSION)"
)
git_sha=$(git -C "${repo_root}" rev-parse --short=12 HEAD)
release_version=${RELEASE_VERSION:-"${base_version}+g${git_sha}"}
output=${OUTPUT:-"${release_dir}/output/${release_version}"}
pyinstaller_requirement=$(
    "${python_bin}" -c \
        "import sys; sys.path.insert(0, '${release_dir}'); from release_manifest import PYINSTALLER_REQUIREMENT; print(PYINSTALLER_REQUIREMENT)"
)

build_args=("${output}" --version "${release_version}")
if [[ -n "${MANYLINUX_PLAT:-}" ]]; then
    build_args+=(--manylinux-platform "${MANYLINUX_PLAT}")
fi
if [[ "${NO_BUILD_ISOLATION:-0}" == "1" ]]; then
    build_args+=(--no-build-isolation)
fi

"${python_bin}" "${release_dir}/build_cython.py" "${build_args[@]}"

wheel=$(find "${output}/wheels" -maxdepth 1 -type f -name 'xqsim-*.whl' -print -quit)
if [[ -z "${wheel}" ]]; then
    echo "Built wheel not found in ${output}/wheels" >&2
    exit 1
fi

smoke_root=$(mktemp -d)
trap 'rm -rf "${smoke_root}"' EXIT
smoke_python="${smoke_root}/venv/bin/python"

if [[ "${SMOKE_NO_DEPS:-0}" == "1" ]]; then
    "${uv_bin}" venv --python "${python_bin}" \
        --system-site-packages "${smoke_root}/venv"
else
    "${uv_bin}" venv --python "${python_bin}" "${smoke_root}/venv"
fi

runtime_install_args=(
    --python "${smoke_python}"
    --strict
    --constraint "${output}/constraints.txt"
)
if [[ "${SMOKE_NO_DEPS:-0}" == "1" ]]; then
    runtime_install_args+=(--no-deps)
fi
build_install_args=(--python "${smoke_python}")
if [[ -n "${DEPENDENCY_WHEELHOUSE:-}" ]]; then
    runtime_install_args+=(
        --no-index
        --find-links "${DEPENDENCY_WHEELHOUSE}"
    )
    build_install_args+=(
        --no-index
        --find-links "${DEPENDENCY_WHEELHOUSE}"
    )
fi

"${uv_bin}" pip install "${runtime_install_args[@]}" "${wheel}"
"${uv_bin}" pip install "${build_install_args[@]}" "${pyinstaller_requirement}"

(
    cd "${smoke_root}"
    "${smoke_python}" -I "${release_dir}/smoke_test.py"
    "${smoke_root}/venv/bin/xqsim" --version
)

"${smoke_python}" "${release_dir}/build_executable.py" "${output}"
executable="${output}/executable/xqsim"
"${python_bin}" "${release_dir}/executable_smoke_test.py" \
    "${executable}" --expected-version "${release_version}"

if [[ -n "${PUBLISH_ROOT:-}" ]]; then
    "${python_bin}" "${release_dir}/deploy.py" \
        --artifact "${output}" --root "${PUBLISH_ROOT}"
fi

echo "Release ready: ${output}"
