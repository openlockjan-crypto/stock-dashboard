import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from alpaca_trade_api.rest import REST

# --- 設定網頁配置 ---
st.set_page_config(page_title="AI 投資決策中心", layout="wide")

# ==========================================
# 核心函數
# ==========================================

# 1. 取得個股資料 (含 yfinance 錯誤處理)
@st.cache_data(ttl=300) # 加入快取時間
def get_stock_data(symbol):
    try:
        stock = yf.Ticker(symbol)
        # 嘗試使用 fast_info，有時候比 history 穩定
        price = stock.fast_info.get('last_price', None)
        
        info = stock.info
        hist = stock.history(period="5y")
        financials = stock.financials
        
        return info, hist, financials
    except Exception as e:
        return None, pd.DataFrame(), pd.DataFrame()

# 2. 取得 Alpaca 庫存資料 (修正版：顯示錯誤原因)
def get_portfolio_data(api_key, secret_key):
    # 自動去除前後空白，防止複製錯誤
    api_key = api_key.strip()
    secret_key = secret_key.strip()
    
    # 連線設定
    try:
        api = REST(api_key, secret_key, base_url='https://paper-api.alpaca.markets')
        # 測試連線：隨便抓一檔股票看看能不能通
        api.get_clock() 
    except Exception as e:
        st.error(f"❌ API 連線失敗！請檢查 Key 是否正確。錯誤訊息：{e}")
        return pd.DataFrame(), 0

    # --- 你的持股清單 ---
    portfolio_data = [
        {'symbol': 'AAL',   'qty': 100,   'avg_cost': 0.0},
        {'symbol': 'GOOGL', 'qty': 30,    'avg_cost': 0.0},
        {'symbol': 'GRAB',  'qty': 200,   'avg_cost': 4.0},
        {'symbol': 'NVDA',  'qty': 40,    'avg_cost': 0.0},
        {'symbol': 'TSLA',  'qty': 20,    'avg_cost': 0.0},
        {'symbol': 'LULU',  'qty': 40,    'avg_cost': 0.0},
        {'symbol': 'PLTR',  'qty': 50,    'avg_cost': 0.0}, # 範例增加
    ]

    results = []
    errors = [] # 收集錯誤訊息
    
    # 開始計算
    for item in portfolio_data:
        symbol = item['symbol']
        qty = item['qty']
        cost = item['avg_cost']

        try:
            # 嘗試取得最新成交價
            current_price = 0
            try:
                # 方法 A: 取得最新交易 (可能延遲)
                trade = api.get_latest_trade(symbol)
                current_price = trade.price
            except:
                # 方法 B: 如果 A 失敗，改抓快照 (Snapshot)
                try:
                    snapshot = api.get_snapshot(symbol)
                    current_price = snapshot.latest_trade.price
                except Exception as inner_e:
                    errors.append(f"{symbol}: {inner_e}")
                    continue # 跳過這檔

            if current_price > 0:
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
            errors.append(f"{symbol} 發生未知錯誤: {e}")

    # 如果全部失敗，顯示第一個錯誤給使用者看
    if not results and errors:
        st.error(f"⚠️ 無法取得報價，原因範例：{errors[0]}")
        if "403" in str(errors[0]):
            st.warning("提示：403 錯誤通常代表 API Key 權限不足，或是您的 Alpaca 免費帳戶沒有即時數據權限。")
    
    if results:
        df = pd.DataFrame(results)
        total_val = df['市值'].sum()
        df['比重 (%)'] = (df['市值'] / total_val) * 100
        return df, total_val
    else:
        return pd.DataFrame(), 0

# ==========================================
# 主程式介面
# ==========================================
st.sidebar.header("🔍 股票篩選")
ticker_input = st.sidebar.text_input("輸入美股代號", value="AAPL").upper()
analysis_btn = st.sidebar.button("開始分析")

tab1, tab2 = st.tabs(["📊 個股分析", "💼 模擬庫存"])

# --- 分頁 1: 個股分析 ---
with tab1:
    st.title(f"📈 {ticker_input} 投資決策中心")
    if analysis_btn or ticker_input:
        with st.spinner('分析數據中...'):
            info, hist, financials = get_stock_data(ticker_input)
            
            if hist is None or hist.empty:
                st.warning("⚠️ 無法取得資料 (可能是 Yahoo Finance 暫時阻擋，請稍後再試)")
            else:
                # 顯示基本資訊
                price = hist['Close'].iloc[-1]
                st.metric("目前股價", f"${price:.2f}")
                st.line_chart(hist['Close'])
                
                # 品質分數 (範例邏輯)
                st.subheader("🛡️ 企業體質評分")
                score = 0
                if info.get('returnOnEquity', 0) > 0.15: score += 20
                if info.get('operatingMargins', 0) > 0.10: score += 20
                st.progress(score, text=f"總分: {score} 分")

# --- 分頁 2: 模擬庫存 ---
with tab2:
    st.header("🚀 股票監控儀表板")
    
    # 讀取 Secrets
    try:
        api_key = st.secrets["ALPACA_API_KEY"]
        secret_key = st.secrets["ALPACA_SECRET_KEY"]
    except:
        st.error("⚠️ 請先設定 .streamlit/secrets.toml")
        st.stop()

    if st.button("🔄 刷新即時報價", type="primary"):
        with st.spinner("連線 Alpaca 抓取最新股價..."):
            df, total_val = get_portfolio_data(api_key, secret_key)
            
            if not df.empty:
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.metric("💰 總資產價值", f"${total_val:,.2f}")
                    
                    # 圓餅圖
                    fig, ax = plt.subplots()
                    plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans'] # 雲端通用字體
                    ax.pie(df['比重 (%)'], labels=df['代號'], autopct='%1.1f%%', startangle=90)
                    ax.axis('equal')
                    st.pyplot(fig)
                
                with col2:
                    # 樣式設定
                    format_mapping = {
                        '買進價': '${:.2f}', '個股買進總價': '${:,.2f}',
                        '現價': '${:.2f}', '市值': '${:,.0f}',
                        '個股盈虧': '${:.2f}', '總盈虧': '${:.2f}',
                        '報酬率 (%)': '{:.2f}%', '比重 (%)': '{:.2f}%'
                    }
                    def highlight(val):
                        if isinstance(val, (int, float)):
                            return 'color: #ff4b4b' if val > 0 else 'color: #09ab3b'
                        return ''
                        
                    st.dataframe(
                        df.style.format(format_mapping).map(highlight, subset=['總盈虧', '報酬率 (%)']),
                        use_container_width=True,
                        height=500
                    )
            else:
                st.info("💡 提示：如果看到連線失敗，請確認 Secrets 中的 Key 是否有多餘空白，或是否為 PK 開頭。")