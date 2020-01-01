#!/usr/bin/env python

import shutil
import sys
import os

os.chdir('bindings/python')

try:
    sys.argv.remove('--pypi')
    shutil.copy('setup-pypi.py', 'setup.py')
except ValueError:
    shutil.copy('setup-bjam.py', 'setup.py')

exec(open('setup.py').read())
