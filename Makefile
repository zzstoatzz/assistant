# Makefile for running the assistant and setting up environment variables

ifeq (,$(shell which uv))
$(error "uv is not installed. Please install it using one of these methods:\n\
	• curl -LsSf https://astral.sh/uv/install.sh | sh  # For macOS/Linux\n\
	• pip install uv  # Using pip\n\
	For more information, visit: https://github.com/astral-sh/uv")
endif

# Configuration
DOCKER_IMAGE := assistant
DOCKERFILE := app/Dockerfile.main

-include .env
export

DEV_PORT ?= 8001
HOST ?= localhost

.PHONY: all
all: setup run

.PHONY: setup
setup: check-env
	@echo "✨ Setup complete"

.PHONY: check-env
check-env:
	@uv run scripts/configure.py

# Development with hot reload
.PHONY: dev
dev:
	uv run fastapi dev app/main.py --host $(HOST) --port $(DEV_PORT)

# Run in production mode
.PHONY: run
run:
	docker build -t $(DOCKER_IMAGE) -f $(DOCKERFILE) . && \
	docker run --rm \
		-p $(ASSISTANT_PORT):$(ASSISTANT_PORT) \
		--env-file .env \
		--name $(DOCKER_IMAGE) \
		-it \
		$(DOCKER_IMAGE)

# Clean up Docker resources
.PHONY: clean
clean:
	@echo "Cleaning up Docker resources..."
	-docker stop $(DOCKER_IMAGE) 2>/dev/null || true
	-docker rm $(DOCKER_IMAGE) 2>/dev/null || true
	-docker rmi $(DOCKER_IMAGE) 2>/dev/null || true

# Install development dependencies
.PHONY: dev-setup
dev-setup:
	UV_SYSTEM_PYTHON=1 uv pip install --editable ".[dev]"
