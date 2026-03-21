# fx-tracker

匯率追蹤 Skill - 自動抓取匯率、記錄歷史、計算平均、發送警報。

## 功能

- 抓取即時匯率（USD → NTD/JPY/GBP/CNY 等）
- 記錄歷史匯率到資料庫
- 計算 30/90/180 天移動平均
- 監控匯率變動，超過阈值（預設 5%）自動 Email 警報
- 每日固定時間更新（11:00、17:00）

## 資料庫

### exchange_rates 表
```
exchange_rates
├── id (PK)
├── from_currency (USD)
├── to_currency (GBP/EUR/JPY...)
├── rate (匯率)
├── effective_date
└── created_at
```

### fx_watchlist 表
```
fx_watchlist
├── id (PK)
├── from_currency
├── to_currency
├── alert_threshold (default 5%)
├── is_active
└── created_at
```

## 使用方式

### 查詢現價
```
查詢 USD-GBP 現價
```

### 查詢移動平均
```
USD-GBP 30天平均
USD-JPY 90天平均
```

### 查詢歷史
```
USD-EUR 上週平均
USD-NTD 這季平均
```

### 管理觀察清單
```
列出觀察中的匯率
新增 USD-EUR 到觀察清單
移除 USD-EUR 從觀察清單
```

### 手動更新匯率
```
更新所有匯率
更新 USD-GBP
```

### 設定警報
```
設定 USD-JPY 警報閾值 3%
```

## Cron 排程

自動更新：每天 11:00、17:00
警報檢查：每次更新時

## API 來源

使用 exchangerate-api.com（免費 API，無需 key）

## Email 警報格式

```
標題：[FX Alert] USD-GBP 變動 +5.2%

USD → GBP
現價：0.82
昨日：0.78
變動：+5.2% ↑

時間：2026-03-21 11:00
```
