import logging
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class Issue:
    id: str
    group_id: str
    group_type: str
    group_name: str
    issue_type: str
    severity: str
    resolved: bool
    message: str
    started_at: int
    updated_at: int

    def to_redis(self) -> dict:
        return {
            "id": self.id,
            "group_id": self.group_id,
            "group_type": self.group_type,
            "group_name": self.group_name,
            "issue_type": self.issue_type,
            "severity": self.severity,
            "resolved": int(self.resolved),
            "message": self.message,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_redis(cls, issue_data: dict) -> Optional["Issue"]:
        if "id" not in issue_data:
            logging.warning(
                f"Skipping malformed issue data: {issue_data}. 'id' field is missing."
            )
            return None

        try:
            return cls(
                id=issue_data["id"],
                group_id=issue_data["group_id"],
                group_type=issue_data["group_type"],
                group_name=issue_data["group_name"],
                issue_type=issue_data["issue_type"],
                severity=issue_data["severity"],
                resolved=bool(int(issue_data["resolved"])),
                message=issue_data["message"],
                started_at=int(issue_data["started_at"]),
                updated_at=int(issue_data["updated_at"]),
            )
        except (ValueError, KeyError) as e:
            logging.error(f"Error parsing issue data {issue_data}: {e}")
            return None


class IssueStore:
    def __init__(self, redis_client):
        self.redis_client = redis_client

    @staticmethod
    def issue_key(issue_id: str) -> str:
        return f"issue:{issue_id}"

    def insert_new_issue(
        self,
        issue_id: str,
        message: str,
        group_id: str,
        group_type: str,
        group_name: str,
        issue_type: str,
        severity: str,
    ) -> None:
        now = int(time.time())
        issue = Issue(
            id=issue_id,
            group_id=group_id,
            group_type=group_type,
            group_name=group_name,
            issue_type=issue_type,
            severity=severity,
            resolved=False,
            message=message,
            started_at=now,
            updated_at=now,
        )
        self.redis_client.hset(self.issue_key(issue_id), mapping=issue.to_redis())

    def issue_exists(self, issue_id: str) -> bool:
        return bool(self.redis_client.exists(self.issue_key(issue_id)))

    def mark_issue_resolved(self, issue_id: str, message: str) -> None:
        self.redis_client.hset(
            self.issue_key(issue_id),
            mapping={"resolved": 1, "message": message, "updated_at": int(time.time())},
        )

    def fetch_issues(self) -> list[Issue]:
        issues = []
        for key in self.redis_client.scan_iter("issue:*"):
            issue = Issue.from_redis(self.redis_client.hgetall(key))
            if issue:
                issues.append(issue)
        return issues

    def delete_issue(self, issue_id: str) -> None:
        self.redis_client.delete(self.issue_key(issue_id))
