cmake_minimum_required(VERSION 3.22)

project(AILifeAssistant NONE)

set(PROJECT_ROOT "${CMAKE_CURRENT_SOURCE_DIR}")
set(BACKEND_DIR "${PROJECT_ROOT}/backend")
set(FRONTEND_DIR "${PROJECT_ROOT}/frontend")
set(PYTHON_VENV_DIR "${BACKEND_DIR}/.venv")
set(FRONTEND_RUN_SCRIPT "dev" CACHE STRING "npm script used by run targets")

find_program(PYTHON_EXECUTABLE NAMES python3 python REQUIRED)
find_program(NPM_EXECUTABLE NAMES npm.cmd npm REQUIRED)
if(WIN32)
  find_program(POWERSHELL_EXECUTABLE NAMES pwsh powershell REQUIRED)
endif()

if(WIN32)
  set(VENV_PYTHON "${PYTHON_VENV_DIR}/Scripts/python.exe")
else()
  set(VENV_PYTHON "${PYTHON_VENV_DIR}/bin/python")
endif()

configure_file(
  "${PROJECT_ROOT}/cmake/ProjectConfig.cmake.in"
  "${CMAKE_BINARY_DIR}/ProjectConfig.cmake"
  @ONLY
)

add_custom_target(run
  COMMAND
    "${CMAKE_COMMAND}"
    -DPROJECT_CONFIG="${CMAKE_BINARY_DIR}/ProjectConfig.cmake"
    -P "${PROJECT_ROOT}/cmake/Run.cmake"
  USES_TERMINAL
  COMMENT "Start backend and frontend"
)

add_custom_target(run-backend
  COMMAND
    "${CMAKE_COMMAND}"
    -DPROJECT_CONFIG="${CMAKE_BINARY_DIR}/ProjectConfig.cmake"
    -P "${PROJECT_ROOT}/cmake/RunBackend.cmake"
  USES_TERMINAL
  COMMENT "Start backend only"
)

add_custom_target(run-frontend
  COMMAND
    "${CMAKE_COMMAND}"
    -DPROJECT_CONFIG="${CMAKE_BINARY_DIR}/ProjectConfig.cmake"
    -P "${PROJECT_ROOT}/cmake/RunFrontend.cmake"
  USES_TERMINAL
  COMMENT "Start frontend only"
)

install(
  CODE
  "
set(PROJECT_CONFIG \"${CMAKE_BINARY_DIR}/ProjectConfig.cmake\")
include(\"${PROJECT_ROOT}/cmake/Install.cmake\")
"
)
