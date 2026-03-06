#!/bin/bash
set -e
mkdir -p ./build
./sh/make-release-tag.sh > ./machine/version.txt
uvx shiv -c machine -o build/machine .
