include("${CMAKE_CURRENT_LIST_DIR}/LoadProjectConfig.cmake")

execute_process(
  COMMAND "${NPM_EXECUTABLE}" run "${FRONTEND_RUN_SCRIPT}"
  WORKING_DIRECTORY "${FRONTEND_DIR}"
  COMMAND_ECHO STDOUT
  RESULT_VARIABLE result
)

if(NOT result EQUAL 0)
  message(FATAL_ERROR "Frontend failed to start (${result})")
endif()
