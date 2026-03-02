include("${CMAKE_CURRENT_LIST_DIR}/LoadProjectConfig.cmake")

if(NOT EXISTS "${VENV_PYTHON}")
  message(FATAL_ERROR "Missing backend virtual environment. Run install first.")
endif()

execute_process(
  COMMAND "${VENV_PYTHON}" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
  WORKING_DIRECTORY "${BACKEND_DIR}"
  COMMAND_ECHO STDOUT
  RESULT_VARIABLE result
)

if(NOT result EQUAL 0)
  message(FATAL_ERROR "Backend failed to start (${result})")
endif()
