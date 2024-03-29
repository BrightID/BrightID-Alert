import pykeybasebot.types.chat1 as chat1
from packaging.version import Version
from datetime import datetime
from pykeybasebot import Bot
from hashlib import sha256
from web3 import Web3
import threading
import xmltodict
import requests
import asyncio
import base64
import json
import time
import config

w3 = Web3(Web3.HTTPProvider(config.IDCHAIN_RPC_URL))
issues = {}
states = {}
last_sent_alert = time.time()
keybase_bot = None
if config.KEYBASE_BOT_KEY:
    keybase_bot = Bot(
        username=config.KEYBASE_BOT_USERNAME,
        paperkey=config.KEYBASE_BOT_KEY,
        handler=None
    )


def how_long(ts):
    duration = time.time() - ts
    if duration > 24 * 60 * 60:
        int_part = int(duration / (24 * 60 * 60))
        str_part = 'day' if int_part == 1 else 'days'
    elif duration > 60 * 60:
        int_part = int(duration / (60 * 60))
        str_part = 'hour' if int_part == 1 else 'hours'
    elif duration > 60:
        int_part = int(duration / 60)
        str_part = 'minute' if int_part == 1 else 'minutes'
    else:
        return ''
    return f'since {int_part} {str_part} ago'


def alert(issue):
    global last_sent_alert
    if issue['resolved']:
        msg = issue['message']
    else:
        msg = f"{issue['message']} {how_long(issue['started_at'])}"
    print(time.strftime('%a, %d %b %Y %H:%M:%S', time.gmtime()), msg)
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
                {'chat_id': config.TELEGRAM_BOT_CHANNEL, 'text': msg})
            headers = {'content-type': 'application/json',
                       'cache-control': 'no-cache'}
            url = f'https://api.telegram.org/bot{config.TELEGRAM_BOT_KEY}/sendMessage'
            requests.post(url, data=payload, headers=headers)
            telegram_done = True
        except Exception as e:
            print('telegram error', e)
            telegram_done = False
    if keybase_done or telegram_done:
        last_sent_alert = time.time()
    return keybase_done or telegram_done


def check_issues():
    for key in list(issues.keys()):
        issue = issues[key]
        if issue['resolved']:
            res = alert(issue)
            if res:
                del issues[key]
            continue

        if issue['last_alert'] == 0:
            res = alert(issue)
            if res:
                issue['last_alert'] = time.time()
                issue['alert_number'] += 1
            continue

        next_interval = min(config.MIN_MSG_INTERVAL * 2 **
                            (issue['alert_number'] - 1), config.MAX_MSG_INTERVAL)
        next_alert = issue['last_alert'] + next_interval
        if next_alert <= time.time():
            res = alert(issue)
            if res:
                issue['last_alert'] = time.time()
                issue['alert_number'] += 1
    if time.time() - last_sent_alert > 24 * 60 * 60 and len(issues) == 0:
        res = alert({
            'resolved': True,
            'message': "There wasn't any issue in the past 24 hours"
        })


def issue_hash(node, issue_name):
    message = (node + issue_name).encode('ascii')
    h = base64.b64encode(sha256(message).digest()).decode('ascii')
    return h.replace('/', '_').replace('+', '-').replace('=', '')


def get_idchain_block_number():
    payload = json.dumps(
        {'jsonrpc': '2.0', 'method': 'eth_blockNumber', 'params': [], 'id': 1})
    headers = {'content-type': 'application/json', 'cache-control': 'no-cache'}
    r = requests.request('POST', config.IDCHAIN_RPC_URL,
                         data=payload, headers=headers)
    return int(r.json()['result'], 0)


def get_eidi_balance(addr):
    payload = json.dumps({
        'jsonrpc': '2.0',
        'method': 'eth_getBalance',
        'params': [addr, 'latest'],
        'id': 1
    })
    headers = {'content-type': 'application/json', 'cache-control': 'no-cache'}
    r = requests.request('POST', config.IDCHAIN_RPC_URL,
                         data=payload, headers=headers)
    return int(r.json()['result'], 0) / 10**18


