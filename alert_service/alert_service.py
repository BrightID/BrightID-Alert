import asyncio
import logging
import time
from threading import Thread

import config
import pykeybasebot.types.chat1 as chat1
import redis
import requests
from pykeybasebot import Bot

from shared.issue_store import Issue, IssueStore

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Initialize Redis
redis_client = redis.Redis(
    host=config.REDIS_HOST, port=config.REDIS_PORT, decode_responses=True
)
issue_store = IssueStore(redis_client)


def fetch_issues() -> list[Issue]:
    """Fetch all issues from Redis."""
    try:
        return issue_store.fetch_issues()
    except Exception as e:
        logging.error(f"Failed to fetch issues from Redis: {e}")
        return []


def group_issues_by_group_id(issues: list[Issue]) -> dict[str, list[Issue]]:
    """Group issues by their alert group id."""
    grouped_issues = {}
    for issue in issues:
        grouped_issues.setdefault(issue.group_id, []).append(issue)
    return grouped_issues


def update_issue(issue_id: str, last_alert: int, alert_number: int) -> None:
    """Updates the last alert time and alert count for a specific issue in Redis."""
    issue_store.update_alert_state(issue_id, last_alert, alert_number)


def delete_issue(issue_id: str) -> None:
    """Deletes a specific issue from Redis."""
    issue_store.delete_issue(issue_id)


def update_health_status() -> None:
    """Update last check timestamp in Redis."""
    redis_client.set("health:alert_service", int(time.time()))


def how_long(ts: int) -> str:
    """Calculate and format a human-readable duration since the given timestamp."""
    duration = int(time.time() - ts)
    intervals = [(24 * 60 * 60, "day", "days"), (60 * 60, "hour", "hours")]
    for seconds, singular, plural in intervals:
        if duration >= seconds:
            count = duration // seconds
            unit = singular if count == 1 else plural
            return f"since {count} {unit} ago"
    return "since a few minutes ago"


class KeybaseBot:
    """Singleton wrapper for the Keybase bot instance."""

    _instance = None

    @staticmethod
    def get_instance():
        if KeybaseBot._instance is None:
            KeybaseBot._instance = Bot(
                username=config.KEYBASE_BOT_USERNAME,
                paperkey=config.KEYBASE_BOT_KEY,
                handler=None,
            )
        return KeybaseBot._instance


def send_alerts(message: str) -> bool:
    """Sends an alert via Keybase and Telegram."""
    keybase_sent = send_keybase_alert(message)
    telegram_sent = send_telegram_alert(message)
    return bool(keybase_sent or telegram_sent)


def send_keybase_alert(message: str) -> bool:
    """Sends an alert via Keybase."""
    try:
        bot = KeybaseBot.get_instance()
        channel = chat1.ChatChannel(**config.KEYBASE_BOT_CHANNEL)
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(bot.chat.send(channel, message))
        return True
    except Exception as e:
        logging.error(f"Keybase error: {e}")
        return False


def send_telegram_alert(message: str) -> bool:
    """Sends an alert via Telegram."""
    try:
        request_data = {"chat_id": config.TELEGRAM_BOT_CHANNEL, "text": message}
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_KEY}/sendMessage"
        response = requests.post(
            url,
            json=request_data,
            headers={"Content-Type": "application/json"},
            timeout=config.HTTP_TIMEOUT,
        )
        response.raise_for_status()
        return True
    except Exception as e:
        logging.error(f"Telegram error: {e}")
        return False


def handle_resolved_issue(issue: Issue) -> None:
    """Handle resolved issues by sending a message and deleting them."""
    if send_alerts(issue.message):
        delete_issue(issue.id)


def handle_first_alert_issue(issue: Issue):
    """Handle new issues by sending a message."""
    if send_alerts(issue.message):
        update_issue(issue.id, int(time.time()), issue.alert_number + 1)


def handle_unresolved_issue(issue: Issue) -> None:
    """Handle unresolved issues by sending a message."""
    current_timestamp = int(time.time())
    next_interval = min(
        config.MIN_MSG_INTERVAL * 2 ** (issue.alert_number - 1),
        config.MAX_MSG_INTERVAL,
    )
    next_alert = issue.last_alert + next_interval
    if next_alert <= current_timestamp:
        message = f"{issue.message}\n{how_long(issue.started_at)}"
        if send_alerts(message):
            update_issue(issue.id, current_timestamp, issue.alert_number + 1)


def handle_issue(issue: Issue) -> None:
    """Check and process an issue."""
    if issue.resolved:
        handle_resolved_issue(issue)
    elif issue.last_alert == 0:
        handle_first_alert_issue(issue)
    else:
        handle_unresolved_issue(issue)


def main() -> None:
    """Main function to check and process all issues."""
    while True:
        try:
            issues = fetch_issues()
            grouped_issues = group_issues_by_group_id(issues)
            for issues_group in grouped_issues.values():
                for issue in issues_group:
                    handle_issue(issue)
            update_health_status()
        except Exception as e:
            logging.error(f"Error in alert_service: {e}")
        time.sleep(config.CHECK_INTERVAL * 2)


if __name__ == "__main__":
    logging.info("Starting Alert Service...")
    alert_thread = Thread(target=main)
    alert_thread.start()
