#!/bin/bash

identifier=dev
commit=$(git log -1 --format=format:%h)

sed -E "s/version='(.*)',/version='\1-$identifier+$commit',/g" -i $1
