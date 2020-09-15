# BrightID-Alert
Monitor a BrightID node and send alerts to keybase and telegram when it has problems. This bot checks if:
- Node is up and API is responding
- `consensus_receiver` service is actively working
- `scorer` service is actively working
- The node address has enough Eidi to relay operations sent by user

## Prerequisites
- Python3.7
- keybase

## Install
```
$ pip3 install -r requirements.txt
```

## Configure

- Create a telegram bot and a telegram channel, add the bot to the channel, make it admin and update telegram `TELEGRAM_BOT_KEY` and `TELEGRAM_BOT_CHANNEL` in config.py
- Create a keybase bot and a keybase channel, add the bot to the channel as writer and update `KEYBASE_BOT_KEY`, `KEYBASE_BOT_USERNAME` and `KEYBASE_BOT_CHANNEL` in config.py

You can set `TELEGRAM_BOT_KEY` or `KEYBASE_BOT_KEY` to `None` if you want to ignore sending messages to those messangers.

## Run
```
$ python3.7 main.py
```
