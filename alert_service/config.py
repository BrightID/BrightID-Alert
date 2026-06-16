import json
import os


def get_json_env(name: str) -> dict:
    """Read an environment variable that must contain a JSON object."""
    try:
        value = os.environ[name]
    except KeyError as e:
        raise RuntimeError(f"{name} is required") from e

    try:
        data = json.loads(value)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"{name} must be valid JSON: {e}") from e

    if not isinstance(data, dict):
        raise RuntimeError(f"{name} must be a JSON object")
    return data


KEYBASE_BOT_KEY = os.environ["KEYBASE_BOT_KEY"]
KEYBASE_BOT_USERNAME = os.environ["KEYBASE_BOT_USERNAME"]
KEYBASE_BOT_CHANNEL = get_json_env("KEYBASE_BOT_CHANNEL")
TELEGRAM_BOT_KEY = os.environ["TELEGRAM_BOT_KEY"]
TELEGRAM_BOT_CHANNEL = os.environ["TELEGRAM_BOT_CHANNEL"]
CHECK_INTERVAL = int(os.environ["CHECK_INTERVAL"])
MAX_MSG_INTERVAL = int(os.environ["MAX_MSG_INTERVAL"])
MIN_MSG_INTERVAL = int(os.environ["MIN_MSG_INTERVAL"])
MAX_RETRIES = int(os.environ["MAX_RETRIES"])
HTTP_CONNECT_TIMEOUT = int(os.environ["HTTP_CONNECT_TIMEOUT"])
HTTP_READ_TIMEOUT = int(os.environ["HTTP_READ_TIMEOUT"])
HTTP_TIMEOUT = (HTTP_CONNECT_TIMEOUT, HTTP_READ_TIMEOUT)
REDIS_HOST = os.environ["REDIS_HOST"]
REDIS_PORT = int(os.environ["REDIS_PORT"])
