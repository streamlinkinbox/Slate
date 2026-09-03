#============================================================================================================================================
# 📦 Project-Zero/CMakeLists.txt — Standalone CMake Build Configuration for Project-Zero Testing Ground
#============================================================================================================================================

cmake_minimum_required(VERSION 3.20)
project(Project-Zero LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

get_filename_component(FRONTIER_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../.." ABSOLUTE)

include_directories(${FRONTIER_ROOT} ${CMAKE_CURRENT_SOURCE_DIR})

file(GLOB ENGINE_SOURCES
    "${FRONTIER_ROOT}/DeviceExchange/*.cpp"
    "${FRONTIER_ROOT}/PhysicalDynamics/*.cpp"
    "${FRONTIER_ROOT}/VolumetricDynamics/*.cpp"
    "${FRONTIER_ROOT}/GeometricRaster/*.cpp"
    "${FRONTIER_ROOT}/PhotometricIllumination/*.cpp"
    "${FRONTIER_ROOT}/PlatformInterchange/*.cpp"
    "${FRONTIER_ROOT}/DisplayPresentation/*.cpp"
)
list(FILTER ENGINE_SOURCES EXCLUDE REGEX ".*EngineExecution\\.cpp$")

file(GLOB PROJECT_ZERO_SOURCES
    "Source/*.cpp"
)

add_executable(Project-Zero ${PROJECT_ZERO_SOURCES} ${ENGINE_SOURCES})
target_compile_definitions(Project-Zero PRIVATE FRONTIER_DEVELOPMENT=1)

if(MSVC)
    target_compile_options(Project-Zero PRIVATE /W4 /WX /wd4324 /utf-8 /fp:precise /Zc:__cplusplus)
    target_link_libraries(Project-Zero PRIVATE user32 gdi32 shell32)
else()
    target_compile_options(Project-Zero PRIVATE -Wall -Wextra -Werror -pedantic)
    target_link_libraries(Project-Zero PRIVATE pthread)
endif()
