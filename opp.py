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
VERSION = "2.26 (Asset Mgmt & Local Backup)"
PORTFOLIO_FILE = "saved_portfolios.json"

# --- 設定網頁配置 (包含 CSS 字體放大優化) ---
st.set_page_config(page_title="AI 投資決策中心", layout="wide")

# CSS: 強制放大表格字體
st.markdown("""
<style>
    /* 放大 dataframe 的字體 */
    div[data-testid="stDataFrame"] div[data-testid="stTable"] {
        font-size: 1.1rem !important; 
    }
    /* 手機版優化 */
    @media (max-width: 640px) {
        div[data-testid="stDataFrame"] div[data-testid="stTable"] {
            font-size: 1.0rem !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 雲端存取函數
# ==========================================
def get_cloud_config():
    try:
        api_key = st.secrets["JSONBIN_API_KEY"]
        bin_id = st.secrets["JSONBIN_BIN_ID"]
        return api_key, bin_id
    except:
        return None, None

def load_saved_portfolios():
    api_key, bin_id = get_cloud_config()
    if not api_key or not bin_id: return {}
    url = f"https://api.jsonbin.io/v3/b/{bin_id}/latest"
    headers = {'X-Master-Key': api_key, 'Content-Type': 'application/json'}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json().get('record', {})
        else: return {}
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

# ==========================================
# 核心函數
# ==========================================
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

# --- Tab 1 ---
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

# --- Tab 2 ---
with tab2:
    st.header(f"💰 {ticker_input} DCF 現金流折現估值模型")
    st.info("此模型採用「二階段成長」計算。")
    try:
        stock_info = yf.Ticker(ticker_input).info
        default_fcf = stock_info.get('freeCashflow', 0) or 0
        default_cash = stock_info.get('totalCash', 0) or 0
        default_debt = stock_info.get('totalDebt', 0) or 0
        default_shares = stock_info.get('sharesOutstanding', 1) or 1
        default_price = stock_info.get('currentPrice', 0)
    except:
        default_fcf = 0; default_cash = 0; default_debt = 0; default_shares = 1; default_price = 0
    st.subheader("1️⃣ 參數設定")
    col_dcf1, col_dcf2 = st.columns(2)
    with col_dcf1:
        growth_rate_1_5 = st.number_input("未來成長率 (1~5年) %", value=10.0, step=0.1) / 100
        growth_rate_6_10 = st.number_input("二階成長率 (6~10年) %", value=5.0, step=0.1) / 100
        perpetual_rate = st.number_input("永久成長率 (終值) %", value=2.5, step=0.1) / 100
        discount_rate = st.number_input("折現率 (WACC) %", value=9.0, step=0.1) / 100
    with col_dcf2:
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
            st.subheader("2️⃣ 估值結果")
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

# --- Tab 3: 模擬庫存 (V2.26 Asset Mgmt) ---
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
        st.session_state.my_portfolio_data = pd.DataFrame([
            {'代號': 'NVDA', '股數': 100.0, '買進價': 120.0, '移除': False},
            {'代號': 'TSLA', '股數': 50.0,  '買進價': 180.0, '移除': False},
        ])
    if 'my_cash_balance' not in st.session_state:
        st.session_state.my_cash_balance = 0.0

    if '移除' not in st.session_state.my_portfolio_data.columns:
        st.session_state.my_portfolio_data['移除'] = False

    # ----------------------------------------------------
    # 1. 雲端與本地備份區
    # ----------------------------------------------------
    try:
        saved_portfolios = load_saved_portfolios()
    except: saved_portfolios = {}

    with st.expander("☁️ 雲端 / 📂 本地備份與還原 (點擊展開)", expanded=False):
        tab_cloud, tab_local = st.tabs(["☁️ 雲端群組", "📥 本地備份與還原"])
        
        # 雲端分頁
        with tab_cloud:
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                if saved_portfolios:
                    selected_group = st.selectbox("選擇群組", list(saved_portfolios.keys()))
                    c_btn1, c_btn2 = st.columns(2)
                    if c_btn1.button("📂 載入群組"):
                        # 載入邏輯: 兼容舊版與新版(含現金)
                        data_pack = saved_portfolios[selected_group]
                        
                        # 判斷是否為新版結構
                        if isinstance(data_pack, dict) and "portfolio" in data_pack:
                            loaded_df = pd.DataFrame(data_pack["portfolio"])
                            st.session_state.my_cash_balance = float(data_pack.get("cash", 0.0))
                        else:
                            # 舊版純 list
                            loaded_df = pd.DataFrame(data_pack)
                            st.session_state.my_cash_balance = 0.0
                        
                        loaded_df['股數'] = loaded_df['股數'].astype(float)
                        loaded_df['買進價'] = loaded_df['買進價'].astype(float)
                        if '移除' not in loaded_df.columns: loaded_df['移除'] = False
                        st.session_state.my_portfolio_data = loaded_df
                        st.toast(f"已載入：{selected_group}")
                        st.rerun()
                    
                    if c_btn2.button("🗑️ 刪除群組"):
                        del saved_portfolios[selected_group]
                        save_portfolios_to_file(saved_portfolios)
                        st.toast(f"已刪除：{selected_group}")
                        st.rerun()
                else: st.info("雲端無存檔")

            with col_c2:
                save_name = st.text_input("存檔名稱", placeholder="例如: 科技股+現金")
                if st.button("💾 上傳雲端"):
                    if save_name:
                        # 儲存結構: { "cash": 1000, "portfolio": [...] }
                        save_data = {
                            "cash": st.session_state.my_cash_balance,
                            "portfolio": st.session_state.my_portfolio_data.to_dict('records')
                        }
                        saved_portfolios[save_name] = save_data
                        save_portfolios_to_file(saved_portfolios)
                        st.toast(f"✅ 已上傳：{save_name}")
                        st.rerun()
                    else: st.error("請輸入名稱")

        # 本地備份分頁
        with tab_local:
            col_l1, col_l2 = st.columns(2)
            with col_l1:
                st.markdown("#### 📥 下載備份")
                # 準備下載資料
                backup_data = {
                    "cash": st.session_state.my_cash_balance,
                    "portfolio": st.session_state.my_portfolio_data.to_dict('records'),
                    "timestamp": str(datetime.now())
                }
                json_str = json.dumps(backup_data, indent=4, ensure_ascii=False)
                st.download_button(
                    label="📥 下載目前設定 (.json)",
                    data=json_str,
                    file_name="my_portfolio_backup.json",
                    mime="application/json"
                )
                st.info("💡 建議定期下載，若雲端故障可使用此檔案還原。")

            with col_l2:
                st.markdown("#### 📤 還原備份")
                uploaded_file = st.file_uploader("上傳備份檔", type=["json"])
                if uploaded_file is not None:
                    try:
                        restored_data = json.load(uploaded_file)
                        if st.button("✅ 成功讀取檔案，按此還原"):
                            # 還原邏輯
                            if "portfolio" in restored_data:
                                st.session_state.my_portfolio_data = pd.DataFrame(restored_data["portfolio"])
                                st.session_state.my_cash_balance = float(restored_data.get("cash", 0.0))
                            else:
                                # 兼容純 list 結構
                                st.session_state.my_portfolio_data = pd.DataFrame(restored_data)
                                st.session_state.my_cash_balance = 0.0
                            
                            st.toast("✅ 還原成功！")
                            st.rerun()
                    except Exception as e:
                        st.error(f"檔案格式錯誤: {e}")

    st.markdown("---")

    # 2. 持股與現金 (摺疊新增)
    col_cash_disp, col_dummy = st.columns([2, 3])
    with col_cash_disp:
        # 顯示並編輯現金
        st.session_state.my_cash_balance = st.number_input(
            "💵 現金餘額 (USD)", 
            min_value=0.0, 
            step=100.0, 
            value=st.session_state.my_cash_balance,
            format="%.2f",
            help="此金額將納入圓餅圖與總資產計算"
        )

    with st.expander("➕ 新增股票 (點擊展開)", expanded=False):
        with st.container():
            c1, c2, c3, c4 = st.columns([1.5, 1.5, 1.5, 1])
            new_symbol = c1.text_input("股票代號", placeholder="例如 GOOGL").upper().strip()
            new_qty = c2.number_input("股數", min_value=0.0, step=0.1, format="%.3f")
            new_cost = c3.number_input("買進價", min_value=0.0, step=0.1, format="%.2f")
            c4.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            
            if c4.button("新增", type="primary"):
                if new_symbol and new_qty > 0:
                    df = st.session_state.my_portfolio_data
                    new_row = pd.DataFrame([{'代號': new_symbol, '股數': new_qty, '買進價': new_cost, '移除': False}])
                    st.session_state.my_portfolio_data = pd.concat([df, new_row], ignore_index=True)
                    st.toast(f"✅ 已新增 {new_symbol}")
                    st.rerun()
                else: st.toast("⚠️ 輸入錯誤", icon="⚠️")

    # 3. 庫存清單 (摺疊)
    with st.expander("📋 目前庫存清單 (點擊展開編輯)", expanded=False):
        col_list, col_del = st.columns([4, 1])
        with col_list:
            edited_df = st.data_editor(
                st.session_state.my_portfolio_data,
                num_rows="fixed",
                use_container_width=True,
                column_config={
                    "代號": st.column_config.TextColumn("代號", disabled=True),
                    "股數": st.column_config.NumberColumn("股數", format="%.3f"),
                    "買進價": st.column_config.NumberColumn("買進價", format="$%.2f"),
                    "移除": st.column_config.CheckboxColumn("移除/賣出", default=False)
                },
                key="portfolio_editor"
            )
            st.session_state.my_portfolio_data = edited_df

        with col_del:
            st.write("")
            st.write("") 
            if st.button("🗑️ 刪除已勾選"):
                current_df = st.session_state.my_portfolio_data
                if '移除' in current_df.columns:
                    new_df = current_df[~current_df['移除']].copy()
                    new_df['移除'] = False
                    new_df.reset_index(drop=True, inplace=True)
                    st.session_state.my_portfolio_data = new_df
                    st.rerun()

    # 4. 計算按鈕
    st.markdown("---")
    if 'portfolio_df' not in st.session_state: st.session_state.portfolio_df = None
    if 'total_val' not in st.session_state: st.session_state.total_val = 0

    if st.button("🔄 刷新即時報價", type="primary", use_container_width=True):
        with st.spinner("連線計算中..."):
            df, total_val, errs = get_portfolio_data(api_key, secret_key, st.session_state.my_portfolio_data)
            st.session_state.portfolio_df = df
            st.session_state.total_val = total_val
            if errs: st.toast(f"部分失敗: {len(errs)}", icon="⚠️")

    # 5. 報表顯示
    if st.session_state.portfolio_df is not None and not st.session_state.portfolio_df.empty:
        df = st.session_state.portfolio_df.copy()
        
        # [V2.26] 加入現金計算總資產
        cash = st.session_state.my_cash_balance
        stock_val = st.session_state.total_val
        total_assets = stock_val + cash
        
        st.markdown("---")
        # 顯示 股票市值 + 現金 = 總資產
        st.metric("💰 總資產價值 (股票+現金)", f"${total_assets:,.2f}", delta=f"現金: ${cash:,.2f}")
        
        # --- (A) 上方：互動圖表區 ---
        st.subheader("📊 資產分佈")
        chart_mode = st.radio("圖表模式", ["依代號合併 (Merge)", "依分批明細 (Detail)"], horizontal=True, label_visibility="collapsed")
        
        # 數據準備
        if chart_mode == "依代號合併 (Merge)":
            plot_df = df.groupby('代號')['市值'].sum().reset_index()
            plot_df['Label'] = plot_df['代號']
            df['ColorKey'] = df['代號'] 
        else:
            plot_df = df.copy()
            plot_df['Label'] = plot_df['代號'] 
            df['ColorKey'] = df['原始索引'].astype(str)
            plot_df['ColorKey'] = plot_df['原始索引'].astype(str)

        # [V2.26] 插入現金到圖表數據
        if cash > 0:
            cash_row = pd.DataFrame([{'Label': 'CASH', '市值': cash, 'ColorKey': 'CASH'}])
            plot_df = pd.concat([plot_df, cash_row], ignore_index=True)

        # 計算百分比
        plot_df['Percent_Val'] = (plot_df['市值'] / total_assets) * 100
        
        # 智慧標籤
        def make_smart_label(row):
            if row['Percent_Val'] >= 1.0:
                return f"{row['Label']}<br>{row['Percent_Val']:.1f}%"
            return ""

        plot_df['Display_Text'] = plot_df.apply(make_smart_label, axis=1)

        # 顏色準備
        unique_keys = plot_df['Label'].unique() if chart_mode == "依代號合併 (Merge)" else plot_df['ColorKey'].unique()
        color_list = generate_distinct_colors(len(unique_keys))
        color_map_dict = dict(zip(unique_keys, color_list))
        
        # 強制指定 CASH 顏色 (例如灰色或綠色)
        color_map_dict['CASH'] = '#85bb65' # Money Green

        chart_colors = []
        for _, row in plot_df.iterrows():
            key = row['Label'] if chart_mode == "依代號合併 (Merge)" else row['ColorKey']
            # 如果是 CASH，直接用 CASH key，否則查表
            if row['Label'] == 'CASH':
                chart_colors.append(color_map_dict['CASH'])
            else:
                chart_colors.append(color_map_dict.get(key, '#dddddd'))

        # 建立 Plotly
        fig = go.Figure(data=[go.Pie(
            labels=plot_df['Label'],
            values=plot_df['市值'],
            text=plot_df['Display_Text'],
            textinfo='text',
            hoverinfo='label+percent+value',
            marker=dict(colors=chart_colors, line=dict(color='#000000', width=1)),
            sort=False
        )])
        
        fig.update_layout(
            margin=dict(t=0, b=0, l=0, r=0),
            showlegend=True,
            legend=dict(orientation="h", y=-0.1)
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # --- (B) 下方：報表區 ---
        st.subheader("📋 詳細損益清單")

        with st.expander("⚙️ 顯示設定 (欄位與手機模式)", expanded=False):
            all_columns = ['代號', '股數', '買進價', '個股買進總價', '現價', '市值', '個股盈虧', '總盈虧', '報酬率 (%)']
            # [V2.26] 手機預設順序優化
            mobile_columns = ['代號', '買進價', '現價', '總盈虧', '報酬率 (%)']
            
            if 'selected_cols_list' not in st.session_state: 
                st.session_state.selected_cols_list = mobile_columns
            
            def on_mode_change():
                if st.session_state.is_mobile_mode: st.session_state.selected_cols_list = mobile_columns
                else: st.session_state.selected_cols_list = all_columns

            col_ctrl1, col_ctrl2 = st.columns([1, 2])
            with col_ctrl1: st.toggle("📱 手機精簡", value=True, key="is_mobile_mode", on_change=on_mode_change)
            with col_ctrl2: selected_cols = st.multiselect("顯示欄位", options=all_columns, key="selected_cols_list")
        
        if not selected_cols: selected_cols = ['代號']

        format_mapping = {
            '股數': '{:.3f}', '買進價': '${:.2f}', '個股買進總價': '${:,.2f}',
            '現價': '${:.2f}', '市值': '${:,.0f}', '個股盈虧': '${:.2f}',
            '總盈虧': '${:.2f}', '報酬率 (%)': '{:.2f}%', '比重 (%)': '{:.2f}%'
        }
        
        def apply_row_colors(row):
            if chart_mode == "依代號合併 (Merge)": key = row['代號']
            else: key = str(row['原始索引'])
            color = color_map_dict.get(key, '#ffffff')
            return [f'background-color: {color}; color: black; font-weight: bold' if col == '代號' else '' for col in row.index]

        display_cols = list(set(selected_cols + ['代號', '原始索引']))
        styled_df = df[display_cols].copy()
        
        # [V2.26] 確保買進價在前面 (如果有的話)
        user_order = [c for c in selected_cols if c != '代號']
        final_cols = ['代號'] + user_order
        
        # [V2.26] 樣式優化: 買進價紅色
        st.dataframe(
            styled_df.style
            .format(format_mapping)
            .apply(apply_row_colors, axis=1)
            .map(lambda x: 'color: #ff3333; font-weight: bold', subset=[c for c in ['買進價'] if c in final_cols])
            .map(lambda x: 'color: #ff3333' if isinstance(x,(int,float)) and x>0 else 'color: #00cc00' if isinstance(x,(int,float)) and x<0 else '', subset=[c for c in ['總盈虧', '報酬率 (%)'] if c in final_cols]),
            column_order=final_cols,
            use_container_width=True,
            height=600
        )

    elif st.session_state.portfolio_df is None:
        st.info("👋 請點擊上方「刷新即時報價」按鈕來載入資料。")