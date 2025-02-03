import hashlib
import logging
import time
from datetime import datetime
from threading import Thread
from typing import Any, Optional

import config
import redis
import requests
import xmltodict
from messages import ISSUE_MESSAGES

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Initialize Redis
redis_client = redis.Redis(
    host=config.REDIS_HOST, port=config.REDIS_PORT, decode_responses=True
)


def insert_new_issue(issue_id: str, message: str) -> None:
    """Insert or update an issue in Redis using a hash structure."""
    issue = {
        "id": issue_id,
        "resolved": int(False),
        "message": message,
        "started_at": int(time.time()),
        "last_alert": 0,
        "alert_number": 0,
    }
    redis_client.hset(f"issue:{issue_id}", mapping=issue)


def is_issue_exists(issue_id: str) -> bool:
    """Check if an issue exists in Redis."""
    return bool(redis_client.exists(f"issue:{issue_id}"))


def mark_issue_resolved(issue_id: str, message: str) -> None:
    """Mark an issue as resolved in Redis using a hash structure."""
    redis_client.hset(f"issue:{issue_id}", mapping={"resolved": 1, "message": message})


def update_health_status() -> None:
    """Update last check timestamp in Redis."""
    redis_client.set("health:monitor_service", int(time.time()))


def generate_issue_id(part1: str, part2: str) -> str:
    """Generate a unique hash for an issue."""
    message = f"{part1}|{part2}".encode("utf-8")
    return hashlib.sha256(message).hexdigest()


def send_rpc_request(method: str, params: list[Any]) -> Optional[Any]:
    """Send an RPC request to IDChain."""
    request_data = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1,
    }
    headers = {"Content-Type": "application/json", "Cache-Control": "no-cache"}
    response = send_post_request(config.IDCHAIN_RPC_URL, request_data, headers)
    if response:
        try:
            return response.json().get("result")
        except ValueError:
            logging.error(
                f"Invalid JSON response from {config.IDCHAIN_RPC_URL}: {response.text}"
            )
    return None


def send_post_request(
    url: str,
    request_data: Optional[dict[str, Any]] = None,
    headers: Optional[dict[str, str]] = None,
) -> Optional[requests.Response]:
    """Send an HTTP POST request with retries."""
    for attempt in range(config.MAX_RETRIES):
        try:
            response = requests.post(url, json=request_data, headers=headers)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException:
            time.sleep(2 * attempt)
    # logging.error(f"POST request to {url} failed after {config.MAX_RETRIES} attempts.")
    return None


def send_get_request(
    url: str,
    params: Optional[dict[str, Any]] = None,
    headers: Optional[dict[str, str]] = None,
) -> Optional[requests.Response]:
    """Send an HTTP GET request with retries."""
    for attempt in range(config.MAX_RETRIES):
        try:
            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException:
            time.sleep(2 * attempt)
    # logging.error(f"GET request to {url} failed after {config.MAX_RETRIES} attempts.")
    return None


def get_eidi_balance(addr: str) -> Optional[float]:
    """Get the Eidi balance of an Ethereum address."""
    balance = send_rpc_request(method="eth_getBalance", params=[addr, "latest"])
    return int(balance, 16) / 10**18 if balance else None


def get_idchain_block_number() -> Optional[int]:
    """Get IDChain block number."""
    block_number_hex = send_rpc_request(
        method="eth_blockNumber",
        params=[],
    )
    return int(block_number_hex, 16) if block_number_hex else None


def get_transaction_count(address: str) -> Optional[int]:
    """Get IDChain block number."""
    transaction_count = send_rpc_request(
        method="eth_getTransactionCount",
        params=[address, "pending"],
    )
    return int(transaction_count, 16) if transaction_count else None


def get_node_state(node_info: dict) -> Optional[dict]:
    """Retrieve the state of a node and manage issue tracking."""
    issue_id = generate_issue_id(node_info["url"], "node state")
    issue_exists = is_issue_exists(issue_id)
    response = send_get_request(node_info["url"])
    node_state = None
    if response:
        try:
            node_state = response.json()["data"]
        except ValueError:
            logging.error(f"Invalid JSON response from {node_info['url']}")

    if not node_state and not issue_exists:
        insert_new_issue(
            issue_id, ISSUE_MESSAGES["node_state_down"].format(node_info["url"])
        )
    elif node_state and issue_exists:
        mark_issue_resolved(
            issue_id, ISSUE_MESSAGES["node_state_resolved"].format(node_info["url"])
        )
    return node_state


