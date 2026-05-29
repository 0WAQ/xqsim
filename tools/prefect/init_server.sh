basepath=$(cd `dirname $0`; pwd)
cd $basepath

pip install .
prefect backend server
mkdir -p ~/.prefect
cp -f install/backend.toml ~/.prefect/backend.toml