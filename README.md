# fx-tracker

OpenClaw skill for tracking foreign exchange rates with historical data and moving average analysis.

## Features

- Fetch live exchange rates (USD to TWD, JPY, GBP, CNY, KRW, etc.)
- Store historical rates in PostgreSQL
- Calculate 30/90/180-day moving averages
- Alert when rate moves beyond threshold (±5%)
- Daily auto-update via OpenClaw cron

## Installation

Copy the `fx-tracker/` folder to your OpenClaw skills directory:

```
~/.openclaw/workspace/skills/fx-tracker/
```

## Setup

### Database

Requires PostgreSQL with these tables:

```sql
CREATE TABLE exchange_rates (
  from_currency VARCHAR(3) NOT NULL,
  to_currency VARCHAR(3) NOT NULL,
  rate DECIMAL(18, 8) NOT NULL,
  effective_date DATE NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (from_currency, to_currency, effective_date)
);

CREATE TABLE fx_watchlist (
  from_currency VARCHAR(3) NOT NULL,
  to_currency VARCHAR(3) NOT NULL,
  alert_threshold DECIMAL(5, 2) DEFAULT 5.00,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (from_currency, to_currency)
);
```

### Cron Job

Set up daily auto-fetch at 2:00 AM:

```
openclaw cron add --name "fx-tracker-0200" --cron "0 2 * * *" --message "更新匯率" --to "YOUR_DISCORD_ID" --channel "discord"
```

## Usage

```bash
# Fetch latest rates for all watchlist pairs
python3 fx-tracker.py fetch

# Fetch specific pair
python3 fx-tracker.py fetch USD-TWD

# List all watchlist pairs
python3 fx-tracker.py list

# Calculate moving average
python3 fx-tracker.py avg USD-TWD 30

# Add pair to watchlist
python3 fx-tracker.py add USD-EUR 5.0

# Remove pair from watchlist
python3 fx-tracker.py remove USD-EUR
```

## Database Connection

Edit the `DB_CONFIG` in `fx-tracker.py`:

```python
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "prostage",
    "user": "george"
}
```

## License

MIT
