# `assistant`

A sandboxed AI assistant for software development.

## Overview

1. Understand your requirements through conversation
2. Create a detailed design document
3. Set up a project structure
4. Implement and iterate on the solution

## Prerequisites

- Docker
- OpenAI API key
- Prefect API key and URL

## Quick Start

```bash
# Set up environment variables and run the assistant
make

# Clean up assistant image
make clean
```

## Project Structure

```

.
├── Dockerfile
├── Makefile
├── instructions.md
└── main.py

```

## Environment Variables

The following environment variables are required and will be prompted for during setup:

- `OPENAI_API_KEY`
- `PREFECT_API_KEY`
- `PREFECT_API_URL`
