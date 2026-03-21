#!/usr/bin/env python3
"""
fx-tracker - 匯率追蹤腳本
用法:
  python3 fx-tracker.py fetch          # 抓取並儲存所有觀察中的匯率
  python3 fx-tracker.py fetch USD-GBP  # 抓取特定匯率
  python3 fx-tracker.py avg USD-GBP 30  # 計算30天平均
  python3 fx-tracker.py list            # 列出觀察清單
  python3 fx-tracker.py add USD-EUR     # 新增到觀察清單
  python3 fx-tracker.py remove USD-EUR  # 從觀察清單移除
"""

import sys
import json
import requests
import psycopg2
from datetime import datetime, date, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ===== 設定 =====
DB_CONFIG = {
    'host': 'localhost',
    'port': '5432',
    'user': 'george',
    'database': 'prostage'
}

EMAIL_CONFIG = {
    'from': 'megan@precaster.com.tw',
    'to': 'george@precaster.com.tw',
    'smtp': 'smtp.gmail.com',
    'port': 587
}

DEFAULT_PAIRS = ['USD-TWD', 'USD-JPY', 'USD-GBP', 'USD-CNY']

# ===== 資料庫函式 =====
def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

def init_db():
    """確保 tables 存在"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # exchange_rates table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS exchange_rates (
            id SERIAL PRIMARY KEY,
            from_currency VARCHAR(3) NOT NULL,
            to_currency VARCHAR(3) NOT NULL,
            rate DECIMAL(12,6) NOT NULL,
            effective_date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(from_currency, to_currency, effective_date)
        )
    """)
    
    # fx_watchlist table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS fx_watchlist (
            id SERIAL PRIMARY KEY,
            from_currency VARCHAR(3) NOT NULL,
            to_currency VARCHAR(3) NOT NULL UNIQUE,
            alert_threshold DECIMAL(5,2) DEFAULT 5.00,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    cur.close()
    conn.close()

def get_watchlist():
    """取得觀察清單"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT from_currency, to_currency, alert_threshold FROM fx_watchlist WHERE is_active = TRUE")
    result = cur.fetchall()
    cur.close()
    conn.close()
    return result

def get_latest_rate(from_cur, to_cur):
    """取得最新匯率"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT rate, effective_date FROM exchange_rates 
        WHERE from_currency = %s AND to_currency = %s 
        ORDER BY effective_date DESC LIMIT 1
    """, (from_cur, to_cur))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result

def get_previous_rate(from_cur, to_cur, days=1):
    """取得之前的匯率"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT rate, effective_date FROM exchange_rates 
        WHERE from_currency = %s AND to_currency = %s 
        ORDER BY effective_date DESC LIMIT 1 OFFSET %s
    """, (from_cur, to_cur, days))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result

def get_average(from_cur, to_cur, days):
    """計算移動平均"""
    conn = get_db_connection()
    cur = conn.cursor()
    start_date = date.today() - timedelta(days=days)
    cur.execute("""
        SELECT AVG(rate) FROM exchange_rates 
        WHERE from_currency = %s AND to_currency = %s AND effective_date >= %s
    """, (from_cur, to_cur, start_date))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result[0] if result[0] else None

def save_rate(from_cur, to_cur, rate):
    """儲存匯率"""
    conn = get_db_connection()
    cur = conn.cursor()
    today = date.today()
    cur.execute("""
        INSERT INTO exchange_rates (from_currency, to_currency, rate, effective_date)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (from_currency, to_currency, effective_date) 
        DO UPDATE SET rate = EXCLUDED.rate
    """, (from_cur, to_cur, rate, today))
    conn.commit()
    cur.close()
    conn.close()

def add_to_watchlist(from_cur, to_cur, threshold=5.0):
    """新增到觀察清單"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO fx_watchlist (from_currency, to_currency, alert_threshold)
        VALUES (%s, %s, %s)
        ON CONFLICT (to_currency) DO UPDATE SET is_active = TRUE
    """, (from_cur, to_cur, threshold))
    conn.commit()
    cur.close()
    conn.close()

def remove_from_watchlist(to_cur):
    """從觀察清單移除"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE fx_watchlist SET is_active = FALSE WHERE to_currency = %s", (to_cur,))
    conn.commit()
    cur.close()
    conn.close()

# ===== 匯率抓取 =====
def fetch_rate(from_cur, to_cur):
    """從 API 抓取匯率"""
    try:
        # 使用 exchangerate-api.com 免費 API
        url = f"https://api.exchangerate-api.com/v4/latest/{from_cur}"
        response = requests.get(url, timeout=10)
        data = response.json()
        return data['rates'].get(to_cur)
    except Exception as e:
        print(f"抓取失敗 {from_cur}-{to_cur}: {e}")
        return None

