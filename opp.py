import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from alpaca_trade_api.rest import REST
from datetime import datetime
import json
import os
import colorsys
import requests 

# --- 版本控制 ---
VERSION = "2.22 (Layout Optimization)"
PORTFOLIO_FILE = "saved_portfolios.json"

# --- 設定網頁配置 ---
st.set_page_config(page_title="AI 投資決策中心", layout="wide")

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
    api = REST(api_key, secret_key, base_url='https://paper-api.alpaca.markets')
    
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
            try:
                quote = api.get_latest_trade(symbol)
                current_price = quote.price
            except:
                try:
                    last_quote = api.get_latest_quote(symbol)
                    current_price = (last_quote.bid_price + last_quote.ask_price) / 2
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

tab1, tab2, tab3 = st.tabs(["📊 個股分析", "💰 DCF估值模型", "💼 模擬庫存"])

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

# --- Tab 3: 模擬庫存 (V2.22) ---
with tab3:
    st.header("🚀 股票監控儀表板")
    
    try:
        api_key = st.secrets["ALPACA_API_KEY"]
        secret_key = st.secrets["ALPACA_SECRET_KEY"]
    except:
        st.error("⚠️ 請先設定 .streamlit/secrets.toml")
        st.stop()

    # 初始化
    if 'my_portfolio_data' not in st.session_state:
        st.session_state.my_portfolio_data = pd.DataFrame([
            {'代號': 'NVDA', '股數': 100.0, '買進價': 120.0, '移除': False},
            {'代號': 'TSLA', '股數': 50.0,  '買進價': 180.0, '移除': False},
        ])
    else:
        if '移除' not in st.session_state.my_portfolio_data.columns:
            st.session_state.my_portfolio_data['移除'] = False

    # 1. 雲端管理 (Expander)
    try:
        saved_portfolios = load_saved_portfolios()
    except: saved_portfolios = {}

    with st.expander("☁️ 雲端投資組合管理 (點擊展開)", expanded=False):
        col_load, col_save = st.columns(2)
        with col_load:
            if saved_portfolios:
                selected_group = st.selectbox("選擇群組", list(saved_portfolios.keys()))
                c_l1, c_l2 = st.columns(2)
                if c_l1.button("📂 載入"):
                    new_data = saved_portfolios[selected_group]
                    loaded_df = pd.DataFrame(new_data)
                    loaded_df['股數'] = loaded_df['股數'].astype(float)
                    loaded_df['買進價'] = loaded_df['買進價'].astype(float)
                    if '移除' not in loaded_df.columns: loaded_df['移除'] = False
                    st.session_state.my_portfolio_data = loaded_df
                    st.toast(f"已載入：{selected_group}")
                    st.rerun()
                if c_l2.button("🗑️ 刪除"):
                    del saved_portfolios[selected_group]
                    save_portfolios_to_file(saved_portfolios)
                    st.toast(f"已刪除：{selected_group}")
                    st.rerun()
            else: st.info("無存檔")
        with col_save:
            save_name = st.text_input("存檔名稱", placeholder="例如: 科技股")
            if st.button("💾 上傳存檔"):
                if save_name:
                    current_data = st.session_state.my_portfolio_data.to_dict('records')
                    saved_portfolios[save_name] = current_data
                    save_portfolios_to_file(saved_portfolios)
                    st.toast(f"✅ 已上傳：{save_name}")
                    st.rerun()
                else: st.error("請輸入名稱")

    # 2. 新增持股 (Container)
    st.subheader("➕ 新增持股")
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

    # 3. [V2.22] 庫存清單 (改為摺疊選單)
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

    # 5. 報表顯示 (V2.22 上下佈局)
    if st.session_state.portfolio_df is not None and not st.session_state.portfolio_df.empty:
        df = st.session_state.portfolio_df.copy()
        total_val = st.session_state.total_val
        st.markdown("---")
        st.metric("💰 總價值", f"${total_val:,.2f}")
        
        # --- (A) 上方：圖表區 ---
        st.subheader("📊 資產分佈")
        
        # 圖表模式選擇
        chart_mode = st.radio("圖表模式", ["依代號合併 (Merge)", "依分批明細 (Detail)"], horizontal=True, label_visibility="collapsed")
        
        # 數據處理
        if chart_mode == "依代號合併 (Merge)":
            plot_df = df.groupby('代號')['市值'].sum().reset_index()
            plot_df['Label'] = plot_df['代號']
            df['ColorKey'] = df['代號'] 
        else:
            plot_df = df.copy()
            plot_df['Label'] = plot_df.apply(lambda x: f"{x['代號']} (${x['買進價']:.0f})", axis=1)
            df['ColorKey'] = df['原始索引'].astype(str)
            plot_df['ColorKey'] = plot_df['原始索引'].astype(str)

        plot_df['比重'] = (plot_df['市值'] / total_val) * 100
        
        # 顏色生成
        unique_keys = plot_df['Label'].unique() if chart_mode == "依代號合併 (Merge)" else plot_df['ColorKey'].unique()
        color_list = generate_distinct_colors(len(unique_keys))
        color_map_dict = dict(zip(unique_keys, color_list))
        
        if chart_mode == "依代號合併 (Merge)":
            chart_colors = [color_map_dict[x] for x in plot_df['Label']]
        else:
            chart_colors = [color_map_dict[str(x)] for x in plot_df['ColorKey']]

        # 繪圖 (放大版)
        fig, ax = plt.subplots(figsize=(10, 6)) # 加大尺寸
        ax.pie(plot_df['比重'], labels=plot_df['Label'], autopct='%1.1f%%', startangle=140, colors=chart_colors)
        ax.axis('equal') 
        st.pyplot(fig, use_container_width=True)

        st.markdown("---")

        # --- (B) 下方：報表區 ---
        st.subheader("📋 詳細損益清單")

        # [V2.22] 顯示設定 (摺疊)
        all_columns = ['代號', '股數', '買進價', '個股買進總價', '現價', '市值', '個股盈虧', '總盈虧', '報酬率 (%)']
        mobile_columns = ['代號', '現價', '市值', '總盈虧', '報酬率 (%)']
        if 'selected_cols_list' not in st.session_state: st.session_state.selected_cols_list = mobile_columns
        
        def on_mode_change():
            if st.session_state.is_mobile_mode: st.session_state.selected_cols_list = mobile_columns
            else: st.session_state.selected_cols_list = all_columns

        with st.expander("⚙️ 顯示設定 (欄位與手機模式)", expanded=False):
            col_ctrl1, col_ctrl2 = st.columns([1, 2])
            with col_ctrl1: st.toggle("📱 手機精簡", value=True, key="is_mobile_mode", on_change=on_mode_change)
            with col_ctrl2: selected_cols = st.multiselect("顯示欄位", options=all_columns, key="selected_cols_list")
        
        if not selected_cols: selected_cols = ['代號']

        # 表格樣式
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
        final_cols = ['代號'] + [c for c in selected_cols if c != '代號']
        
        st.dataframe(
            styled_df.style
            .format(format_mapping)
            .apply(apply_row_colors, axis=1)
            .map(lambda x: 'color: #ff3333' if isinstance(x,(int,float)) and x>0 else 'color: #00cc00' if isinstance(x,(int,float)) and x<0 else '', subset=[c for c in ['總盈虧', '報酬率 (%)'] if c in final_cols]),
            column_order=final_cols,
            use_container_width=True,
            height=600
        )

    elif st.session_state.portfolio_df is None:
        st.info("👋 請點擊上方「刷新即時報價」按鈕來載入資料。")