def check_consensus_sender_balance(node_url: str, consensus_sender: str) -> None:
    """Check the Eidi balance of the consensus sender and manage issue tracking."""
    issue_id = generate_issue_id(node_url, "consensus sender eidi balance")
    issue_exists = is_issue_exists(issue_id)
    balance = get_eidi_balance(consensus_sender)
    if balance is None:
        logging.error(f"Get Eidi balance failed. {consensus_sender} not checked.")
        return

    low_balance = balance < config.BALANCE_BORDER
    if low_balance and not issue_exists:
        insert_new_issue(
            issue_id,
            ISSUE_MESSAGES["node_balance_low"].format(
                node_url, balance, config.BALANCE_BORDER
            ),
        )
    elif issue_exists and not low_balance:
        mark_issue_resolved(
            issue_id, ISSUE_MESSAGES["node_balance_resolved"].format(node_url)
        )


def check_consensus_receiver(
    node_url: str, last_processed_block: int, block_number: int
) -> None:
    """Check if the consensus receiver service is active and manage issue tracking."""
    issue_id = generate_issue_id(node_url, "consensus receiver service")
    issue_exists = is_issue_exists(issue_id)
    is_active = block_number - last_processed_block < config.RECEIVER_BORDER
    if not is_active and not issue_exists:
        insert_new_issue(
            issue_id, ISSUE_MESSAGES["receiver_service_down"].format(node_url)
        )
    elif is_active and issue_exists:
        mark_issue_resolved(
            issue_id, ISSUE_MESSAGES["receiver_service_resolved"].format(node_url)
        )


def check_scorer(node_url: str, verifications_block: int, block_number: int) -> None:
    """Check if the scorer service is active and manage issue tracking."""
    issue_id = generate_issue_id(node_url, "scorer service")
    issue_exists = is_issue_exists(issue_id)
    is_active = (
        block_number - verifications_block
        < config.SNAPSHOT_PERIOD + config.SCORER_BORDER
    )
    if not is_active and not issue_exists:
        insert_new_issue(
            issue_id, ISSUE_MESSAGES["scorer_service_down"].format(node_url)
        )
    elif is_active and issue_exists:
        mark_issue_resolved(
            issue_id, ISSUE_MESSAGES["scorer_service_resolved"].format(node_url)
        )


def check_consensus_sender(node_eth_signer: str, states: dict) -> None:
    """Check if the consensus sender service is active and manage issue tracking."""

    def is_incremental(numbers: list) -> bool:
        """Check if a list of numbers is non-decreasing."""
        return all(x <= y for x, y in zip(numbers, numbers[1:]))

    if len(states[node_eth_signer]) < 5:
        return

    node_state = states[node_eth_signer][-1]
    issue_id = generate_issue_id(node_state["url"], "consensus sender service")
    issue_exists = is_issue_exists(issue_id)
    initiated_operations = [state["initOp"] for state in states[node_eth_signer]]
    sender_transactions_counters = [
        state["senderTransactionCount"]
        for state in states[node_eth_signer]
        if state["senderTransactionCount"] is not None
    ]
    is_sender_transactions_count_increasing = is_incremental(
        sender_transactions_counters
    )
    is_initiated_operations_increasing = is_incremental(initiated_operations)

    # If initiated operations are increasing or constant while the first one is not 0 and sender transactions counter is not increasing
    service_down = (
        is_initiated_operations_increasing and initiated_operations[0] != 0
    ) and not is_sender_transactions_count_increasing
    if service_down and not issue_exists:
        insert_new_issue(
            issue_id, ISSUE_MESSAGES["sender_service_down"].format(node_state["url"])
        )
    elif not service_down and issue_exists:
        mark_issue_resolved(
            issue_id,
            ISSUE_MESSAGES["sender_service_resolved"].format(node_state["url"]),
        )


def check_profile_service(profile_service_url: str) -> None:
    """Check if the profile service is active and manage issue tracking."""
    issue_id = generate_issue_id(profile_service_url, "profile service")
    issue_exists = is_issue_exists(issue_id)
    response = send_get_request(profile_service_url)
    succeeded = response is not None and response.status_code == 200
    if not succeeded and not issue_exists:
        insert_new_issue(
            issue_id, ISSUE_MESSAGES["profile_service_down"].format(profile_service_url)
        )
    elif succeeded and issue_exists:
        mark_issue_resolved(
            issue_id,
            ISSUE_MESSAGES["profile_service_resolved"].format(profile_service_url),
        )