def get_node_state(node):
    global states
    key = issue_hash(node['url'], 'state')
    try:
        r = requests.get(node['url'])
        state = r.json().get('data', {})
        state['senderTransactionCount'] = w3.eth.getTransactionCount(
            w3.toChecksumAddress(state['consensusSenderAddress']), 'pending')
        if key not in states:
            states[key] = []
        states[key].append(state)
        states[key] = states[key][-5:]
        if key in issues:
            issues[key]['resolved'] = True
            issues[key]['message'] = f'BrightID node {node["url"]} state issue is resolved.'
    except:
        state = None
        if key not in issues:
            issues[key] = {
                'resolved': False,
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
    key = issue_hash(node['url'], 'Eidi balance')
    if balance < config.BALANCE_BORDER:
        if key not in issues:
            issues[key] = {
                'resolved': False,
                'message': f'BrightID node {node["url"]} has only {round(balance, 2)} Eidi! Alert border is {config.BALANCE_BORDER} Eidi.',
                'started_at': int(time.time()),
                'last_alert': 0,
                'alert_number': 0
            }
        else:
            issues[key]['message'] = f'BrightID node {node["url"]} has only {round(balance, 2)} Eidi! Alert border is {config.BALANCE_BORDER} Eidi.'
    else:
        if key in issues:
            issues[key]['resolved'] = True
            issues[key]['message'] = f'BrightID node {node["url"]} Eidi balance issue is resolved.'


def check_node_receiver(node, state, block_number):
    key = issue_hash(node['url'], 'consensus receiver service')
    if block_number - state['lastProcessedBlock'] > config.RECEIVER_BORDER:
        if key not in issues:
            issues[key] = {
                'resolved': False,
                'message': f'BrightID node {node["url"]} consensus receiver service is not working!',
                'started_at': int(time.time()),
                'last_alert': 0,
                'alert_number': 0
            }
    else:
        if key in issues:
            issues[key]['resolved'] = True
            issues[key]['message'] = f'BrightID node {node["url"]} consensus receiver service issue is resolved.'


def check_node_scorer(node, state, block_number):
    key = issue_hash(node['url'], 'scorer service')
    if block_number - state['verificationsBlock'] > config.SNAPSHOT_PERIOD + config.SCORER_BORDER:
        if key not in issues:
            issues[key] = {
                'resolved': False,
                'message': f'BrightID node {node["url"]} scorer service is not working!',
                'started_at': int(time.time()),
                'last_alert': 0,
                'alert_number': 0
            }
    else:
        if key in issues:
            issues[key]['resolved'] = True
            issues[key]['message'] = f'BrightID node {node["url"]} scorer service issue is resolved.'


def check_node_sender(node):
    if len(states[issue_hash(node['url'], 'state')]) < 5:
        return

    key = issue_hash(node['url'], 'consensus sender service')
    inits = [state['initOp']
             for state in states[issue_hash(node['url'], 'state')]]
    sents = [state['senderTransactionCount']
             for state in states[issue_hash(node['url'], 'state')]]
    is_sending = sents[-1] > sents[-3]
    # if inits are increasing or constant while first is not 0
    if (sorted(inits) == inits and inits[0] != 0) and not is_sending:
        if key not in issues:
            issues[key] = {
                'resolved': False,
                'message': f'BrightID node {node["url"]} consensus sender service is not working!',
                'started_at': int(time.time()),
                'last_alert': 0,
                'alert_number': 0
            }
    else:
        if key in issues:
            issues[key]['resolved'] = True
            issues[key]['message'] = f'BrightID node {node["url"]} consensus sender service issue is resolved.'


def check_node_profile(node):
    r = requests.get(node['profile_service_url'])
    key = issue_hash(node['url'], 'profile service')
    if r.status_code != 200:
        if key not in issues:
            issues[key] = {
                'resolved': False,
                'message': f'BrightID node {node["url"]} profile service is not working!',
                'started_at': int(time.time()),
                'last_alert': 0,
                'alert_number': 0
            }
    else:
        if key in issues:
            issues[key]['resolved'] = True
            issues[key]['message'] = f'BrightID node {node["url"]} profile service issue is resolved.'


def check_node_version(node):
    last_release = states[issue_hash(
        'http://node.brightid.org/brightid/v6/state', 'state')][0]['version']
    node_release = states[issue_hash(node['url'], 'state')][0]['version']
    key = issue_hash(node['url'], 'v6_version')
    if Version(node_release) < Version(last_release):
        if key not in issues:
            issues[key] = {
                'resolved': False,
                'message': f'BrightID node {node["url"]} ({node_release}) is not updated! current release is {last_release}',
                'started_at': int(time.time()),
                'last_alert': 0,
                'alert_number': 0
            }
    else:
        if key in issues:
            issues[key]['resolved'] = True
            issues[key]['message'] = f'BrightID node {node["url"]} update issue is resolved.'


def check_nodes():
    for node in config.NODES:
        try:
            state = get_node_state(node)
            if state:
                block_number = get_idchain_block_number()
                check_node_balance(node, state)
                check_node_receiver(node, state, block_number)
                check_node_scorer(node, state, block_number)
                check_node_sender(node)
                check_node_profile(node)
                check_node_version(node)
                check_node_updater(node, state, block_number)
        except Exception as e:
            print('Error: ', node['url'], e)


def check_recovery_service():
    r = requests.get(config.RECOVERY_SERVICE_URL)
    key = issue_hash(config.NODE_ONE, 'recovery service')
    if r.status_code != 200:
        if key not in issues:
            issues[key] = {
                'resolved': False,
                'message': f'BrightID recovery service is not working!',
                'started_at': int(time.time()),
                'last_alert': 0,
                'alert_number': 0
            }
    else:
        if key in issues:
            issues[key]['resolved'] = True
            issues[key]['message'] = f'BrightID recovery service issue is resolved.'


def check_backup_service():
    key = issue_hash(config.NODE_ONE, 'backup service')
    r = requests.get(config.BACKUPS_URL)
    backups = xmltodict.parse(r.text)['ListBucketResult']['Contents']
    times = [b['LastModified']
             for b in backups if b['Key'].endswith('.tar.gz')]
    last_backup = datetime.strptime(
        times[-1], '%Y-%m-%dT%H:%M:%S.%fZ').timestamp()
    if time.time() - last_backup > config.BACKUP_BORDER:
        if key not in issues:
            issues[key] = {
                'resolved': False,
                'message': f'BrightID official node backup service is not working!',
                'started_at': int(time.time()),
                'last_alert': 0,
                'alert_number': 0
            }
    else:
        if key in issues:
            issues[key]['resolved'] = True
            issues[key]['message'] = f'BrightID official node backup service issue is resolved.'


def check_apps_sp_balance():
    apps = requests.get(f'{config.NODE_ONE}/apps').json()['data']['apps']
    for app in apps:
        if app['assignedSponsorships'] == 0:
            continue
        key = issue_hash(app['id'], 'sp balance')
        border = int(app['assignedSponsorships'] * 0.05)
        if app['unusedSponsorships'] < border:
            if key not in issues:
                issues[key] = {
                    'resolved': False,
                    'message': f'{app["id"]} has only {app["unusedSponsorships"]} unused Sponsorships!',
                    'started_at': int(time.time()),
                    'last_alert': 0,
                    'alert_number': 0
                }
            else:
                issues[key]['message'] = f'{app["id"]} has only {app["unusedSponsorships"]} unused Sponsorships!'
        else:
            if key in issues:
                issues[key]['resolved'] = True
                issues[key]['message'] = f'{app["id"]} Sponsorships balance issue is resolved.'


def check_node_updater(node, state, block_number):
    apps_key = issue_hash(node['url'], 'apps updater service')
    if block_number - state['appsLastUpdateBlock'] > config.APPS_UPDATE_BORDER:
        if apps_key not in issues:
            issues[apps_key] = {
                'resolved': False,
                'message': f'BrightID node {node["url"]} apps updater service is not working!',
                'started_at': int(time.time()),
                'last_alert': 0,
                'alert_number': 0
            }
    else:
        if apps_key in issues:
            issues[apps_key]['resolved'] = True
            issues[apps_key]['message'] = f'BrightID node {node["url"]} apps updater service issue is resolved.'

    sp_key = issue_hash(node['url'], 'sponsorships updater service')
    if block_number - state['sponsorshipsLastUpdateBlock'] > config.SPONSORSHIPS_UPDATE_BORDER:
        if sp_key not in issues:
            issues[sp_key] = {
                'resolved': False,
                'message': f'BrightID node {node["url"]} sponsorships updater service is not working!',
                'started_at': int(time.time()),
                'last_alert': 0,
                'alert_number': 0
            }
    else:
        if sp_key in issues:
            issues[sp_key]['resolved'] = True
            issues[sp_key]['message'] = f'BrightID node {node["url"]} sponsorships updater service issue is resolved.'

    sg_key = issue_hash(node['url'], 'seed groups updater service')
    if block_number - state['seedGroupsLastUpdateBlock'] > config.SEEDGROUPS_UPDATE_BORDER:
        if sg_key not in issues:
            issues[sg_key] = {
                'resolved': False,
                'message': f'BrightID node {node["url"]} seed groups updater service is not working!',
                'started_at': int(time.time()),
                'last_alert': 0,
                'alert_number': 0
            }
    else:
        if sg_key in issues:
            issues[sg_key]['resolved'] = True
            issues[sg_key]['message'] = f'BrightID node {node["url"]} seed groups updater service issue is resolved.'


def monitor_service():
    i = 0
    while True:
        i += 1
        check_nodes()

        try:
            check_recovery_service()
        except Exception as e:
            print('Error recovery service: ', e)

        if i % 20 == 0:
            try:
                check_backup_service()
            except Exception as e:
                print('Error backup service: ', e)

        if i == 40:
            try:
                check_apps_sp_balance()
            except Exception as e:
                print('Error check_apps_sp_balance service: ', e)
            i = 0

        time.sleep(config.CHECK_INTERVAL)


def alert_service():
    while True:
        check_issues()
        time.sleep(config.CHECK_INTERVAL)


if __name__ == '__main__':
    print('START')
    service1 = threading.Thread(target=monitor_service)
    service1.start()
    alert_service()
