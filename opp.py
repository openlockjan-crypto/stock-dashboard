import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import matplotlib.colors as mcolors
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestTradeRequest, StockLatestQuoteRequest
from datetime import datetime
import json
import os
import colorsys
import requests 
import io

# --- 版本控制 ---
VERSION = "2.34 (Fix NameError: api_key)"
PORTFOLIO_FILE = "saved_portfolios.json"

# --- 設定網頁配置 ---
st.set_page_config(page_title="AI 投資決策中心", layout="wide")

# --- CSS 視覺優化 (標題字體修正) ---
st.markdown("""
<style>
    /* 1. 強制放大指標標題 (總資產價值) */
    [data-testid="stMetricLabel"] p, [data-testid="stMetricLabel"] div, [data-testid="stMetricLabel"] {
        font-size: 26px !important; 
        font-weight: 700 !important;
        color: #31333f !important;
    }
    
    /* 指標數值 (數字部分) */
    [data-testid="stMetricValue"] {
        font-size: 2.8rem !important;
    }

    /* 2. 表格字體優化 */
    div[data-testid="stDataFrame"] div[data-testid="stTable"] {
        font-size: 1.1rem !important; 
    }
    
    /* 縮減表格儲存格內邊距 */
    [data-testid="stTable"] td, [data-testid="stTable"] th {
        padding: 4px 8px !important;
    }

    /* 3. 手機版適配 */
    @media (max-width: 640px) {
        [data-testid="stMetricLabel"] p { font-size: 20px !important; }
        [data-testid="stMetricValue"] { font-size: 2.0rem !important; }
        div[data-testid="stDataFrame"] div[data-testid="stTable"] { font-size: 1.0rem !important; }
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 核心與存取函數
# ==========================================
def get_cloud_config():
    try:
        api_key = st.secrets["JSONBIN_API_KEY"]
        bin_id = st.secrets["JSONBIN_BIN_ID"]
        return api_key, bin_id
    except: return None, None

def load_saved_portfolios():
    api_key, bin_id = get_cloud_config()
    if not api_key or not bin_id: return {}
    url = f"https://api.jsonbin.io/v3/b/{bin_id}/latest"
    headers = {'X-Master-Key': api_key, 'Content-Type': 'application/json'}
    try:
        response = requests.get(url, headers=headers)
        return response.json().get('record', {}) if response.status_code == 200 else {}
    except: return {}

def save_portfolios_to_file(data_dict):
    api_key, bin_id = get_cloud_config()
    if not api_key or not bin_id:
        st.error("⚠️ 未設定 JSONBin Secrets")
        return
    url = f"https://api.jsonbin.io/v3/b/{bin_id}"
    headers = {'X-Master-Key': api_key, 'Content-Type': 'application/json'}
    try:
        requests.put(url, json=data_dict, headers=headers)
    except Exception as e:
        st.error(f"連線錯誤: {e}")

def generate_distinct_colors(n):
    colors = []
    for i in range(n):
        hue = i / n
        saturation = 0.6 + (i % 2) * 0.2 
        value = 0.9 - (i % 2) * 0.1
        rgb = colorsys.hsv_to_rgb(hue, saturation, value)
        hex_color = mcolors.to_hex(rgb)
        colors.append(hex_color)
    return colors

@st.cache_data
def get_stock_data(symbol):
    stock = yf.Ticker(symbol)
    info = stock.info
    hist = stock.history(period="5y")
    financials = stock.financials
    return info, hist, financials

def get_portfolio_data(api_key, secret_key, input_df):
    api_key = api_key.strip()
    secret_key = secret_key.strip()
    
    try:
        client = StockHistoricalDataClient(api_key, secret_key)
    except Exception as e:
        return pd.DataFrame(), 0, [f"API連線失敗: {e}"]
    
    results = []
    error_logs = []
    
    if input_df.empty: return pd.DataFrame(), 0, []
    input_df = input_df.reset_index(drop=True)

    for index, row in input_df.iterrows():
        if '移除' in row and row['移除'] == True: continue
        if pd.isna(row.get('代號')): continue
        symbol = str(row['代號']).upper().strip()
        if not symbol: continue

        try:
            qty = float(row.get('股數', 0))
            cost = float(row.get('買進價', 0))
        except: continue 
        if qty == 0: continue 

        try:
            current_price = 0
            try:
                req = StockLatestTradeRequest(symbol_or_symbols=symbol)
                res = client.get_stock_latest_trade(req)
                current_price = res[symbol].price
            except:
                try:
                    req = StockLatestQuoteRequest(symbol_or_symbols=symbol)
                    res = client.get_stock_latest_quote(req)
                    quote = res[symbol]
                    current_price = (quote.ask_price + quote.bid_price) / 2
                except Exception as e:
                    error_logs.append(f"{symbol}: {e}")
                    continue 

            market_value = qty * current_price
            total_cost = qty * cost 
            profit_per_share = current_price - cost
            total_profit = market_value - total_cost
            roi_percent = (profit_per_share / cost * 100) if cost > 0 else 0.0

            results.append({
                '原始索引': index,
                '代號': symbol, '股數': qty, '買進價': cost,
                '個股買進總價': total_cost, '現價': current_price, '市值': market_value,
                '個股盈虧': profit_per_share, '總盈虧': total_profit, '報酬率 (%)': roi_percent
            })
        except: pass 

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
st.sidebar.header("🔍 股票篩選")
ticker_input = st.sidebar.text_input("輸入美股代號 (例如: KO, AAPL, NVDA)", value="AAPL").upper()
analysis_btn = st.sidebar.button("開始分析")
st.sidebar.markdown("---")
st.sidebar.caption(f"App Version: {VERSION}")

tab1, tab2, tab3 = st.tabs(["📊 個股分析", "💰 DCF估值模型", "💼 資產管理儀表板"])

# ------------------------------------------------------------------
# 分頁 1: 個股分析 (完整保留)
# ------------------------------------------------------------------
with tab1:
    st.title(f"📈 {ticker_input} 投資決策中心")
    if analysis_btn or ticker_input:
        try:
            with st.spinner('分析數據中...'):
                info, hist, financials = get_stock_data(ticker_input)
                
                if hist.empty:
                    st.error("找不到該股票資料。")
                    st.stop()

                current_price = hist['Close'].iloc[-1]
                delta = current_price - hist['Close'].iloc[-2]
                
                col_a, col_b, col_c, col_d = st.columns(4)
                col_a.metric("目前股價", f"${current_price:.2f}", f"{delta:.2f}")
                col_b.metric("公司名稱", info.get('longName', 'N/A'))
                col_c.metric("產業", info.get('industry', 'N/A'))
                col_d.metric("Beta", f"{info.get('beta', 0):.2f}")

                st.subheader("🛡️ 企業體質評分 (Quality Score)")
                score = 0
                if info.get('returnOnEquity', 0) > 0.15: score += 20
                if info.get('operatingMargins', 0) > 0.10: score += 20
                if info.get('dividendRate', 0) > 0: score += 20
                if info.get('freeCashflow', 0) > 0: score += 20
                if info.get('grossMargins', 0) > 0.3: score += 20
                
                q_c1, q_c2 = st.columns([1,3])
                with q_c1:
                    if score >= 80: st.success(f"總分: {score} (優異)")
                    else: st.warning(f"總分: {score}")
                with q_c2:
                    st.caption("✅ ROE > 15% | ✅ 營益率 > 10% | ✅ 有配息 | ✅ 自由現金流 > 0 | ✅ 毛利率 > 30%")

        except Exception as e:
            st.error(f"錯誤: {e}")

# ------------------------------------------------------------------
# 分頁 2: DCF 估值模型 (完整保留)
# ------------------------------------------------------------------
with tab2:
    st.header(f"💰 {ticker_input} DCF 現金流折現估值模型")
    st.info("此模型採用「二階段成長」計算：前 5 年為第一階段，6-10 年為第二階段，最後計算終值。")

    try:
        stock_info = yf.Ticker(ticker_input).info
        default_fcf = stock_info.get('freeCashflow', 0) or 0
        default_cash = stock_info.get('totalCash', 0) or 0
        default_debt = stock_info.get('totalDebt', 0) or 0
        default_shares = stock_info.get('sharesOutstanding', 1) or 1
        default_price = stock_info.get('currentPrice', 0)
    except:
        default_fcf = 0; default_cash = 0; default_debt = 0; default_shares = 1; default_price = 0

    st.subheader("1️⃣ 參數設定 (可手動修改)")
    col_dcf1, col_dcf2 = st.columns(2)
    
    with col_dcf1:
        st.markdown("##### 📈 成長率與折現率")
        growth_rate_1_5 = st.number_input("未來成長率 (1~5年) %", value=10.0, step=0.1) / 100
        growth_rate_6_10 = st.number_input("二階成長率 (6~10年) %", value=5.0, step=0.1) / 100
        perpetual_rate = st.number_input("永久成長率 (終值) %", value=2.5, step=0.1) / 100
        discount_rate = st.number_input("折現率 (WACC) %", value=9.0, step=0.1) / 100

    with col_dcf2:
        st.markdown("##### 🏢 財務基礎數據 (自動帶入)")
        base_fcf = st.number_input("目前自由現金流 (FCF)", value=float(default_fcf), step=1000000.0, format="%.0f")
        cash_and_equiv = st.number_input("現金及約當現金", value=float(default_cash), step=1000000.0, format="%.0f")
        total_debt = st.number_input("總負債", value=float(default_debt), step=1000000.0, format="%.0f")
        shares_out = st.number_input("流通股數", value=float(default_shares), step=1000.0, format="%.0f")

    st.markdown("---")
    if st.button("開始 DCF 估值計算", type="primary"):
        future_fcf = []
        discount_factors = []
        discounted_fcf = []
        current_year = datetime.now().year
        years = []

        temp_fcf = base_fcf
        for i in range(1, 11):
            years.append(current_year + i)
            g = growth_rate_1_5 if i <= 5 else growth_rate_6_10
            temp_fcf = temp_fcf * (1 + g)
            future_fcf.append(temp_fcf)
            
            factor = (1 + discount_rate) ** i
            discount_factors.append(factor)
            discounted_fcf.append(temp_fcf / factor)

        if discount_rate <= perpetual_rate:
            st.error("錯誤：折現率 (WACC) 必須大於永久成長率。")
        else:
            terminal_value = future_fcf[-1] * (1 + perpetual_rate) / (discount_rate - perpetual_rate)
            terminal_value_discounted = terminal_value / ((1 + discount_rate) ** 10)

            enterprise_value = sum(discounted_fcf) + terminal_value_discounted
            equity_value = enterprise_value + cash_and_equiv - total_debt
            fair_value_per_share = equity_value / shares_out
            
            margin_of_safety = 0
            if default_price > 0:
                margin_of_safety = (fair_value_per_share - default_price) / default_price * 100

            st.subheader("2️⃣ 估值結果 (Valuation Result)")
            res_col1, res_col2, res_col3 = st.columns(3)
            res_col1.metric("計算出的合理價", f"${fair_value_per_share:.2f}")
            res_col2.metric("目前市場股價", f"${default_price:.2f}")
            color = "normal" if margin_of_safety > 0 else "off"
            res_col3.metric("潛在漲幅 / 溢價", f"{margin_of_safety:.2f}%", delta_color=color)

            st.subheader("3️⃣ 詳細現金流預估表")
            dcf_data = {
                "年份": years,
                "預估 FCF (百萬)": [f"${x/1000000:,.0f}" for x in future_fcf],
                "折現後 FCF (百萬)": [f"${x/1000000:,.0f}" for x in discounted_fcf]
            }
            st.dataframe(pd.DataFrame(dcf_data), use_container_width=True)

# ------------------------------------------------------------------
# 分頁 3: 資產管理儀表板 (V2.34 Fix NameError)
# ------------------------------------------------------------------
with tab3:
    st.header("🚀 資產管理儀表板")
    try:
        api_key = st.secrets["ALPACA_API_KEY"]
        secret_key = st.secrets["ALPACA_SECRET_KEY"]
    except:
        st.error("⚠️ 請先設定 .streamlit/secrets.toml")
        st.stop()

    # 初始化 State
    if 'my_portfolio_data' not in st.session_state:
        st.session_state.my_portfolio_data = pd.DataFrame([{'代號': 'NVDA', '股數': 10.0, '買進價': 120.0, '移除': False}])
    if 'my_cash_balance' not in st.session_state: 
        st.session_state.my_cash_balance = 0.0 # Float
    
    # 補強: 確保計算按鈕需要的變數存在
    if 'portfolio_df' not in st.session_state: 
        st.session_state.portfolio_df = None
    if 'total_val' not in st.session_state: 
        st.session_state.total_val = 0.0

    if '移除' not in st.session_state.my_portfolio_data.columns:
        st.session_state.my_portfolio_data['移除'] = False

    # 1. 備份與雲端
    saved_portfolios = load_saved_portfolios()
    with st.expander("☁️ 雲端 / 📂 本地備份與還原", expanded=False):
        c_cl, c_lo = st.tabs(["雲端群組", "本地備份"])
        with c_cl:
            col1, col2 = st.columns(2)
            if saved_portfolios:
                sel = col1.selectbox("選擇群組", list(saved_portfolios.keys()))
                if col1.button("📂 載入"):
                    data = saved_portfolios[sel]
                    st.session_state.my_portfolio_data = pd.DataFrame(data["portfolio"] if isinstance(data, dict) else data)
                    st.session_state.my_cash_balance = float(data.get("cash", 0.0)) if isinstance(data, dict) else 0.0
                    st.rerun()
            name = col2.text_input("存檔名稱")
            if col2.button("💾 上傳"):
                save_portfolios_to_file({**saved_portfolios, name: {"cash": st.session_state.my_cash_balance, "portfolio": st.session_state.my_portfolio_data.to_dict('records')}})
                st.toast("已上傳"); st.rerun()
        
        with c_lo:
            col_l1, col_l2 = st.columns(2)
            with col_l1:
                st.markdown("#### 📥 下載備份")
                backup_data = {
                    "cash": st.session_state.my_cash_balance,
                    "portfolio": st.session_state.my_portfolio_data.to_dict('records'),
                    "timestamp": str(datetime.now())
                }
                st.download_button("📥 下載目前設定 (.json)", json.dumps(backup_data, indent=4), "backup.json", "application/json")
            with col_l2:
                st.markdown("#### 📤 還原備份")
                uploaded_file = st.file_uploader("上傳備份檔", type=["json"])
                if uploaded_file and st.button("✅ 按此還原"):
                    try:
                        restored = json.load(uploaded_file)
                        st.session_state.my_portfolio_data = pd.DataFrame(restored.get("portfolio", restored))
                        st.session_state.my_cash_balance = float(restored.get("cash", 0.0))
                        st.rerun()
                    except: st.error("格式錯誤")

    # 2. 現金與新增
    col_c, _ =