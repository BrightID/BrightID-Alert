import json
import time
import asyncio
import requests
from pykeybasebot import Bot
import pykeybasebot.types.chat1 as chat1
from config import *

sent = {}
keybaseBot = None
if KEYBASE_BOT_KEY:
    keybaseBot = Bot(username=KEYBASE_BOT_USERNAME, paperkey=KEYBASE_BOT_KEY, handler=None)

def alert(msg):
    if msg in sent and time.time() - sent[msg] < SENT_TIMEOUT:
        return
    print(time.strftime("%a, %d %b %Y %H:%M:%S", time.gmtime()), msg)
    sent[msg] = int(time.time())
    if KEYBASE_BOT_KEY:
        try:
            channel = chat1.ChatChannel(**KEYBASE_BOT_CHANNEL)
            asyncio.run(keybaseBot.chat.send(channel, msg))
        except Exception as e:
            print('keybase error', e)
    if TELEGRAM_BOT_KEY:
        try:
            payload = json.dumps({"chat_id": TELEGRAM_BOT_CHANNEL, "text": msg})
            headers = {'content-type': "application/json", 'cache-control': "no-cache"}
            url = f'https://api.telegram.org/bot{TELEGRAM_BOT_KEY}/sendMessage'
            r = requests.post(url, data=payload, headers=headers)
        except Exception as e:
            print('telegram error', e)

def getIDChainBlockNumber():
    payload = json.dumps({"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1})
    headers = {'content-type': "application/json", 'cache-control': "no-cache"}
    r = requests.request("POST", IDCHAIN_RPC_URL, data=payload, headers=headers)
    return int(r.json()['result'], 0)

def getIDChainBalance(addr):
    payload = json.dumps({"jsonrpc": "2.0", "method": "eth_getBalance", "params": [addr, 'latest'], "id": 1})
    headers = {'content-type': "application/json", 'cache-control': "no-cache"}
    r = requests.request("POST", IDCHAIN_RPC_URL, data=payload, headers=headers)
    return int(r.json()['result'], 0) / 10**18

states = []
def check():
    global states
    r = requests.get(NODE_URL + '/state')
    state = None
    try:
        state = r.json().get('data', {})
        states.append(state)
        states = states[-3:]
    except:
        pass
    if not state:
        alert(f'BrightID node {NODE_URL} is not returning its state!')
    else:
        blockNumber = getIDChainBlockNumber()
        if blockNumber - state['lastProcessedBlock'] > RECEIVER_BORDER:
            alert(f'BrightID node {NODE_URL} consensus receiver service is not working!')
        if blockNumber - state['verificationsBlock'] > SNAPSHOT_PERIOD + SCORER_BORDER:
            alert(f'BrightID node {NODE_URL} scorer service is not working!')
        inits = [state['initOp'] for state in states]
        print(inits)
        # if numbers are increasing or constant while last is not 0
        if sorted(inits) == inits and inits[-1] != 0:
            alert(f'BrightID node {NODE_URL} consensus sender service is not working!')
    balance = getIDChainBalance(NODE_ETH_ADDRESS)
    if balance < BALANCE_BORDER:
        alert(f'BrightID node {NODE_URL} does not have enough Eidi balance!')

if __name__ == '__main__':
    while True:
        try:
            check()
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt as e:
            raise
        except Exception as e:
            print('error', e)

