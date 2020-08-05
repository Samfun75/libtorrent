from sysconfig import get_paths
import sys

paths = get_paths()

version = sys.version[:3]
executable = sys.executable.replace('\\', '/')
include = paths['include'].replace('\\', '/')

filename = sys.argv[1]
config = ' : '.join(['using python', version, executable, include]) + ' ;\n'

with open(filename, 'w') as file:
    print(config)
    file.write(config)