def fetch_and_save(pair):
    """抓取並儲存匯率，回傳 (from, to, rate)"""
    from_cur, to_cur = pair.split('-')
    rate = fetch_rate(from_cur, to_cur)
    if rate:
        save_rate(from_cur, to_cur, rate)
        print(f"✓ {from_cur} → {to_cur}: {rate}")
    return from_cur, to_cur, rate

# ===== Email 警報 =====
def send_alert(from_cur, to_cur, current_rate, previous_rate, threshold):
    """發送匯率變動警報"""
    if not previous_rate:
        return
    
    change_pct = ((current_rate - previous_rate) / previous_rate) * 100
    
    if abs(change_pct) >= threshold:
        direction = "↑" if change_pct > 0 else "↓"
        body = f"""
{from_cur} → {to_cur}
現價：{current_rate:.4f}
昨日：{previous_rate:.4f}
變動：{change_pct:+.2f}% {direction}

時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
        subject = f"[FX Alert] {from_cur}-{to_cur} 變動 {change_pct:+.2f}%"
        
        try:
            msg = MIMEMultipart()
            msg['From'] = EMAIL_CONFIG['from']
            msg['To'] = EMAIL_CONFIG['to']
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(EMAIL_CONFIG['smtp'], EMAIL_CONFIG['port']) as server:
                server.starttls()
                # Note: 需要 SMTP 認證資訊
                pass
                server.send_message(msg)
            
            print(f"✓ 警報已發送: {subject}")
        except Exception as e:
            print(f"✗ 發送警報失敗: {e}")

def check_alerts():
    """檢查所有觀察中的匯率"""
    watchlist = get_watchlist()
    for from_cur, to_cur, threshold in watchlist:
        current = get_latest_rate(from_cur, to_cur)
        previous = get_previous_rate(from_cur, to_cur, days=1)
        
        if current and previous:
            send_alert(from_cur, to_cur, float(current[0]), float(previous[0]), float(threshold))

# ===== 主程式 =====
def main():
    init_db()
    
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    command = sys.argv[1].lower()
    
    if command == 'fetch':
        if len(sys.argv) >= 3:
            # 抓取特定匯率
            pair = sys.argv[2].upper()
            fetch_and_save(pair)
        else:
            # 抓取所有觀察中的匯率
            watchlist = get_watchlist()
            if not watchlist:
                # 如果沒有觀察清單，用預設清單
                pairs = DEFAULT_PAIRS
            else:
                pairs = [f"{r[0]}-{r[1]}" for r in watchlist]
            
            for pair in pairs:
                fetch_and_save(pair)
            
            # 檢查警報
            check_alerts()
    
    elif command == 'avg':
        if len(sys.argv) >= 4:
            pair = sys.argv[2].upper()
            days = int(sys.argv[3])
            from_cur, to_cur = pair.split('-')
            avg = get_average(from_cur, to_cur, days)
            if avg:
                print(f"{from_cur}-{to_cur} {days}天平均: {avg:.4f}")
            else:
                print("沒有足夠資料")
        else:
            print("用法: python3 fx-tracker.py avg USD-GBP 30")
    
    elif command == 'list':
        watchlist = get_watchlist()
        if watchlist:
            print("觀察中的匯率：")
            for from_cur, to_cur, threshold in watchlist:
                latest = get_latest_rate(from_cur, to_cur)
                rate_str = f"{latest[0]:.4f}" if latest else "N/A"
                print(f"  {from_cur}-{to_cur}: {rate_str} (警報閾值: {threshold}%)")
        else:
            print("觀察清單是空的")
    
    elif command == 'add':
        if len(sys.argv) >= 3:
            pair = sys.argv[2].upper()
            from_cur, to_cur = pair.split('-')
            add_to_watchlist(from_cur, to_cur)
            print(f"✓ 已新增 {pair} 到觀察清單")
        else:
            print("用法: python3 fx-tracker.py add USD-EUR")
    
    elif command == 'remove':
        if len(sys.argv) >= 3:
            pair = sys.argv[2].upper()
            to_cur = pair.split('-')[1]
            remove_from_watchlist(to_cur)
            print(f"✓ 已從觀察清單移除 {pair}")
        else:
            print("用法: python3 fx-tracker.py remove USD-EUR")
    
    else:
        print(f"未知指令: {command}")
        print(__doc__)

if __name__ == '__main__':
    main()
