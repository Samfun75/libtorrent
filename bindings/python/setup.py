#!/usr/bin/env python3


from setuptools import setup, Extension
import os
import platform
import sys
import glob
import shutil
import multiprocessing


try:
    from wheel.bdist_wheel import bdist_wheel as _bdist_wheel

    class bdist_wheel(_bdist_wheel):
        def finalize_options(self):
            _bdist_wheel.finalize_options(self)
            self.root_is_pure = False
except ImportError:
    bdist_wheel = None

try:
    from distutils.command.install import install as _install

    class install(_install):
        def finalize_options(self):
            self.install_lib = self.install_platlib
            _install.finalize_options(self)
except ImportError:
    install = None


def parse_linking_arguments(library):
    if '--{}-link=static'.format(library) in sys.argv:
        del sys.argv[sys.argv.index('--{}-link=static'.format(library))]
        return True
    elif '--{}-link=shared'.format(library) in sys.argv:
        del sys.argv[sys.argv.index('--{}-link=shared'.format(library))]
        return False

    if library == 'libtorrent':
        return True
    elif library == 'boost':
        return True if platform.system() == 'Windows' else False


def parse_option_arguments(option, default=None):
    for arg in sys.argv:
        if arg.startswith('--{}='.format(option)):
            del sys.argv[sys.argv.index(arg)]
            return ' ' + arg

    if default:
        return ' ' + option + '=' + default
    else:
        return ''


def bjam_build():
    # prepare directories
    shutil.rmtree('build', ignore_errors=True)
    shutil.rmtree('libtorrent', ignore_errors=True)
    os.makedirs('build/lib')
    os.makedirs('libtorrent')

    # don't build libtorrent when using commands that were not supposed to use built extension
    if not any(cmd.startswith(('build', 'install', 'bdist')) for cmd in sys.argv):
        return None

    toolset = parse_option_arguments('toolset')
    file_ext = '.dll' if platform.system() == 'Windows' else '.so'

    libtorrent_link_static = parse_linking_arguments('libtorrent')
    boost_link_static = parse_linking_arguments('boost')

    if platform.system() == 'Windows' and not toolset:
        # https://packaging.python.org/guides/packaging-binary-extensions/#binary-extensions-for-windows
        #
        # See https://wiki.python.org/moin/WindowsCompilers for a table of msvc versions
        # used for each python version
        # Specify the full version number for 9.0 and 10.0 because apparently
        # older versions of boost don't support only specifying the major number and
        # there was only one version of msvc with those majors.
        # Only specify the major for msvc-14 so that 14.1, 14.11, etc can be used.
        # Hopefully people building with msvc-14 are using a new enough version of boost
        # for this to work.
        if sys.version_info[0:2] in ((2, 6), (2, 7), (3, 0), (3, 1), (3, 2)):
            toolset = ' toolset=msvc-9.0'
        elif sys.version_info[0:2] in ((3, 3), (3, 4)):
            toolset = ' toolset=msvc-10.0'
        elif sys.version_info[0:2] in ((3, 5), (3, 6), (3, 7), (3, 8), (3, 9)):
            toolset = ' toolset=msvc-14.2'  # libtorrent requires VS 2017 or newer
        else:
            # unknown python version, lets hope the user has the right version of msvc configured
            toolset = ' toolset=msvc'

    if libtorrent_link_static:
        toolset += ' libtorrent-link=static'
    if boost_link_static:
        toolset += ' boost-link=static'

    parallel_builds = ' -j%d' % multiprocessing.cpu_count()
    if sys.maxsize > 2**32:
        address_model = ' address-model=64'
    else:
        address_model = ' address-model=32'

    # don't force current Python interpreter if it was already specified in user-config.jam
    # this fixes problem with Boost which causes wrong Python include directories
    if not os.path.isfile(os.path.expanduser('~/user-config.jam')):
        # add extra quoting around the path to prevent bjam from parsing it as a list if the path has spaces
        os.environ['LIBTORRENT_PYTHON_INTERPRETER'] = '"' + sys.executable + '"'

    # build libtorrent using bjam and build the installer with distutils
    cmdline = ('b2 release optimization=space stage_module --hash' +
               address_model + toolset + parallel_builds)
    print(cmdline)
    if os.system(cmdline) != 0:
        print('build failed')
        sys.exit(1)

    # copy compiled libtorrent into correct directory
    for file in glob.glob('libtorrent*' + file_ext):
        shutil.copy2(file, 'build/lib')

    return None


def distutils_build():
    src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "src"))
    source_list = [os.path.join(src_dir, s) for s in os.listdir(src_dir) if s.endswith(".cpp")]

    ext = [Extension(
        'libtorrent',
        sources=sorted(source_list),
        language='c++',
        include_dirs=['../../include'],
        library_dirs=[],
        libraries=['torrent-rasterbar'],
        extra_compile_args=['-DTORRENT_USE_OPENSSL', '-DTORRENT_USE_LIBCRYPTO',
                            '-DBOOST_ASIO_HAS_STD_CHRONO=1 -DBOOST_EXCEPTION_DISABLE',
                            '-DBOOST_ASIO_ENABLE_CANCELIO', '-DTORRENT_LINKING_SHARED',
                            '-DTORRENT_BUILDING_LIBRARY']
    )
    ]

    return ext


with open('README.rst') as f:
    readme = f.read()

ext = bjam_build()
# ext = distutils_build()

shutil.copy2('../../COPYING', 'COPYING')
shutil.copy2('../../LICENSE', 'LICENSE')

setup(
    name='libtorrent',
    description='Python bindings for libtorrent-rasterbar',
    long_description=readme,
    license='BSD',

    version='2.0.1',

    packages=['libtorrent'],
    ext_modules=ext,

    author='Arvid Norberg',
    author_email='arvid@libtorrent.org',
    url='http://libtorrent.org',
    keywords='bittorrent, libtorrent, cpp-bindings',

    classifiers=[
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

    cmdclass={
        'bdist_wheel': bdist_wheel,
        'install': install,
    },
)
