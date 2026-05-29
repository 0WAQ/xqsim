basepath=$(
  cd $(dirname $0)
  pwd
)
cd $basepath

OUTPUT=/home/michael/qsim

BIN=${CONDA_PREFIX}/bin
echo "${BIN}"
PIP=${BIN}/pip
PYTHON=${BIN}/python

${PIP} install -r ../setup/requirements.txt -i http://mirrors.aliyun.com/pypi/simple --trusted-host mirrors.aliyun.com
${PYTHON} ../build_cython.py ${OUTPUT} append

cd ${OUTPUT} && sudo "${PIP}" install . && cd -