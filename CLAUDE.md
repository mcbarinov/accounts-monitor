# Claude Development Guidelines

This document contains specific guidelines and rules for Claude when working on this project.

## Language Rules

1. **Always write in English** - All code, comments, documentation, commit messages, and communication should be in English only.

## Project Context

This is a multi-blockchain accounts monitoring application that tracks wallet balances and domain names across:
- EVM-based chains (Ethereum and compatible)
- Solana
- Aptos  
- StarkNet

## Development Commands

When working on this project, use these commands for quality assurance:

```bash
# Format code
just format

# Run linting and type checking
just lint

# Run tests
just test

# Security audit
just audit

# Full build (includes all above)
just build

# Development mode
just dev
```

## Architecture Notes

- Built with Python 3.13 and FastAPI
- Uses MongoDB for data storage
- Modular service architecture with separate services for balance checking, name resolution, group management, etc.
- Built-in task scheduler for automated monitoring
- Web UI with Jinja2 templates
- Docker deployment ready

## Code Standards

- Follow the existing code style and patterns
- Use the mm-base6 framework conventions
- All new features should include appropriate error handling
- Use type hints consistently
- Follow the linting rules defined in pyproject.toml