def check_node_version(last_version: str, node_state: dict) -> None:
    """Check if the node is running the latest version and manage issue tracking.."""
    issue_id = generate_issue_id(node_state["url"], "node version")
    issue_exists = is_issue_exists(issue_id)
    is_version_latest = node_state["version"] == last_version
    if not is_version_latest and not issue_exists:
        insert_new_issue(
            issue_id,
            ISSUE_MESSAGES["node_version_outdated"].format(
                node_state["url"], node_state["version"], last_version
            ),
        )
    elif is_version_latest and issue_exists:
        mark_issue_resolved(
            issue_id, ISSUE_MESSAGES["node_version_resolved"].format(node_state["url"])
        )


def check_apps_updater(
    node_url: str, apps_last_update_block: int, block_number: int
) -> None:
    """Check if the apps updater service is active and manage issue tracking."""
    issue_id = generate_issue_id(node_url, "apps updater service")
    issue_exists = is_issue_exists(issue_id)
    is_active = block_number - apps_last_update_block < config.APPS_UPDATE_BORDER
    if not is_active and not issue_exists:
        insert_new_issue(issue_id, ISSUE_MESSAGES["apps_updater_down"].format(node_url))
    elif is_active and issue_exists:
        mark_issue_resolved(
            issue_id, ISSUE_MESSAGES["apps_updater_resolved"].format(node_url)
        )


def check_sp_updater(
    node_url: str, sp_last_update_block: int, block_number: int
) -> None:
    """Check if the sp updater service is active and manage issue tracking."""
    issue_id = generate_issue_id(node_url, "sp updater service")
    issue_exists = is_issue_exists(issue_id)
    is_active = block_number - sp_last_update_block < config.SPONSORSHIPS_UPDATE_BORDER
    if not is_active and not issue_exists:
        insert_new_issue(issue_id, ISSUE_MESSAGES["sp_updater_down"].format(node_url))
    elif is_active and issue_exists:
        mark_issue_resolved(
            issue_id, ISSUE_MESSAGES["sp_updater_resolved"].format(node_url)
        )


def check_seed_groups_updater(
    node_url: str, seed_groups_last_update_block: int, block_number: int
) -> None:
    """Check if the seed groups updater service is active and manage issue tracking."""
    issue_id = generate_issue_id(node_url, "seed groups updater service")
    issue_exists = is_issue_exists(issue_id)
    is_active = (
        block_number - seed_groups_last_update_block < config.SEED_GROUPS_UPDATE_BORDER
    )
    if not is_active and not issue_exists:
        insert_new_issue(
            issue_id, ISSUE_MESSAGES["seed_groups_updater_down"].format(node_url)
        )
    elif is_active and issue_exists:
        mark_issue_resolved(
            issue_id, ISSUE_MESSAGES["seed_groups_updater_resolved"].format(node_url)
        )


def check_all_nodes_services(states: dict, active_nodes: list) -> None:
    """Perform health checks for all active nodes in the network."""
    try:
        last_version = states[config.NODE_ONE_ETH_SIGNER][-1]["version"]
    except (KeyError, IndexError, TypeError):
        last_version = None

    for node_eth_signer, node_states in states.items():
        if node_eth_signer not in active_nodes:
            continue

        node_state = node_states[-1]
        check_consensus_sender(node_eth_signer, states)
        check_consensus_sender_balance(
            node_state["url"], node_state["consensusSenderAddress"]
        )
        check_profile_service(node_state["profile_service_url"])
        check_consensus_receiver(
            node_state["url"],
            node_state["lastProcessedBlock"],
            node_state["stateBlock"],
        )
        check_scorer(
            node_state["url"],
            node_state["verificationsBlock"],
            node_state["stateBlock"],
        )
        check_apps_updater(
            node_state["url"],
            node_state["appsLastUpdateBlock"],
            node_state["stateBlock"],
        )
        check_sp_updater(
            node_state["url"],
            node_state["sponsorshipsLastUpdateBlock"],
            node_state["stateBlock"],
        )
        check_seed_groups_updater(
            node_state["url"],
            node_state["seedGroupsLastUpdateBlock"],
            node_state["stateBlock"],
        )
        if last_version:
            check_node_version(last_version, node_state)


