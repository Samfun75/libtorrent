#! /bin/bash

set -e
set -x

# Don't re-build and re-install Boost if it was already installed previously
if [[ "$OSTYPE" == "msys" ]] && [[ -f /c/Boost/bin/b2.exe ]]
then
  echo Using cache...
  exit 0
elif [[ "$OSTYPE" == "darwin"* ]] && [[ -f /usr/local/bin/b2 ]]
then
  echo Using cache...
  exit 0
fi

# Download Boost sources
curl -L https://dl.bintray.com/boostorg/release/1.73.0/source/boost_1_73_0.tar.gz -o /tmp/boost.tar.gz
tar xzf /tmp/boost.tar.gz -C /tmp

# Install Boost from Homebrew on macOS
if [[ "$OSTYPE" == "darwin"* ]]
then
  brew update
  brew install boost boost-build
  exit 0
fi

# Add modern Python to PATH on Linux
if [[ "$OSTYPE" == "linux-gnu"* ]]
then
  PATH=/opt/python/cp38-cp38/bin:$PATH
fi

# Use MSVC and specific prefixes for Boost on Windows
if [[ "$OSTYPE" == "msys" ]]
then
  toolset=toolset=msvc
  prefix=--prefix=C:/Boost
fi

# Get number of CPU cores
cores=$(python -c "import multiprocessing; print(multiprocessing.cpu_count(), end='')")

# Install Boost without Python
cd /tmp/boost_1_73_0
rm -f project-config.jam
./bootstrap.sh --without-libraries=python $prefix
./b2 install release $toolset --layout=tagged $prefix -j$cores

# Install Boost Build
cd /tmp/boost_1_73_0/tools/build
./bootstrap.sh
./b2 install release $toolset -j$cores
