# BrightID Alert System

## Overview
The BrightID Alert System is a monitoring and alerting service designed to track system health and send alerts via Keybase and Telegram. It consists of three main services:

- **Monitor Service**: Periodically checks the status of critical components.
- **Alert Service**: Sends alerts to Keybase and Telegram when an issue is detected.
- **Watchdog Service**: Ensures that the Monitor and Alert services are running and restarts them if necessary.

The system uses Redis for storing status updates and inter-service communication.

---

## Requirements
Before running the system, ensure you have:

- Docker & Docker Compose installed
- A Keybase bot account
- A Telegram bot account

---

## Installation & Setup

### 1. Clone the Repository
```sh
git clone https://github.com/BrightID/BrightID-Alert.git
cd BrightID-Alert
```

### 2. Configure Environment Variables
Create a `config.env` file based on `config.env.example` and update it with your settings:
```sh
cp config.env.example config.env
nano config.env  # Update values accordingly
```

### 3. Build and Start the Services
```sh
docker compose up --build -d
```

This will build and start all services in detached mode.

### 4. Check Logs
```sh
docker compose logs -f
```

### 5. Stop the Services
To stop the running services:
```sh
docker compose down
```

