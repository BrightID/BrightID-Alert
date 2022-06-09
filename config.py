NODES = [{
    'url': 'http://node.brightid.org/brightid/v6',
    'eth_address': '0x636D49c1D76ff8E04767C68fe75eC9900719464b',
    'profile_service_url': 'http://node.brightid.org/profile'
}, {
    'url': 'http://brightid.idealmoney.io/brightid/v6',
    'eth_address': '0x2f8772B0DF9Bb8e295AEa6187F03ae353B00ac3D',
    'profile_service_url': 'http://brightid.idealmoney.io/profile'
}, {
    'url': 'http://brightid2.idealmoney.io/brightid/v6',
    'eth_address': '0x51E4093bb8DA34AdD694A152635bE8e38F4F1a29',
    'profile_service_url': 'http://brightid2.idealmoney.io/profile'
}, {
    'url': 'https://brightid.59836e71dd6e5898.dyndns.dappnode.io/brightid/v6',
    'eth_address': '0x0C46c148aD7406C24a944b09099fd5316D28198E',
    'profile_service_url': 'https://brightid.59836e71dd6e5898.dyndns.dappnode.io/profile'
}, {
    'url': 'http://bright.daosquare.io/brightid/v6',
    'eth_address': '0xFa53553a1Be4493dD8C94e9f9aE8EEb98Cdeca05',
    'profile_service_url': 'http://bright.daosquare.io/profile/'
}]

NODE_ONE = 'http://node.brightid.org/brightid/v6'
RECOVERY_SERVICE_URL = 'https://recovery.brightid.org/backups/immutable/PUT_YOUR_GROUP_ID'
BACKUPS_URL = 'http://storage.googleapis.com/brightid-backups/'
IDCHAIN_RPC_URL = 'https://idchain.one/rpc/'
RECEIVER_BORDER = 24
SCORER_BORDER = 480
BALANCE_BORDER = 5
BACKUP_BORDER = 90 * 60
SNAPSHOT_PERIOD = 240
CHECK_INTERVAL = 15
MAX_MSG_INTERVAL = 24 * 60 * 60
MIN_MSG_INTERVAL = 60 * 60

KEYBASE_BOT_KEY = 'PUT_YOUR_KEY_HERE'
KEYBASE_BOT_USERNAME = 'BrightID_Bot'
KEYBASE_BOT_CHANNEL = {'name': 'brightid.core_team', 'topic_name': 'alerts_critical', 'members_type': 'team'}

TELEGRAM_BOT_KEY = 'PUT_YOUR_KEY_HERE'
TELEGRAM_BOT_CHANNEL = '@brightid_alerts'
