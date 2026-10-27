cmake_minimum_required(VERSION 3.13)

project(BFVNoiseUpperBoundBenchmark VERSION 1.0 LANGUAGES CXX)

find_package(SEAL 4.1 REQUIRED)

add_executable(bfv_noise_upper_bound_benchmark
  bfv_noise_upper_bound_benchmark.cpp
  ../../ufhe/src/ufhe/seal_backend/bfv_noise_estimator.cpp
)

target_include_directories(bfv_noise_upper_bound_benchmark PRIVATE ../../ufhe/src)
target_compile_features(bfv_noise_upper_bound_benchmark PRIVATE cxx_std_17)
set_target_properties(bfv_noise_upper_bound_benchmark PROPERTIES CXX_EXTENSIONS OFF)
target_link_libraries(bfv_noise_upper_bound_benchmark PRIVATE SEAL::seal)

if(WIN32)
  target_link_libraries(bfv_noise_upper_bound_benchmark PRIVATE bcrypt)
endif()

add_executable(bfv_noise_bound_workloads
  bfv_noise_bound_workloads.cpp
  ../../ufhe/src/ufhe/seal_backend/bfv_noise_estimator.cpp
)

target_include_directories(bfv_noise_bound_workloads PRIVATE ../../ufhe/src)
target_compile_features(bfv_noise_bound_workloads PRIVATE cxx_std_17)
set_target_properties(bfv_noise_bound_workloads PROPERTIES CXX_EXTENSIONS OFF)
target_link_libraries(bfv_noise_bound_workloads PRIVATE SEAL::seal)

if(WIN32)
  target_link_libraries(bfv_noise_bound_workloads PRIVATE bcrypt)
endif()

add_executable(bfv_noise_bound_cli
  bfv_noise_bound_cli.cpp
  ../../ufhe/src/ufhe/seal_backend/bfv_noise_estimator.cpp
)

target_include_directories(bfv_noise_bound_cli PRIVATE ../../ufhe/src)
target_compile_features(bfv_noise_bound_cli PRIVATE cxx_std_17)
set_target_properties(bfv_noise_bound_cli PROPERTIES CXX_EXTENSIONS OFF)
target_link_libraries(bfv_noise_bound_cli PRIVATE SEAL::seal)

if(WIN32)
  target_link_libraries(bfv_noise_bound_cli PRIVATE bcrypt)
endif()
