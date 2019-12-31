#!/usr/bin/env python

import shutil
import os

os.chdir('bindings/python')
shutil.copy('setup-bjam.py', 'setup.py')

exec(open('setup.py').read())
