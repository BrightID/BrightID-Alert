
import pykeybasebot.types.chat1 as chat1
from pykeybasebot import Bot
from hashlib import sha256
import threading
import requests
import asyncio
import base64
import json
import time
import config

issues = {}
states = []
keybase_bot = None
if config.KEYBASE_BOT_KEY:
    keybase_bot = Bot(
        username=config.KEYBASE_BOT_USERNAME,
        paperkey=config.KEYBASE_BOT_KEY,
        handler=None
    )


def alert(msg):
    print(time.strftime("%a, %d %b %Y %H:%M:%S", time.gmtime()), msg)
    if config.KEYBASE_BOT_KEY:
        try:
            channel = chat1.ChatChannel(**config.KEYBASE_BOT_CHANNEL)
            asyncio.run(keybase_bot.chat.send(channel, msg))
            keybase_done = True
        except Exception as e:
            print('keybase error', e)
            keybase_done = False
    if config.TELEGRAM_BOT_KEY:
        try:
            payload = json.dumps(
                {"chat_id": config.TELEGRAM_BOT_CHANNEL, "text": msg})
            headers = {'content-type': "application/json",
                       'cache-control': "no-cache"}
            url = f'https://api.telegram.org/bot{config.TELEGRAM_BOT_KEY}/sendMessage'
            requests.post(url, data=payload, headers=headers)
            telegram_done = True
        except Exception as e:
            print('telegram error', e)
            telegram_done = False
    return keybase_done or telegram_done


def check_issues():
    for issue in issues.values():
        if issue['last_alert'] == 0:
            res = alert(issue['message'])
            if res:
                issue['last_alert'] = time.time()
                issue['alert_number'] += 1
            continue

        next_interval = min(config.MIN_MSG_INTERVAL * 2 ** (issue['alert_number'] - 1), config.MAX_MSG_INTERVAL)
        next_alert = issue['last_alert'] + next_interval
        if next_alert <= time.time():
            res = alert(issue['message'])
            if res:
                issue['last_alert'] = time.time()
                issue['alert_number'] += 1


def issue_hash(node, issue_name):
    message = (node + issue_name).encode('ascii')
    h = base64.b64encode(sha256(message).digest()).decode("ascii")
    return h.replace('/', '_').replace('+', '-').replace('=', '')


def get_idchain_block_number():
    payload = json.dumps(
        {"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1})
    headers = {'content-type': "application/json", 'cache-control': "no-cache"}
    r = requests.request("POST", config.IDCHAIN_RPC_URL,
                         data=payload, headers=headers)
    return int(r.json()['result'], 0)


def get_eidi_balance(addr):
    payload = json.dumps({
        "jsonrpc": "2.0",
        "method": "eth_getBalance",
        "params": [addr, 'latest'],
        "id": 1
    })
    headers = {'content-type': "application/json", 'cache-control': "no-cache"}
    r = requests.request("POST", config.IDCHAIN_RPC_URL,
                         data=payload, headers=headers)
    return int(r.json()['result'], 0) / 10**18


def get_node_state(node):
    global states
    try:
        r = requests.get(node['url'] + '/state')
        state = r.json().get('data', {})
        states.append(state)
        states = states[-5:]
    except:
        state = None
        key = issue_hash(node['url'], 'state')
        if key not in issues:
            issues[key] = {
                'node': node,
                'message': f'BrightID node {node["url"]} is not returning its state!',
                'started_at': int(time.time()),
                'last_alert': 0,
                'alert_number': 0
            }
    return state


def check_node_balance(node, state):
    consensus_sender = state.get('consensusSenderAddress')
    if not consensus_sender:
        consensus_sender = node['eth_address']
    balance = get_eidi_balance(consensus_sender)
    if balance < config.BALANCE_BORDER:
        key = issue_hash(node['url'], 'Eidi balance')
        if key not in issues:
            issues[key] = {
                'node': node,
                'message': f'BrightID node {node["url"]} does not have enough Eidi balance!',
                'started_at': int(time.time()),
                'last_alert': 0,
                'alert_number': 0
            }


def check_node_receiver(node, state, block_number):
    if block_number - state['lastProcessedBlock'] > config.RECEIVER_BORDER:
        key = issue_hash(node['url'], 'consensus receiver service')
        if key not in issues:
            issues[key] = {
                'node': node,
                'message': f'BrightID node {node["url"]} consensus receiver service is not working!',
                'started_at': int(time.time()),
                'last_alert': 0,
                'alert_number': 0
            }


def check_node_scorer(node, state, block_number):
    if block_number - state['verificationsBlock'] > config.SNAPSHOT_PERIOD + config.SCORER_BORDER:
        key = issue_hash(node['url'], 'scorer service')
        if key not in issues:
            issues[key] = {
                'node': node,
                'message': f'BrightID node {node["url"]} scorer service is not working!',
                'started_at': int(time.time()),
                'last_alert': 0,
                'alert_number': 0
            }


def check_node_sender(node):
    inits = [state['initOp'] for state in states]
    # if numbers are increasing or constant while first is not 0
    if sorted(inits) == inits and inits[0] != 0:
        key = issue_hash(node['url'], 'consensus sender service')
        if key not in issues:
            issues[key] = {
                'node': node,
                'message': f'BrightID node {node["url"]} consensus sender service is not working!',
                'started_at': int(time.time()),
                'last_alert': 0,
                'alert_number': 0
            }


def check_node_profile(node):
    r = requests.get(node['profile_service_url'])
    if r.status_code != 200:
        key = issue_hash(node['url'], 'profile service')
        if key not in issues:
            issues[key] = {
                'node': node,
                'message': f'BrightID node {node["url"]} profile service is not working!',
                'started_at': int(time.time()),
                'last_alert': 0,
                'alert_number': 0
            }


def check_node(node):
    check_node_profile(node)
    state = get_node_state(node)
    if state:
        block_number = get_idchain_block_number()
        check_node_balance(node, state)
        check_node_receiver(node, state, block_number)
        check_node_scorer(node, state, block_number)
        check_node_sender(node)


def monitor_service():
    while True:
        for node in config.NODES:
            try:
                check_node(node)
            except Exception as e:
                print('Error: ', node['url'], e)
        time.sleep(config.CHECK_INTERVAL)


def alert_service():
    while True:
        check_issues()
        time.sleep(config.CHECK_INTERVAL)


if __name__ == '__main__':
    service1 = threading.Thread(target=monitor_service)
    service1.start()
    service2 = threading.Thread(target=alert_service)
    service2.start()
