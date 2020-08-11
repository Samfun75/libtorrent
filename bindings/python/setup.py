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


def bjam_build():
    # prepare directories
    shutil.rmtree('build', ignore_errors=True)
    shutil.rmtree('libtorrent', ignore_errors=True)
    os.makedirs('build/lib')
    os.makedirs('libtorrent')

    # don't build libtorrent when using commands that were not supposed to use built extension
    if any(cmd in ['--help', '--help-commands', 'clean', 'sdist', 'dist_info', 'egg_info'] for cmd in sys.argv):
        return None

    toolset = ''
    file_ext = '.so'
    static_link = True

    if '--static-link' in sys.argv:
        del sys.argv[sys.argv.index('--static-link')]
        static_link = True

    if '--shared-link' in sys.argv:
        del sys.argv[sys.argv.index('--shared-link')]
        static_link = False

    if platform.system() == 'Windows':
        file_ext = '.pyd'
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
        elif sys.version_info[0:2] in ((3, 5), (3, 6), (3, 7), (3, 8)):
            toolset = ' toolset=msvc-14.2'  # libtorrent requires VS 2017 or newer
        else:
            # unknown python version, lets hope the user has the right version of msvc configured
            toolset = ' toolset=msvc'

        # on windows, just link all the dependencies together to keep it simple
        toolset += ' boost-link=static'
        static_link = True

    if static_link:
        toolset += ' libtorrent-link=static'

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
    shutil.copy2(glob.glob('libtorrent*' + file_ext)[0], 'build/lib')

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

    version='2.0.0',

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
