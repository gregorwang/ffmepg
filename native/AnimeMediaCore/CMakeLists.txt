cmake_minimum_required(VERSION 3.21)

project(AnimeMediaCore LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(AnimeMediaCore SHARED
    src/AnimeMediaCore.cpp
)

target_include_directories(AnimeMediaCore
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_compile_definitions(AnimeMediaCore
    PRIVATE
        WIN32_LEAN_AND_MEAN
        NOMINMAX
)

set_target_properties(AnimeMediaCore PROPERTIES
    OUTPUT_NAME "AnimeMediaCore"
)
