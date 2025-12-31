import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from alpaca_trade_api.rest import REST
from datetime import datetime

# --- 版本控制 ---
VERSION = "2.17-B (Form Input Mode)"

# --- 設定網頁配置 ---
st.set_page_config(page_title="AI 投資決策中心", layout="wide")

# ==========================================
# 核心函數
# ==========================================

# 1. 取得個股資料
@st.cache_data
def get_stock_data(symbol):
    stock = yf.Ticker(symbol)
    info = stock.info
    hist = stock.history(period="5y")
    financials = stock.financials
    return info, hist, financials

# 2. 取得 Alpaca 庫存資料
def get_portfolio_data(api_key, secret_key, input_df):
    api_key = api_key.strip()
    secret_key = secret_key.strip()
    api = REST(api_key, secret_key, base_url='https://paper-api.alpaca.markets')
    
    results = []
    error_logs = []
    
    # 確保輸入的 DataFrame 有正確的欄位
    if input_df.empty:
        return pd.DataFrame(), 0, []

    for index, row in input_df.iterrows():
        # 基本防呆
        if pd.isna(row.get('代號')): continue
        symbol = str(row['代號']).upper().strip()
        if not symbol: continue

        # 數值讀取
        try:
            qty = float(row.get('股數', 0))
            cost = float(row.get('買進價', 0))
        except:
            continue 

        if qty == 0: continue 

        try:
            # 抓取現價
            try:
                quote = api.get_latest_trade(symbol)
                current_price = quote.price
            except Exception as e1:
                try:
                    last_quote = api.get_latest_quote(symbol)
                    current_price = (last_quote.bid_price + last_quote.ask_price) / 2
                except Exception as e2:
                    error_logs.append(f"{symbol} 抓取失敗: {e2}")
                    continue 

            # 計算數值
            market_value = qty * current_price
            total_cost = qty * cost 
            profit_per_share = current_price - cost
            total_profit = market_value - total_cost
            roi_percent = (profit_per_share / cost * 100) if cost > 0 else 0.0

            results.append({
                '代號': symbol,
                '股數': qty,
                '買進價': cost,
                '個股買進總價': total_cost,
                '現價': current_price,
                '市值': market_value,
                '個股盈虧': profit_per_share,
                '總盈虧': total_profit,
                '報酬率 (%)': roi_percent
            })
        except Exception as e:
            error_logs.append(f"{symbol} 未知錯誤: {e}")
            pass 

    if results:
        df = pd.DataFrame(results)
        total_val = df['市值'].sum()
        df['比重 (%)'] = (df['市值'] / total_val) * 100 
        return df, total_val, error_logs
    else:
        return pd.DataFrame(), 0, error_logs

# ==========================================
# 主程式介面
# ==========================================
st.sidebar.header("🔍 股票篩