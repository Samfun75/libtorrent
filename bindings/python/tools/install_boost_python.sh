#! /bin/bash

set -e
set -x

# Get number of CPU cores and Python version
# Write Python config to fix bug where Boost guesses wrong paths
cores=$(python -c "import multiprocessing; print(multiprocessing.cpu_count(), end='')")
version=$(python -c "import sys; print(sys.version[:3].replace('.', ''), end='')")
model=$(python -c "import sys; print('x64' if sys.maxsize > 2**32 else 'x32', end='')")
python $1/bindings/python/tools/generate_boost_config.py ~/user-config.jam

# Don't re-build and re-install Boost if it was already installed previously
if [[ "$OSTYPE" == "msys" ]] && [[ -f /c/Boost/lib/libboost_python$version-mt-$model.lib ]]
then
  echo Using cache...
  rm -f /c/Boost/lib/boost_system.lib
  rm -f /c/Boost/lib/boost_python3.lib
  ln /c/Boost/lib/libboost_system-mt-$model.lib /c/Boost/lib/boost_system.lib
  ln /c/Boost/lib/libboost_python$version-mt-$model.lib /c/Boost/lib/boost_python3.lib
  exit 0
elif [[ "$OSTYPE" == "darwin"* ]] && [[ -f /usr/local/lib/libboost_python$version-mt.dylib ]]
then
  echo Using cache...
  exit 0
fi

# Install Boost as root and use same config as Boost from Homebrew on macOS
# On other systems, just use normal tagged layout
if [[ "$OSTYPE" == "darwin"* ]]
then
  root=sudo
  threading=threading=multi,single
  link=link=shared,static
  layout=--layout=tagged-1.66
else
  layout=--layout=tagged
fi

# Use MSVC and specific prefixes for Boost on Windows
if [[ "$OSTYPE" == "msys" ]]
then
  toolset=toolset=msvc
  prefix=--prefix=C:/Boost
fi

# Download Boost sources if they are not already downloaded
if [[ ! -d /tmp/boost_1_73_0 ]]
then
  curl -L https://dl.bintray.com/boostorg/release/1.73.0/source/boost_1_73_0.tar.gz -o /tmp/boost.tar.gz
  tar xzf /tmp/boost.tar.gz -C /tmp
fi

# Install Boost Python
cd /tmp/boost_1_73_0
rm -f project-config.jam
./bootstrap.sh --with-libraries=python --with-python=python3 $prefix
$root ./b2 install release $toolset $threading $link $layout $prefix -j$cores

# Link Boost.System and Boost.Python library to correct name
if [[ "$OSTYPE" == "linux-gnu"* ]]
then
  rm -f /usr/local/lib/libboost_system.a /usr/local/lib/libboost_system.so
  rm -f /usr/local/lib/libboost_python3.a /usr/local/lib/libboost_python3.so
  ln /usr/local/lib/libboost_system-mt-$model.a /usr/local/lib/libboost_system.a
  ln /usr/local/lib/libboost_system-mt-$model.so /usr/local/lib/libboost_system.so
  ln /usr/local/lib/libboost_python$version-mt-$model.a /usr/local/lib/libboost_python3.a
  ln /usr/local/lib/libboost_python$version-mt-$model.so /usr/local/lib/libboost_python3.so
elif [[ "$OSTYPE" == "msys" ]]
then
  rm -f /c/Boost/lib/boost_system.lib
  rm -f /c/Boost/lib/boost_python3.lib
  ln /c/Boost/lib/libboost_system-mt-$model.lib /c/Boost/lib/boost_system.lib
  ln /c/Boost/lib/libboost_python$version-mt-$model.lib /c/Boost/lib/boost_python3.lib
fi

# Fix library ID on macOS
if [[ "$OSTYPE" == "darwin"* ]]
then
  $root install_name_tool /usr/local/lib/libboost_python$version-mt.dylib -id /usr/local/lib/libboost_python$version-mt.dylib
fi
