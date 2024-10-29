# Makefile for running the assistant and setting up environment variables

# Configuration
DOCKER_IMAGE := assistant
DOCKERFILE := app/Dockerfile.main

# Load environment variables
include .env
export

# Development port with a different default than production
DEV_PORT ?= 8001
HOST ?= localhost

.PHONY: all
all: setup run

.PHONY: setup
setup: check-env
	@echo "Setting up the environment..."
	@if [ ! -f .env ]; then \
		touch .env; \
	fi
	@if ! grep -q ASSISTANT_PORT .env; then \
		echo "ASSISTANT_PORT=8000" >> .env; \
	fi
	@if ! grep -q OPENAI_API_KEY .env; then \
		read -p "Enter your OpenAI API key: " openai_key; \
		echo "OPENAI_API_KEY=$$openai_key" >> .env; \
	fi
	@if ! grep -q PREFECT_API_KEY .env; then \
		read -p "Enter your Prefect API key: " prefect_key; \
		echo "PREFECT_API_KEY=$$prefect_key" >> .env; \
	fi
	@if ! grep -q PREFECT_API_URL .env; then \
		read -p "Enter your Prefect API URL: " prefect_url; \
		echo "PREFECT_API_URL=$$prefect_url" >> .env; \
	fi
	@echo "Setup complete. Required environment variables are present in .env file."

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

check-env:
	@echo "Checking environment variables..."
	@[ -n "$(OPENAI_API_KEY)" ] || (echo "OPENAI_API_KEY is not set" && exit 1)
	@[ -n "$(PREFECT_API_KEY)" ] || (echo "PREFECT_API_KEY is not set" && exit 1)
	@[ -n "$(PREFECT_API_URL)" ] || (echo "PREFECT_API_URL is not set" && exit 1)
	@[ -n "$(HUMANLAYER_API_KEY)" ] || (echo "HUMANLAYER_API_KEY is not set" && exit 1)
	@[ -n "$(GITHUB_TOKEN)" ] || (echo "GITHUB_TOKEN is not set" && exit 1)
	@[ -n "$(SLACK_BOT_TOKEN)" ] || (echo "SLACK_BOT_TOKEN is not set" && exit 1)
	@echo "All required environment variables are set."
