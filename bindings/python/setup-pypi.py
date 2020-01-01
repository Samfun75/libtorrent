from setuptools import setup, Extension
import shutil
import glob
import sys
import os


def copy(src, dst):
    if os.path.exists(dst):
        shutil.rmtree(dst)

    shutil.copytree(src, dst)


with open('README.rst') as f:
    readme = f.read()

if os.path.isfile('setup-pypi.py') and os.path.isfile('setup-bjam.py'):
    shutil.copy2('../../COPYING', 'COPYING')
    shutil.copy2('../../LICENSE', 'LICENSE')

    copy('../../include/libtorrent', 'include/libtorrent')
    copy('../../src', 'lib/libtorrent')

src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'src'))
src_list = [os.path.join(src_dir, s) for s in os.listdir(src_dir) if s.endswith('.cpp')]

libtorrent_include = 'include'
libtorrent_lib = 'lib'

boost_include = os.environ.get('BOOST_ROOT')
boost_lib = os.environ.get('BOOST_LIBRARYDIR')

python_version = str(sys.version_info[0]) + str(sys.version_info[1])

include_dirs = [libtorrent_include, boost_include]
libraries = ['boost_system', 'boost_python' + python_version]

if sys.platform == 'win32':
    library_dirs = [libtorrent_lib, boost_lib]
    extra_objects = []
else:
    library_dirs = [libtorrent_lib]
    extra_objects = ['{}/lib{}.a'.format(boost_lib, lib) for lib in libraries]
    libraries = None

extra_compile_args = ['-std=c++14', '-DTORRENT_USE_OPENSSL', '-DTORRENT_USE_LIBCRYPTO', '-DBOOST_ASIO_ENABLE_CANCELIO', '-DBOOST_ASIO_HAS_STD_CHRONO=1', '-DBOOST_EXCEPTION_DISABLE']

module = Extension(
    'libtorrent',
    sorted(src_list),

    language='c++',

    library_dirs=library_dirs,
    include_dirs=include_dirs,

    libraries=libraries,
    extra_objects=extra_objects,

    extra_compile_args=extra_compile_args,
    extra_link_args=extra_compile_args,
)

data_files = [('.', ['README.rst', 'COPYING', 'LICENSE'])]

if 'sdist' in sys.argv:
    data_files.append(('.', glob.glob('include/**/*.hpp', recursive=True)))
    data_files.append(('.', glob.glob('lib/**/*.cpp', recursive=True)))
    data_files.append(('.', glob.glob('src/**/*.[ch]pp', recursive=True)))

setup(
    name = 'libtorrent',
    description = 'Python bindings for libtorrent-rasterbar',
    long_description = readme,
    license = 'BSD',

    version = '2.0.0',

    ext_modules = [module],
    data_files = data_files,

    author = 'Arvid Norberg',
    author_email = 'arvid@libtorrent.org',
    url = 'http://libtorrent.org',
    keywords = 'bittorrent, libtorrent, cpp-bindings',

    classifiers = [
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
        'Topic :: Communications :: File Sharing',
        'Topic :: Internet',
        'Topic :: Scientific/Engineering :: Interface Engine/Protocol Translator',
        'Topic :: Software Development :: Libraries',
        'Topic :: System :: Networking',
        'Topic :: Utilities',
    ],
)
