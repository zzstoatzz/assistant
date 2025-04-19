# Check for uv installation
check-uv:
    #!/usr/bin/env sh
    if ! command -v uv >/dev/null 2>&1; then
        echo "uv is not installed. Please install it using one of these methods:"
        echo "• curl -LsSf https://astral.sh/uv/install.sh | sh  # For macOS/Linux"
        echo "• pip install uv  # Using pip"
        echo "For more information, visit: https://github.com/astral-sh/uv"
        exit 1
    fi

# Load environment variables
set dotenv-load

# Default values
dev-port := env_var_or_default("DEV_PORT", "8001")
host := env_var_or_default("HOST", "localhost")
mcp-port := env_var_or_default("MCP_PORT", "8002")
docker-image := "assistant"
dockerfile := "app/Dockerfile.main"
assistant-port := env_var_or_default("ASSISTANT_PORT", "8000")

# List available commands
default:
    @just --list

# Setup environment and check dependencies
setup: check-uv check-env
    @echo "✨ Setup complete"

# Check environment configuration
check-env: check-uv
    @uv run scripts/configure.py

# Run development server with hot reload
dev: check-uv
    uv run --all-extras fastapi dev app/main.py --host {{host}} --port {{dev-port}}

# Run MCP server in development mode
mcp-dev: check-uv
    @echo "Starting MCP server in development mode..."
    uv run fastmcp dev mcp/server.py

# Run both development servers
dev-all: check-uv
    @echo "Starting all development servers..."
    just dev & just mcp-dev

# Build and run in production mode
run: check-uv check-env
    docker build -t {{docker-image}} -f {{dockerfile}} .
    docker run --rm \
        -p {{assistant-port}}:{{assistant-port}} \
        --env-file .env \
        --name {{docker-image}} \
        -it \
        {{docker-image}}

# Clean up Docker resources
clean:
    @echo "Cleaning up Docker resources..."
    -docker stop {{docker-image}} 2>/dev/null || true
    -docker rm {{docker-image}} 2>/dev/null || true
    -docker rmi {{docker-image}} 2>/dev/null || true

# Install development dependencies
dev-setup: check-uv
    UV_SYSTEM_PYTHON=1 uv pip install --editable ".[dev]"

# Run tests
test: check-uv
    uv run --with ".[dev]" pytest tests/ -v --tb=short --show-capture=no

# Run tests with coverage
test-cov: check-uv
    uv run --with ".[dev]" pytest tests/ -v --tb=short --cov=assistant --cov=app --cov-report=term-missing

# Run all setup and deployment steps
all: setup run

# Install MCP dependencies
mcp-setup: check-uv
    @echo "Installing MCP dependencies..."
    cd mcp && uv pip install -r requirements.txt
