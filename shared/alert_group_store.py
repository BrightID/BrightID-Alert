import logging
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class AlertGroup:
    group_id: str
    first_seen: int
    last_alert: int = 0
    alert_number: int = 0
    last_fingerprint: str = ""

    def to_redis(self) -> dict:
        return {
            "group_id": self.group_id,
            "first_seen": self.first_seen,
            "last_alert": self.last_alert,
            "alert_number": self.alert_number,
            "last_fingerprint": self.last_fingerprint,
        }

    @classmethod
    def from_redis(cls, group_data: dict) -> Optional["AlertGroup"]:
        if "group_id" not in group_data:
            logging.warning(
                f"Skipping malformed alert group data: {group_data}. "
                "'group_id' field is missing."
            )
            return None

        try:
            return cls(
                group_id=group_data["group_id"],
                first_seen=int(group_data["first_seen"]),
                last_alert=int(group_data["last_alert"]),
                alert_number=int(group_data["alert_number"]),
                last_fingerprint=group_data["last_fingerprint"],
            )
        except (ValueError, KeyError) as e:
            logging.error(f"Error parsing alert group data {group_data}: {e}")
            return None


class AlertGroupStore:
    def __init__(self, redis_client):
        self.redis_client = redis_client

    @staticmethod
    def group_key(group_id: str) -> str:
        return f"alert_group:{group_id}"

    def get_or_create_group(self, group_id: str) -> AlertGroup:
        group = self.get_group(group_id)
        if group:
            return group

        group = AlertGroup(group_id=group_id, first_seen=int(time.time()))
        self.redis_client.hset(self.group_key(group_id), mapping=group.to_redis())
        return group

    def get_group(self, group_id: str) -> Optional[AlertGroup]:
        group_data = self.redis_client.hgetall(self.group_key(group_id))
        return AlertGroup.from_redis(group_data) if group_data else None

    def update_group_state(
        self,
        group_id: str,
        last_alert: int,
        alert_number: int,
        last_fingerprint: str,
    ) -> None:
        self.redis_client.hset(
            self.group_key(group_id),
            mapping={
                "last_alert": last_alert,
                "alert_number": alert_number,
                "last_fingerprint": last_fingerprint,
            },
        )

    def delete_group(self, group_id: str) -> None:
        self.redis_client.delete(self.group_key(group_id))
