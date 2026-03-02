include("${CMAKE_CURRENT_LIST_DIR}/LoadProjectConfig.cmake")

function(run_checked)
  set(options)
  set(oneValueArgs WORKING_DIRECTORY)
  set(multiValueArgs COMMAND)
  cmake_parse_arguments(RUN "${options}" "${oneValueArgs}" "${multiValueArgs}" ${ARGN})

  if(NOT RUN_COMMAND)
    message(FATAL_ERROR "run_checked requires COMMAND")
  endif()

  execute_process(
    COMMAND ${RUN_COMMAND}
    WORKING_DIRECTORY "${RUN_WORKING_DIRECTORY}"
    RESULT_VARIABLE result
    COMMAND_ECHO STDOUT
  )

  if(NOT result EQUAL 0)
    string(REPLACE ";" " " display_command "${RUN_COMMAND}")
    message(FATAL_ERROR "Command failed (${result}): ${display_command}")
  endif()
endfunction()

if(NOT EXISTS "${PYTHON_VENV_DIR}/pyvenv.cfg")
  message(STATUS "Creating backend virtual environment")
  run_checked(COMMAND "${PYTHON_EXECUTABLE}" -m venv "${PYTHON_VENV_DIR}")
endif()

if(NOT EXISTS "${VENV_PYTHON}")
  message(FATAL_ERROR "Virtual environment python not found at: ${VENV_PYTHON}")
endif()

message(STATUS "Installing backend dependencies")
run_checked(COMMAND "${VENV_PYTHON}" -m pip install --upgrade pip)
run_checked(COMMAND "${VENV_PYTHON}" -m pip install --upgrade setuptools wheel)
run_checked(
  COMMAND "${VENV_PYTHON}" -m pip install -r requirements.txt
  WORKING_DIRECTORY "${BACKEND_DIR}"
)

message(STATUS "Installing frontend dependencies")
if(EXISTS "${FRONTEND_DIR}/package-lock.json")
  run_checked(
    COMMAND "${NPM_EXECUTABLE}" ci
    WORKING_DIRECTORY "${FRONTEND_DIR}"
  )
else()
  run_checked(
    COMMAND "${NPM_EXECUTABLE}" install
    WORKING_DIRECTORY "${FRONTEND_DIR}"
  )
endif()

if(NOT EXISTS "${BACKEND_DIR}/.env")
  file(
    WRITE "${BACKEND_DIR}/.env"
    "JWT_SECRET_KEY=change-this-jwt-secret\nJWT_EXPIRE_MINUTES=10080\n"
  )
  message(STATUS "Created backend/.env")
endif()

if(NOT EXISTS "${FRONTEND_DIR}/.env")
  file(
    WRITE "${FRONTEND_DIR}/.env"
    "VITE_API_URL=http://127.0.0.1:8000\n"
  )
  message(STATUS "Created frontend/.env")
endif()

message(STATUS "Install completed")
