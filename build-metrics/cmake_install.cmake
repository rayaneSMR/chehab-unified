# Install script for directory: .

# Set the install prefix
if(NOT DEFINED CMAKE_INSTALL_PREFIX)
  set(CMAKE_INSTALL_PREFIX "C:/Program Files (x86)/FHECo")
endif()
string(REGEX REPLACE "/$" "" CMAKE_INSTALL_PREFIX "${CMAKE_INSTALL_PREFIX}")

# Set the install configuration name.
if(NOT DEFINED CMAKE_INSTALL_CONFIG_NAME)
  if(BUILD_TYPE)
    string(REGEX REPLACE "^[^A-Za-z0-9_]+" ""
           CMAKE_INSTALL_CONFIG_NAME "${BUILD_TYPE}")
  else()
    set(CMAKE_INSTALL_CONFIG_NAME "")
  endif()
  message(STATUS "Install configuration: \"${CMAKE_INSTALL_CONFIG_NAME}\"")
endif()

# Set the component getting installed.
if(NOT CMAKE_INSTALL_COMPONENT)
  if(COMPONENT)
    message(STATUS "Install component: \"${COMPONENT}\"")
    set(CMAKE_INSTALL_COMPONENT "${COMPONENT}")
  else()
    set(CMAKE_INSTALL_COMPONENT)
  endif()
endif()

# Is this installation the result of a crosscompile?
if(NOT DEFINED CMAKE_CROSSCOMPILING)
  set(CMAKE_CROSSCOMPILING "FALSE")
endif()

# Set path to fallback-tool for dependency-resolution.
if(NOT DEFINED CMAKE_OBJDUMP)
  set(CMAKE_OBJDUMP "C:/c_files/mingw64/bin/objdump.exe")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
  list(APPEND CMAKE_ABSOLUTE_DESTINATION_FILES
   "C:/Program Files (x86)/FHECo/lib/libfheco.a")
  if(CMAKE_WARN_ON_ABSOLUTE_INSTALL_DESTINATION)
    message(WARNING "ABSOLUTE path INSTALL DESTINATION : ${CMAKE_ABSOLUTE_DESTINATION_FILES}")
  endif()
  if(CMAKE_ERROR_ON_ABSOLUTE_INSTALL_DESTINATION)
    message(FATAL_ERROR "ABSOLUTE path INSTALL DESTINATION forbidden (by caller): ${CMAKE_ABSOLUTE_DESTINATION_FILES}")
  endif()
  file(INSTALL DESTINATION "C:/Program Files (x86)/FHECo/lib" TYPE STATIC_LIBRARY FILES "./build-metrics/libfheco.a")
endif()

if(NOT CMAKE_INSTALL_LOCAL_ONLY)
  # Include the install script for each subdirectory.
  include("./build-metrics/src/fheco/cmake_install.cmake")
  include("./build-metrics/benchmarks/box_blur/cmake_install.cmake")
  include("./build-metrics/benchmarks/sort/cmake_install.cmake")
  include("./build-metrics/benchmarks/max/cmake_install.cmake")
  include("./build-metrics/benchmarks/dot_product/cmake_install.cmake")
  include("./build-metrics/benchmarks/gx_kernel/cmake_install.cmake")
  include("./build-metrics/benchmarks/gy_kernel/cmake_install.cmake")
  include("./build-metrics/benchmarks/sobel/cmake_install.cmake")
  include("./build-metrics/benchmarks/roberts_cross/cmake_install.cmake")
  include("./build-metrics/benchmarks/hamming_dist/cmake_install.cmake")
  include("./build-metrics/benchmarks/l2_distance/cmake_install.cmake")
  include("./build-metrics/benchmarks/lin_reg/cmake_install.cmake")
  include("./build-metrics/benchmarks/matrix_mul/cmake_install.cmake")
  include("./build-metrics/benchmarks/poly_reg/cmake_install.cmake")
  include("./build-metrics/benchmarks/polynomials_coyote/cmake_install.cmake")
  include("./build-metrics/benchmarks/poly_derivative/cmake_install.cmake")
  include("./build-metrics/benchmarks/discrete_cosin_transform/cmake_install.cmake")
  include("./build-metrics/benchmarks/conv2d/cmake_install.cmake")
  include("./build-metrics/benchmarks/deep_network/cmake_install.cmake")
  include("./build-metrics/benchmarks/dnn_tensor/cmake_install.cmake")
  include("./build-metrics/RL/veclang_runner/cmake_install.cmake")

endif()

string(REPLACE ";" "\n" CMAKE_INSTALL_MANIFEST_CONTENT
       "${CMAKE_INSTALL_MANIFEST_FILES}")
if(CMAKE_INSTALL_LOCAL_ONLY)
  file(WRITE "./build-metrics/install_local_manifest.txt"
     "${CMAKE_INSTALL_MANIFEST_CONTENT}")
endif()
if(CMAKE_INSTALL_COMPONENT)
  if(CMAKE_INSTALL_COMPONENT MATCHES "^[a-zA-Z0-9_.+-]+$")
    set(CMAKE_INSTALL_MANIFEST "install_manifest_${CMAKE_INSTALL_COMPONENT}.txt")
  else()
    string(MD5 CMAKE_INST_COMP_HASH "${CMAKE_INSTALL_COMPONENT}")
    set(CMAKE_INSTALL_MANIFEST "install_manifest_${CMAKE_INST_COMP_HASH}.txt")
    unset(CMAKE_INST_COMP_HASH)
  endif()
else()
  set(CMAKE_INSTALL_MANIFEST "install_manifest.txt")
endif()

if(NOT CMAKE_INSTALL_LOCAL_ONLY)
  file(WRITE "./build-metrics/${CMAKE_INSTALL_MANIFEST}"
     "${CMAKE_INSTALL_MANIFEST_CONTENT}")
endif()
