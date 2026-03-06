include("${CMAKE_CURRENT_LIST_DIR}/LoadProjectConfig.cmake")

if(NOT EXISTS "${VENV_PYTHON}")
  message(FATAL_ERROR "Missing backend virtual environment. Run install first.")
endif()

if(WIN32)
  execute_process(
    COMMAND
      "${POWERSHELL_EXECUTABLE}"
      -NoProfile
      -ExecutionPolicy
      Bypass
      -Command
      "Start-Process -FilePath '${VENV_PYTHON}' -ArgumentList '-m','uvicorn','app.main:app','--reload','--host','127.0.0.1','--port','8000' -WorkingDirectory '${BACKEND_DIR}'"
    RESULT_VARIABLE backend_result
    COMMAND_ECHO STDOUT
  )

  if(NOT backend_result EQUAL 0)
    message(FATAL_ERROR "Failed to launch backend (${backend_result})")
  endif()

  message(STATUS "Backend started in a separate process")

  execute_process(
    COMMAND "${NPM_EXECUTABLE}" run "${FRONTEND_RUN_SCRIPT}"
    WORKING_DIRECTORY "${FRONTEND_DIR}"
    RESULT_VARIABLE frontend_result
    COMMAND_ECHO STDOUT
  )

  if(NOT frontend_result EQUAL 0)
    message(FATAL_ERROR "Frontend failed to start (${frontend_result})")
  endif()
else()
  execute_process(
    COMMAND
      sh
      -c
      "(cd \"${BACKEND_DIR}\" && \"${VENV_PYTHON}\" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000) & (cd \"${FRONTEND_DIR}\" && \"${NPM_EXECUTABLE}\" run \"${FRONTEND_RUN_SCRIPT}\")"
    RESULT_VARIABLE run_result
    COMMAND_ECHO STDOUT
  )

  if(NOT run_result EQUAL 0)
    message(FATAL_ERROR "Run failed (${run_result})")
  endif()
endif()
