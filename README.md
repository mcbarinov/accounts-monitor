# Accounts Monitor

A multi-blockchain wallet monitoring application that tracks account balances and domain names across different blockchain networks. Supports automated monitoring, historical data storage, and web interface for management.

## Supported Blockchains

- **EVM-based chains** (Ethereum and compatible) - native tokens and ERC20
- **Solana** - SOL and SPL tokens  
- **Aptos** - APT and other tokens
- **StarkNet** - tokens (requires token address)

## Key Features

### 🔍 Balance Monitoring
- Automated periodic balance checking with configurable interval (default 15 minutes)
- Support for native tokens and custom tokens on each blockchain
- Parallel processing with configurable worker limits
- Proxy support for requests
- RPC monitoring with response time tracking

### 🌐 Domain Name Resolution
- ENS (Ethereum Name Service) for EVM chains
- ANS (Aptos Name Service) for Aptos
- StarkNet ID for StarkNet
- Automated periodic name checking

### 👥 Group Management
- Organize accounts into groups by network type
- Track multiple accounts and coins per group
- Add notes for groups and individual accounts
- Import/export groups via TOML files

### 📊 Historical Data
- Create snapshots of group balances and names
- Compare historical data to track changes
- Automatic cleanup of old monitoring data (3-hour retention)

## Technology Stack

- **Backend**: Python 3.13, FastAPI
- **Database**: MongoDB
- **Frontend**: Jinja2 templates
- **Task Scheduling**: Built-in scheduler
- **Blockchain Libraries**: mm-base6, mm-eth, mm-sol, mm-apt, mm-strk
- **Deployment**: Docker, Docker Compose
- **Development**: UV package manager, Just task runner

## Installation and Setup

### Requirements

- Python 3.13+
- MongoDB
- UV package manager
- Just task runner (optional)

### Quick Start with Docker

1. Clone the repository:
```bash
git clone <repository-url>
cd accounts-monitor
```

2. Create `.env` file:
```bash
APP_NAME=accounts-monitor
DOCKER_REGISTRY=your-registry
ACCESS_TOKEN=your-secure-token
```

3. Run with Docker Compose:
```bash
just docker-compose
# or
cd docker && docker compose up --build
```

Application will be available at `http://localhost:3000`

### Local Development

1. Install dependencies:
```bash
uv sync --all-extras
```

2. Set up MongoDB and create `.env` file with appropriate settings

3. Run in development mode:
```bash
just dev
```

## Configuration

### Environment Variables

- `APP_NAME` - application name
- `DATABASE_URL` - MongoDB connection URL
- `DATA_DIR` - data directory
- `DOMAIN` - application domain
- `ACCESS_TOKEN` - access token
- `DEBUG` - debug mode
- `USE_HTTPS` - use HTTPS

### Application Settings

Main settings are located in `src/app/config.py`:

- `mm_node_checker` - URL for RPC node checking
- `proxies_url` - URL for proxy retrieval
- `round_ndigits` - decimal places for rounding (default 5)
- `limit_network_workers` - parallel requests limit per network (20)
- `limit_naming_workers` - parallel requests limit per naming service (20)
- `check_balance_interval` - balance check interval in minutes (15)
- `check_name_interval` - name check interval in minutes (15)

## API

### Main Endpoints

- `GET /` - home page
- `GET /bot` - bot management
- `GET /groups` - group management
- `GET /history` - history view
- `GET /networks` - network management
- `GET /coins` - token management
- `GET /rpc_monitoring` - RPC monitoring

### REST API

- `GET /api/groups` - list groups
- `POST /api/groups` - create group
- `GET /api/balances` - account balances
- `GET /api/names` - account names
- `GET /api/history` - historical data

## Development Commands

```bash
# Code formatting
just format

# Linting
just lint

# Tests
just test

# Security audit
just audit

# Build
just build

# Clean
just clean

# Docker build
just docker-build

# Publish
just publish
```

## Architecture

### Services

- **BalanceService** - balance checking across all blockchains
- **NameService** - blockchain domain name resolution
- **GroupService** - account group management and aggregations
- **HistoryService** - creating and comparing historical snapshots
- **NetworkService** - RPC URL management and network monitoring
- **CoinService** - token/coin configuration management
- **ProxyService** - proxy rotation
- **BotService** - monitoring state control

### Task Scheduler

The application uses a built-in scheduler for automated tasks:

- Balance checking every 2 seconds for each network
- Name checking every 2 seconds for each naming service
- mm-node-checker update every 30 seconds
- Proxy update every 60 seconds

## Deployment

### With Ansible

The project includes Ansible configuration for automated deployment:

```bash
cd ansible
ansible-playbook -i hosts.yml playbook.yml
```

### Docker Image

Build Docker image:

```bash
just docker-build
```

Upload to registry:

```bash
just docker-upload
```

## License

This project is intended for legitimate cryptocurrency portfolio monitoring. Use for illegal purposes is prohibited.
