#!/bin/bash
basepath=$(cd `dirname $0`; pwd)
cd $basepath

pip install .

echo "Starting Prefect server..."
echo "Set PREFECT_API_URL=http://127.0.0.1:4200/api in your environment to connect."
prefect server start
