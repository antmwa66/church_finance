cmake_minimum_required(VERSION 3.18)
project(churchfinance-native LANGUAGES CXX)

add_library(churchfinance-native SHARED churchfinance-native.cpp)
find_library(log-lib log)

target_compile_features(churchfinance-native PRIVATE cxx_std_17)
target_link_libraries(churchfinance-native ${log-lib})