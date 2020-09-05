import json
import time
import asyncio
import requests
from pykeybasebot import Bot
import pykeybasebot.types.chat1 as chat1
from config import *

sent = {}
bot = Bot(username=KEYBASE_BOT_USERNAME, paperkey=KEYBASE_BOT_KEY, handler=None)
def alert(msg):
    if msg in sent and time.time() - sent[msg] < SENT_TIMEOUT:
        return
    sent[msg] = int(time.time())
    channel = chat1.ChatChannel(**KEYBASE_BOT_CHANNEL)
    asyncio.run(bot.chat.send(channel, msg))

def checkIDChainNodes():
    payload = json.dumps({"jsonrpc": "2.0", "method": "clique_status", "params": [], "id": 1})
    headers = {'content-type': "application/json", 'cache-control': "no-cache"}
    r = requests.request("POST", IDCHAIN_RPC_URL, data=payload, headers=headers)
    status = r.json()['result']
    numBlocks = status['numBlocks']
    sealersCount = len(status['sealerActivity'])
    for sealer, sealedBlock in status['sealerActivity'].items():
        if sealedBlock < (numBlocks/sealersCount - SEALING_BORDER):
            alert(f'IDChain node {sealer}  is not sealing blocks!')

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

def checkBrightIDNode(node, blockNumber):
    r = requests.get(node['url'] + '/state')
    state = r.json().get('data', {})
    if not state:
        alert(f'BrightID node {node["url"]} is not returning its state!')
    else:
        print(node, blockNumber, state['lastProcessedBlock'], state['verificationsBlock'])
        if blockNumber - state['lastProcessedBlock'] > RECEIVER_BORDER:
            alert(f'BrightID node {node["url"]} consensus service is not working!')
        if blockNumber - state['verificationsBlock'] > 120 + SCORER_BORDER:
            alert(f'BrightID node {node["url"]} scorer service is not working!')
    if getIDChainBalance(node['eth_address']) < BALANCE_BORDER:
        alert(f'BrightID node {node["url"]} does not have enough Eidi balance!')

def main():
    checkIDChainNodes()
    blockNumber = getIDChainBlockNumber()
    for node in BRIGHTID_NODES:
        checkBrightIDNode(node, blockNumber)

if __name__ == '__main__':
    main()
