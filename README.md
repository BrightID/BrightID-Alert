# BrightID-Alert
Monitor a BrightID node and send alerts to keybase and telegram when it has problems. This bot checks if:
- Node is up and API is responding
- `consensus_receiver` service is actively working
- `scorer` service is actively working
- The node address has enough Eidi to relay operations sent by user
