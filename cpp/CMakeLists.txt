cmake_minimum_required(VERSION 3.20)
project(order_latency_bench CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

# libcurl, OpenSSL 위치는 -DCMAKE_PREFIX_PATH=<prefix>로 넘긴다(README 참고).
find_package(CURL REQUIRED)
find_package(OpenSSL 3 REQUIRED)

if(MSVC)
  add_compile_options(/W4 /utf-8 /O2)
endif()

add_library(upbit_order STATIC src/upbit_order.cpp)
target_include_directories(upbit_order PUBLIC src)
target_link_libraries(upbit_order PUBLIC OpenSSL::Crypto)

add_executable(upbit_bench src/bench.cpp)
target_link_libraries(upbit_bench PRIVATE upbit_order CURL::libcurl)

if(WIN32)
  add_executable(mock_server src/mock_server.cpp)
  target_link_libraries(mock_server PRIVATE ws2_32)
endif()
