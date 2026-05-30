#!/bin/bash
basepath=$(cd `dirname $0`; pwd)
cd $basepath

pip install supervisor
mkdir -p ~/supervisor
cp -f supervisord.conf ~/supervisor/supervisord.conf
sed -i "s/USER/${USER}/g" ~/supervisor/supervisord.conf
supervisord -c ~/supervisor/supervisord.conf
