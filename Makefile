CMAKE ?= cmake
PROJECT_ROOT := $(CURDIR)

.PHONY: configure install run run-backend run-frontend clean

configure:
	@echo "No configure step required for script-mode workflow."

install:
	$(CMAKE) -DPROJECT_ROOT="$(PROJECT_ROOT)" -P cmake/Install.cmake

run:
	$(CMAKE) -DPROJECT_ROOT="$(PROJECT_ROOT)" -P cmake/Run.cmake

run-backend:
	$(CMAKE) -DPROJECT_ROOT="$(PROJECT_ROOT)" -P cmake/RunBackend.cmake

run-frontend:
	$(CMAKE) -DPROJECT_ROOT="$(PROJECT_ROOT)" -P cmake/RunFrontend.cmake

clean:
	$(CMAKE) -E rm -rf build
