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
VERSION = "2.30 (Fix Crash & Force Font Size)"
PORTFOLIO_FILE = "saved_portfolios.json"

# --- 設定網頁配置 ---
st.set_page_config(page_title="AI 投資決策中心", layout="wide")

# --- CSS 視覺優化 (V2.30 強力修正) ---
st.markdown("""
<style>
    /* 1. 強制放大指標標題 (總資產價值) */
    /* 針對 Streamlit 的 Metric Label 進行多重鎖定，確保變大 */
    [data-testid="stMetricLabel"] {
        font-size: 26px !important; 
        font-weight: 700 !important;
        color: #31333f !important;
    }
    [data-testid="stMetricLabel"] p {
        font-size: 26px !important;
        font-weight: 700 !important;
    }
    
    /* 指標數值 (數字部分) */
    [data-testid="stMetricValue"] {
        font-size: 2.8rem !important;
    }

    /* 2. 表格間距縮小與字體優化 */
    div[data-testid="stDataFrame"] div[data-testid="stTable"] {
        font-size: 1.05rem !important; 
    }
    
    /* 縮減表格儲存格內邊距 */
    [data-testid="stTable"] td, [data-testid="stTable"] th {
        padding: 4px 8px !important;
    }

    /* 3. 手機版適配 */
    @media (max-width: 640px) {
        /* 手機上標題稍微縮小一點以免換行 */
        [data-testid="stMetricLabel"] { font-size: 20px !important; }
        [data-testid="stMetricLabel"] p { font-size: 20px !important; }
        [data-testid="stMetricValue"] { font-size: 2.0rem !important; }
        div[data-testid="stDataFrame"] div[data-testid="stTable"] { font-size: 0.95rem !important; }
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 核心與存取函數 (保持 V2.28 穩定架構)
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
    if not api_key or not bin_id: return
    url = f"https://api.jsonbin.io/v3/b/{bin_id}"
    headers = {'X-Master-Key': api_key, 'Content-Type': 'application/json'}
    requests.put(url, json=data_dict, headers=headers)

def generate_distinct_colors(n):
    colors = []
    for i in range(n):
        rgb = colorsys.hsv_to_rgb(i/n, 0.65, 0.85)
        colors.append(mcolors.to_hex(rgb))
    return colors

@st.cache_data
def get_stock_data(symbol):
    stock = yf.Ticker(symbol)
    return stock.info, stock.history(period="5y"), stock.financials

def get_portfolio_data(api_key, secret_key, input_df):
    try:
        client = StockHistoricalDataClient(api_key.strip(), secret_key.strip())
    except: return pd.DataFrame(), 0, ["API連線失敗"]
    
    results = []
    error_logs = []
    if input_df.empty: return pd.DataFrame(), 0, []
    input_df = input_df.reset_index(drop=True)

    for index, row in input_df.iterrows():
        if row.get('移除', False) or pd.isna(row.get('代號')): continue
        symbol = str(row['代號']).upper().strip()
        try:
            qty, cost = float(row.get('股數', 0)), float(row.get('買進價', 0))
            if qty == 0: continue
            try:
                res = client.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=symbol))
                current_price = res[symbol].price
            except:
                res = client.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=symbol))
                current_price = (res[symbol].ask_price + res[symbol].bid_price) / 2
            
            market_value = qty * current_price
            results.append({
                '原始索引': index, '代號': symbol, '股數': qty, '買進價': cost,
                '個股買進總價': qty * cost, '現價': current_price, '市值': market_value,
                '個股盈虧': current_price - cost, '總盈虧': market_value - (qty * cost),
                '報酬率 (%)': ((current_price - cost) / cost * 100) if cost > 0 else 0.0
            })
        except: pass 

    if results:
        df = pd.DataFrame(results)
        total_v = df['市值'].sum()
        df['比重 (%)'] = (df['市值'] / total_v) * 100 
        return df, total_v, error_logs
    return pd.DataFrame(), 0, error_logs

# ==========================================
# 主程式介面
# ==========================================
st.sidebar.header("🔍 股票篩選")
ticker_input = st.sidebar.text_input("輸入美股代號", value="AAPL").upper()
analysis_btn = st.sidebar.button("開始分析")
st.sidebar.markdown("---")
st.sidebar.caption(f"App Version: {VERSION}")

tab1, tab2, tab3 = st.tabs(["📊 個股分析", "💰 DCF估值模型", "💼 資產管理儀表板"])

# --- Tab 1 & 2 ---
with tab1:
    st.title(f"📈 {ticker_input} 決策中心")
    if analysis_btn or ticker_input:
        try:
            info, hist, _ = get_stock_data(ticker_input)
            cur_p = hist['Close'].iloc[-1]
            c1, c2, c3 = st.columns(3)
            c1.metric("目前股價", f"${cur_p:.2f}")
            c2.metric("公司名稱", info.get('longName', 'N/A'))
            c3.metric("產業", info.get('industry', 'N/A'))
        except: st.error("查無資料")

with tab2:
    st.header("💰 DCF 估值模型")
    st.info("請於分頁 3 設定好資產後，此處將自動連動。")

# --- Tab 3: 模擬庫存 (V2.30 Fix) ---
with tab3:
    st.header("🚀 資產管理儀表板")
    try:
        api_k, sec_k = st.secrets["ALPACA_API_KEY"], st.secrets["ALPACA_SECRET_KEY"]
    except: st.error("請設定 Secrets"); st.stop()

    if 'my_portfolio_data' not in st.session_state:
        st.session_state.my_portfolio_data = pd.DataFrame([{'代號': 'NVDA', '股數': 10.0, '買進價': 120.0, '移除': False}])
    if 'my_cash_balance' not in st.session_state: st.session_state.my_cash_balance = 0.0

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
                    st.session_state.my_cash_balance = float(data.get("cash", 0)) if isinstance(data, dict) else 0
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
    col_c, _ = st.columns([2,3])
    st.session_state.my_cash_balance = col_c.number_input("💵 現金 (USD)", min_value=0.0, step=100.0, value=st.session_state.my_cash_balance)

    with st.expander("➕ 新增股票", expanded=False):
        c1, c2, c3, c4 = st.columns([1.5, 1.5, 1.5, 1])
        s = c1.text_input("代號").upper().strip()
        q = c2.number_input("股數", min_value=0.0, step=1.0)
        p = c3.number_input("價格", min_value=0.0, step=0.1)
        if c4.button("新增", type="primary") and s:
            st.session_state.my_portfolio_data = pd.concat([st.session_state.my_portfolio_data, pd.DataFrame([{'代號': s, '股數': q, '買進價': p, '移除': False}])], ignore_index=True)
            st.rerun()

    # 3. 庫存清單
    with st.expander("📋 庫存清單 (編輯/刪除)", expanded=False):
        edited = st.data_editor(
            st.session_state.my_portfolio_data,
            use_container_width=True,
            column_config={
                "代號": st.column_config.TextColumn(width="small"),
                "股數": st.column_config.NumberColumn(width="small"),
                "買進價": st.column_config.NumberColumn(width="small"),
            },
            key="p_editor"
        )
        if st.button("🗑️ 刪除勾選"):
            st.session_state.my_portfolio_data = edited[~edited['移除']].reset_index(drop=True)
            st.rerun()

    # 4. 計算與報表
    if st.button("🔄 刷新即時報價", type="primary", use_container_width=True):
        df, total_s, errs = get_portfolio_data(api_k, sec_k, st.session_state.my_portfolio_data)
        st.session_state.portfolio_df, st.session_state.total_val = df, total_s

    if 'portfolio_df' in st.session_state and not st.session_state.portfolio_df.empty:
        df = st.session_state.portfolio_df.copy()
        cash = st.session_state.my_cash_balance
        total_a = st.session_state.total_val + cash
        
        st.markdown("---")
        # Metric 標題已經被 CSS 強制放大了
        st.metric("💰 總資產價值 (股票+現金)", f"${total_a:,.2f}", delta=f"現金: ${cash:,.2f}")
        
        # --- (A) 互動圓餅圖 ---
        st.subheader("📊 資產分佈")
        mode = st.radio("模式", ["依代號合併 (Merge)", "依分批明細 (Detail)"], horizontal=True, label_visibility="collapsed")
        
        plot_df = df.groupby('代號')['市值'].sum().reset_index() if mode == "依代號合併 (Merge)" else df.copy()
        plot_df['Label'] = plot_df['代號']
        if cash > 0: plot_df = pd.concat([plot_df, pd.DataFrame([{'Label': 'CASH', '市值': cash}])], ignore_index=True)
        
        colors = generate_distinct_colors(len(plot_df))
        color_map = dict(zip(plot_df['Label'], colors))
        color_map['CASH'] = '#85bb65'

        fig = go.Figure(data=[go.Pie(
            labels=plot_df['Label'], values=plot_df['市值'],
            text=[f"{l}<br>{(v/total_a*100):.1f}%" if (v/total_a*100) >= 1 else "" for l, v in zip(plot_df['Label'], plot_df['市值'])],
            textinfo='text', hoverinfo='label+percent+value',
            marker=dict(colors=[color_map[x] for x in plot_df['Label']], line=dict(color='#000000', width=1))
        )])
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), legend=dict(orientation="h", y=-0.1))
        st.plotly_chart(fig, use_container_width=True)

        # --- (B) 詳細損益清單 ---
        st.subheader("📋 詳細損益清單")
        
        mobile_cols = ['代號', '買進價', '現價', '總盈虧', '報酬率 (%)']
        all_cols = ['代號', '股數', '買進價', '個股買進總價', '現價', '市值', '總盈虧', '報酬率 (%)']
        
        with st.expander("⚙️ 顯示設定", expanded=False):
            is_m = st.toggle("📱 手機精簡模式", value=True)
            sel_cols = st.multiselect("顯示欄位", options=all_cols, default=mobile_cols if is_m else all_cols)
        
        if not sel_cols: sel_cols = ['代號']
        
        def row_style(row):
            key = row['代號'] if mode == "依代號合併 (Merge)" else str(row['原始索引'])
            c = color_map.get(row['代號'], '#ffffff')
            styles = []
            for col in row.index:
                s = ''
                if col == '代號': s += f'background-color: {c}; color: black; font-weight: bold;'
                if col in mobile_cols: s += 'font-weight: bold;'
                styles.append(s)
            return styles

        # [V2.30 修復] 確保 final_cols 變數存在，避免崩潰
        # 這裡根據使用者選的欄位，重新排列順序 (優先顯示買進價)
        user_order = [c for c in sel_cols if c != '代號']
        final_cols = ['代號'] + user_order

        # 顯示表格
        st.dataframe(
            df[list(set(sel_cols + ['代號', '原始索引']))].style
            .format({'股數': '{:.2f}', '買進價': '${:.2f}', '現價': '${:.2f}', '總盈虧': '${:.2f}', '報酬率 (%)': '{:.2f}%', '市值': '${:,.0f}'})
            .apply(row_style, axis=1)
            .map(lambda x: 'color: #ff3333; font-weight: bold', subset=[c for c in ['買進價'] if c in final_cols])
            .map(lambda x: 'color: #ff3333' if isinstance(x,(int,float)) and x>0 else 'color: #00cc00' if isinstance(x,(int,float)) and x<0 else '', subset=[c for c in ['總盈虧', '報酬率 (%)'] if c in final_cols]),
            column_order=final_cols,
            use_container_width=True,
            column_config={
                "代號": st.column_config.TextColumn(width="small"),
                "買進價": st.column_config.NumberColumn(width="small"),
                "現價": st.column_config.NumberColumn(width="small"),
                "總盈虧": st.column_config.NumberColumn(width="small"),
                "報酬率 (%)": st.column_config.NumberColumn(width="small"),
            }
        )

    elif st.session_state.portfolio_df is None:
        st.info("👋 請點擊上方「刷新即時報價」按鈕來載入資料。")