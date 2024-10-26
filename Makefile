# Makefile for running the assistant and setting up environment variables

# Default target
.PHONY: all
all: setup run

# Setup environment variables
.PHONY: setup
setup:
	@if [ ! -f .env ]; then \
		touch .env; \
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


# Run the assistant
.PHONY: run
run:
	docker build -t assistant . && docker run -it --rm --env-file .env assistant


# Clean up Docker images and artifacts
.PHONY: clean
clean:
	@echo "Cleaning up Docker images and artifacts..."
	-docker stop assistant 2>/dev/null || true
	-docker rm assistant 2>/dev/null || true
	-docker rmi assistant 2>/dev/null || true
	@if [ $$? -eq 0 ]; then \
		echo "Successfully cleaned up Docker images and artifacts."; \
	elif [ $$? -eq 1 ]; then \
		echo "No Docker images or containers found to clean up."; \
	else \
		echo "An error occurred during cleanup."; \
	fi
