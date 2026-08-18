cmake_minimum_required(VERSION 3.10)
project(good_multiphysics)

add_subdirectory(src/structural)
add_subdirectory(src/thermal)
add_subdirectory(src/fluid)
add_subdirectory(coupling)
add_subdirectory(plugin)

target_link_libraries(coupling structural thermal fluid)
target_link_libraries(plugin coupling)
