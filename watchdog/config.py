import os

REDIS_HOST = os.environ["REDIS_HOST"]
REDIS_PORT = int(os.environ["REDIS_PORT"])
CHECK_INTERVAL = int(os.environ["CHECK_INTERVAL"])
WATCHDOG_THRESHOLD = int(os.environ["WATCHDOG_THRESHOLD"])