def check_recovery_service() -> None:
    """Check the recovery service and handle issue tracking."""
    issue_id = generate_issue_id(config.NODE_ONE_URL, "recovery service")
    issue_exists = is_issue_exists(issue_id)
    response = send_get_request(config.RECOVERY_SERVICE_URL)
    succeeded = response is not None and response.status_code == 200
    if not succeeded and not issue_exists:
        insert_new_issue(issue_id, ISSUE_MESSAGES["recovery_service_down"])
    elif succeeded and issue_exists:
        mark_issue_resolved(issue_id, ISSUE_MESSAGES["recovery_service_resolved"])


def check_backup_service() -> None:
    """Check the backup service and handle issue tracking."""
    issue_id = generate_issue_id(config.NODE_ONE_URL, "backup service")
    issue_exists = is_issue_exists(issue_id)

    is_active = False
    response = send_get_request(config.BACKUPS_SERVICE_URL)
    if response is None or response.status_code != 200:
        logging.error("Backup service request failed.")

    else:
        try:
            data = xmltodict.parse(response.text)
            backups = data.get("ListBucketResult", {}).get("Contents", [])
            times = [
                b["LastModified"]
                for b in backups
                if b.get("Key", "").endswith(".tar.gz")
            ]
            if times:
                last_backup = datetime.strptime(
                    times[-1], "%Y-%m-%dT%H:%M:%S.%fZ"
                ).timestamp()
                is_active = (time.time() - last_backup) < config.BACKUP_BORDER
            else:
                logging.warning("No valid backup files found in backup service.")
        except Exception as e:
            logging.error(f"Error parsing backup service response: {e}")

    if not is_active and not issue_exists:
        insert_new_issue(issue_id, ISSUE_MESSAGES["backup_service_down"])
    elif is_active and issue_exists:
        mark_issue_resolved(issue_id, ISSUE_MESSAGES["backup_service_resolved"])


def check_apps_sp_balance() -> None:
    response = send_get_request(f"{config.NODE_ONE_URL}/apps")
    if not response:
        logging.error("Failed to fetch apps data. Apps SP checks aborted.")
        return

    try:
        apps = response.json()["data"]["apps"]
    except ValueError:
        logging.error("Failed to fetch apps data. Apps SP checks aborted.")
        return

    for app in apps:
        if app["assignedSponsorships"] == 0:
            continue

        issue_id = generate_issue_id(app["id"], "sp balance")
        issue_exists = is_issue_exists(issue_id)

        border = int(app["assignedSponsorships"] * 0.05)
        low_balance = app["unusedSponsorships"] < border
        if low_balance and not issue_exists:
            insert_new_issue(
                issue_id,
                ISSUE_MESSAGES["app_sp_balance_low"].format(
                    app["id"], app["unusedSponsorships"]
                ),
            )
        elif issue_exists and not low_balance:
            mark_issue_resolved(
                issue_id, ISSUE_MESSAGES["app_sp_balance_resolved"].format(app["id"])
            )


def update_nodes_states(states: dict) -> tuple[dict, list]:
    """Fetch the nodes state and updates the states."""
    active_nodes = []
    block_number = get_idchain_block_number()
    if block_number is None:
        logging.error("Failed to retrieve block number. Nodes service checks aborted.")
        return states, []

    for node_info in config.NODES_INFO:
        node_state = get_node_state(node_info)
        if not node_state:
            continue

        node_state["stateBlock"] = block_number
        node_state["senderTransactionCount"] = get_transaction_count(
            node_state["consensusSenderAddress"]
        )
        node_state.update(node_info)

        key = node_state["ethSigningAddress"]
        states.setdefault(key, [])
        states[key].append(node_state)
        states[key] = states[key][-5:]
        active_nodes.append(key)
    return states, active_nodes


def main() -> None:
    """Continuously monitor the health of BrightID services."""
    states = {}
    counter = 0
    while True:
        counter += 1
        try:
            states, active_nodes = update_nodes_states(states)

            check_all_nodes_services(states, active_nodes)

            check_recovery_service()

            if counter % 20 == 0:
                check_backup_service()

            if counter % 40 == 0:
                check_apps_sp_balance()
                counter = 0

            update_health_status()
        except Exception as e:
            logging.error(f"Error in monitor_service: {e}")

        time.sleep(config.CHECK_INTERVAL)


if __name__ == "__main__":
    logging.info("Starting Monitor Service...")
    monitor_thread = Thread(target=main)
    monitor_thread.start()
