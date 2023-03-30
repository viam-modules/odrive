#!/bin/sh
cd `dirname $0`

exec /opt/homebrew/Caskroom/miniconda/base/envs/pysdk/bin/python -m src.main $@
