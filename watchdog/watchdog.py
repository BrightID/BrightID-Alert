import logging
import time

import config
import docker
import redis

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Initialize Redis
redis_client = redis.Redis(
    host=config.REDIS_HOST, port=config.REDIS_PORT, decode_responses=True
)

SERVICES = ["monitor_service", "alert_service"]
docker_client = docker.from_env()
watchdog_start_time = int(time.time())


def get_last_check(service_name: str) -> int:
    """Retrieve last check timestamp from Redis."""
    timestamp = redis_client.get(f"health:{service_name}")
    return int(timestamp) if timestamp else 0


def restart_service(service_name: str):
    """Restart the given service."""
    try:
        container = docker_client.containers.get(f"brightid-alert-{service_name}-1")
        logging.warning(f"{service_name} is unresponsive! Restarting...")
        container.restart()
        logging.info(f"{service_name} restarted successfully.")
    except Exception as e:
        logging.error(f"Failed to restart {service_name}: {e}")


def watchdog():
    """Main loop checking service health."""
    while True:
        current_time = int(time.time())
        for service in SERVICES:
            # Skip check if we are still in the startup grace period
            if current_time - watchdog_start_time < config.WATCHDOG_THRESHOLD:
                continue

            last_check = get_last_check(service)
            if current_time - last_check > config.WATCHDOG_THRESHOLD:
                restart_service(service)
        time.sleep(config.CHECK_INTERVAL * 3)


if __name__ == "__main__":
    logging.info("Starting Watchdog Service...")
    watchdog()
