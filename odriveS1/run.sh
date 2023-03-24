#!/bin/bash

cd `dirname $0`

go build ./
exec ./odriveS1 $@