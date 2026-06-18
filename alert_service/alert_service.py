import asyncio
import logging
import time
from threading import Thread
from typing import Optional

import config
import pykeybasebot.types.chat1 as chat1
import redis
import requests
from pykeybasebot import Bot

from shared.alert_group_store import AlertGroup, AlertGroupStore
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
alert_group_store = AlertGroupStore(redis_client)


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


def issue_summary(issue: Issue) -> str:
    """Return a compact summary for grouped messages."""
    lines = []
    for line in issue.message.splitlines():
        line = line.strip()
        if not line:
            continue
        if issue.group_type == "node" and line.startswith("Node:"):
            continue
        lines.append(line)
    summary = " ".join(lines)
    return summary.replace("⚠️ ", "").replace("✅ ", "")


def pluralize_issue(count: int) -> str:
    return "issue" if count == 1 else "issues"


def visible_active_issues(issues: list[Issue]) -> list[Issue]:
    """Return active issues after applying suppression rules."""
    active_issues = [issue for issue in issues if not issue.resolved]
    if not active_issues:
        return []

    group_type = active_issues[0].group_type
    node_state_issues = [
        issue for issue in active_issues if issue.issue_type == "node_state"
    ]
    if group_type == "node" and node_state_issues:
        return sorted(node_state_issues, key=lambda issue: issue.id)

    return sorted(active_issues, key=lambda issue: issue.id)


def group_fingerprint(issues: list[Issue]) -> str:
    """Build a stable fingerprint for the visible active issue set."""
    return "|".join(f"{issue.issue_type}:{issue.id}" for issue in issues)


def should_send_active_group(
    group: AlertGroup, fingerprint: str, current_timestamp: int
) -> bool:
    """Decide whether an active group notification is due."""
    if group.last_alert == 0:
        return current_timestamp - group.first_seen >= config.GROUP_WAIT

    if fingerprint != group.last_fingerprint:
        return current_timestamp - group.last_alert >= config.GROUP_INTERVAL

    return current_timestamp - group.last_alert >= config.REPEAT_INTERVAL


def build_active_group_message(
    active_issues: list[Issue], resolved_issues: Optional[list[Issue]] = None
) -> str:
    """Build a grouped message for active visible issues."""
    first_issue = active_issues[0]
    count = len(active_issues)

    if first_issue.group_type == "node" and first_issue.issue_type == "node_state":
        return f"⚠️ BrightID node is down\nNode: {first_issue.group_name}"

    if first_issue.group_type == "node":
        header = (
            f"⚠️ BrightID node has {count} active {pluralize_issue(count)}\n"
            f"Node: {first_issue.group_name}"
        )
    elif first_issue.group_type == "apps":
        header = f"⚠️ BrightID apps have {count} active {pluralize_issue(count)}"
    else:
        header = f"⚠️ BrightID system has {count} active {pluralize_issue(count)}"

    sections = []
    if resolved_issues:
        resolved_lines = "\n".join(
            f"- {issue_summary(issue)}"
            for issue in sorted(resolved_issues, key=lambda issue: issue.id)
        )
        sections.append(f"Resolved:\n{resolved_lines}")

    active_lines = "\n".join(f"- {issue_summary(issue)}" for issue in active_issues)
    sections.append(f"Active:\n{active_lines}")

    oldest_started_at = min(issue.started_at for issue in active_issues)
    return (
        f"{header}\n\n" + "\n\n".join(sections) + f"\n\n{how_long(oldest_started_at)}"
    )


def build_resolved_group_message(group_id: str, issues: list[Issue]) -> str:
    """Build a simple full-recovery message for a group."""
    issue = issues[0]
    if issue.group_type == "node":
        return f"✅ BrightID node issues resolved\nNode: {issue.group_name}"
    if issue.group_type == "apps":
        return "✅ BrightID apps issues resolved"
    if issue.group_type == "system":
        return "✅ BrightID system issues resolved"
    return f"✅ BrightID alert group resolved\nGroup: {group_id}"


def delete_issues(issues: list[Issue]) -> None:
    for issue in issues:
        delete_issue(issue.id)


def handle_issue_group(group_id: str, issues: list[Issue]) -> None:
    """Check and process grouped issues using group-level timing."""
    group = alert_group_store.get_or_create_group(
        group_id, first_seen=min(issue.started_at for issue in issues)
    )
    current_timestamp = int(time.time())
    active_issues = visible_active_issues(issues)
    resolved_issues = [issue for issue in issues if issue.resolved]

    if not active_issues:
        if group.last_alert == 0:
            delete_issues(issues)
            alert_group_store.delete_group(group_id)
            return

        if send_alerts(build_resolved_group_message(group_id, issues)):
            delete_issues(issues)
            alert_group_store.delete_group(group_id)
        return

    fingerprint = group_fingerprint(active_issues)
    if not should_send_active_group(group, fingerprint, current_timestamp):
        return

    if send_alerts(build_active_group_message(active_issues, resolved_issues)):
        alert_group_store.update_group_state(
            group_id,
            current_timestamp,
            group.alert_number + 1,
            fingerprint,
        )
        delete_issues(resolved_issues)


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


def main() -> None:
    """Main function to check and process all issues."""
    while True:
        try:
            issues = fetch_issues()
            grouped_issues = group_issues_by_group_id(issues)
            for group_id, issues_group in grouped_issues.items():
                handle_issue_group(group_id, issues_group)
            update_health_status()
        except Exception as e:
            logging.error(f"Error in alert_service: {e}")
        time.sleep(config.CHECK_INTERVAL * 2)


if __name__ == "__main__":
    logging.info("Starting Alert Service...")
    alert_thread = Thread(target=main)
    alert_thread.start()
