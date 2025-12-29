import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from alpaca_trade_api.rest import REST
from datetime import datetime

# --- 版本控制 ---
VERSION = "2.7 (Tab Reorder)"

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
def get_portfolio_data(api_key, secret_key):
    api_key = api_key.strip()
    secret_key = secret_key.strip()
    api = REST(api_key, secret_key, base_url='https://paper-api.alpaca.markets')
    
    portfolio_data = [
        {'symbol': 'AAL',   'qty': 100,   'avg_cost': 0.0},
        {'symbol': 'COST',  'qty': 0,     'avg_cost': 0.0},
        {'symbol': 'GGR',   'qty': 0,     'avg_cost': 0.0},
        {'symbol': 'GOOGL', 'qty': 30,    'avg_cost': 0.0},
        {'symbol': 'GRAB',  'qty': 200,   'avg_cost': 4.0}, 
        {'symbol': 'LFMD',  'qty': 400,   'avg_cost': 0.0},
        {'symbol': 'MRNA',  'qty': 0,     'avg_cost': 0.0},
        {'symbol': 'NVDA',  'qty': 40,    'avg_cost': 0.0},
        {'symbol': 'RIVN',  'qty': 200,   'avg_cost': 0.0},
        {'symbol': 'SOFI',  'qty': 200,   'avg_cost': 0.0},
        {'symbol': 'TSLA',  'qty': 20,    'avg_cost': 0.0},
        {'symbol': 'VZ',    'qty': 132.4, 'avg_cost': 0.0},
        {'symbol': 'LULU',  'qty': 40,    'avg_cost': 0.0},
        {'symbol': 'HIMS',  'qty': 300,   'avg_cost': 0.0},
        {'symbol': 'RKLB',  'qty': 100,   'avg_cost': 0.0},
        {'symbol': 'FTNT',  'qty': 30,    'avg_cost': 0.0},
        {'symbol': 'DXYZ',  'qty': 0,     'avg_cost': 0.0},
        {'symbol': 'FIG',   'qty': 10,    'avg_cost': 0.0},
        {'symbol': 'GGR',   'qty': 10,    'avg_cost': 0.0},
        {'symbol': 'QSI',   'qty': 600,   'avg_cost': 0.0},
        {'symbol': 'NVDA',  'qty': 5,     'avg_cost': 0.0},
        {'symbol': 'NVDA',  'qty': 15,    'avg_cost': 0.0},
    ]

    results = []
    error_logs = []
    
    for item in portfolio_data:
        symbol = item['symbol']
        qty = item['qty']
        cost = item['avg_cost']
        if qty == 0: continue 

        try:
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

    if error_logs:
        print(f"⚠️ 偵測到部分股票資料抓取失敗: {error_logs}")

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
ticker_input = st.sidebar.text_input("輸入美股代號 (例如: KO, AAPL, NVDA)", value="AAPL").upper()
analysis_btn = st.sidebar.button("開始分析")
st.sidebar.markdown("---")
st.sidebar.caption(f"App Version: {VERSION}")

# [修改] 調整分頁順序：1.個股分析 2.DCF模型 3.模擬庫存
tab1, tab2, tab3 = st.tabs(["📊 個股分析", "💰 DCF估值模型", "💼 模擬庫存"])

# ------------------------------------------------------------------
# 分頁 1: 個股分析
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

                # 品質分數
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
# 分頁 2: DCF 估值模型 (原本的分頁 3)
# ------------------------------------------------------------------
with tab2:
    st.header(f"💰 {ticker_input} DCF 現金流折現估值模型")
    st.info("此模型採用「二階段成長」計算：前 5 年為第一階段，6-10 年為第二階段，最後計算終值。")

    # 1. 嘗試抓取自動帶入的數據
    try:
        stock_info = yf.Ticker(ticker_input).info
        
        # 預設值處理 (如果抓不到就設為 0 或預設比率)
        default_fcf = stock_info.get('freeCashflow', 0)
        if default_fcf is None: default_fcf = 0
        
        default_cash = stock_info.get('totalCash', 0)
        if default_cash is None: default_cash = 0
        
        default_debt = stock_info.get('totalDebt', 0)
        if default_debt is None: default_debt = 0
        
        default_shares = stock_info.get('sharesOutstanding', 1)
        if default_shares is None: default_shares = 1

        default_price = stock_info.get('currentPrice', 0)
    except:
        default_fcf = 0
        default_cash = 0
        default_debt = 0
        default_shares = 1
        default_price = 0

    # 2. 建立輸入表單 (仿 Excel 配置)
    st.subheader("1️⃣ 參數設定 (可手動修改)")
    
    col_dcf1, col_dcf2 = st.columns(2)
    
    with col_dcf1:
        st.markdown("##### 📈 成長率與折現率")
        growth_rate_1_5 = st.number_input("未來成長率 (1~5年) %", value=10.0, step=0.1, help="預估公司未來 5 年的平均成長率") / 100
        growth_rate_6_10 = st.number_input("二階成長率 (6~10年) %", value=5.0, step=0.1, help="預估公司第 6 到 10 年的成長率") / 100
        perpetual_rate = st.number_input("永久成長率 (終值) %", value=2.5, step=0.1, help="保守建議設在 2%~3% 之間 (接近通膨)") / 100
        discount_rate = st.number_input("折現率 (WACC) %", value=9.0, step=0.1, help="期望的投資回報率，通常設 8%~12%") / 100

    with col_dcf2:
        st.markdown("##### 🏢 財務基礎數據 (自動帶入)")
        # 這裡單位換算成「百萬」或維持「原始數值」皆可，為了精確度建議用原始數值
        base_fcf = st.number_input("目前自由現金流 (FCF)", value=float(default_fcf), step=1000000.0, format="%.0f")
        cash_and_equiv = st.number_input("現金及約當現金", value=float(default_cash), step=1000000.0, format="%.0f")
        total_debt = st.number_input("總負債", value=float(default_debt), step=1000000.0, format="%.0f")
        shares_out = st.number_input("流通股數", value=float(default_shares), step=1000.0, format="%.0f")

    # 3. 計算邏輯
    st.markdown("---")
    if st.button("開始 DCF 估值計算", type="primary"):
        
        # 產生 10 年現金流預估
        future_fcf = []
        discount_factors = []
        discounted_fcf = []
        
        current_year = datetime.now().year
        years = []

        # 計算 1-10 年
        temp_fcf = base_fcf
        for i in range(1, 11):
            years.append(current_year + i)
            
            # 判斷成長率階段
            if i <= 5:
                g = growth_rate_1_5
            else:
                g = growth_rate_6_10
            
            temp_fcf = temp_fcf * (1 + g)
            future_fcf.append(temp_fcf)
            
            # 折現因子
            factor = (1 + discount_rate) ** i
            discount_factors.append(factor)
            
            # 折現後價值
            discounted_fcf.append(temp_fcf / factor)

        # 計算終值 (Terminal Value)
        # 公式: TV = FCF_10 * (1 + g_perp) / (WACC - g_perp)
        if discount_rate <= perpetual_rate:
            st.error("錯誤：折現率 (WACC) 必須大於永久成長率，否則模型無法收斂。")
            st.stop()
            
        terminal_value = future_fcf[-1] * (1 + perpetual_rate) / (discount_rate - perpetual_rate)
        terminal_value_discounted = terminal_value / ((1 + discount_rate) ** 10)

        # 企業價值 (Enterprise Value) = 所有折現現金流總和 + 折現終值
        sum_discounted_fcf = sum(discounted_fcf)
        enterprise_value = sum_discounted_fcf + terminal_value_discounted
        
        # 股權價值 (Equity Value) = EV + 現金 - 負債
        equity_value = enterprise_value + cash_and_equiv - total_debt
        
        # 合理股價
        fair_value_per_share = equity_value / shares_out
        
        # 安全邊際
        margin_of_safety = 0
        if default_price > 0:
            margin_of_safety = (fair_value_per_share - default_price) / default_price * 100

        # 4. 顯示結果
        st.subheader("2️⃣ 估值結果 (Valuation Result)")
        
        res_col1, res_col2, res_col3 = st.columns(3)
        
        with res_col1:
            st.metric("計算出的合理價", f"${fair_value_per_share:.2f}")
        
        with res_col2:
            st.metric("目前市場股價", f"${default_price:.2f}")
            
        with res_col3:
            color = "normal"
            if margin_of_safety > 0: color = "normal" # 潛在漲幅
            else: color = "off"
            
            st.metric("潛在漲幅 / 溢價", f"{margin_of_safety:.2f}%", delta_color=color)
            if margin_of_safety > 20:
                st.success("🚀 股價被低估 (Undervalued) - 安全邊際 > 20%")
            elif margin_of_safety < -20:
                st.error("⚠️ 股價被高估 (Overvalued)")
            else:
                st.warning("⚖️ 股價接近合理區間")

        # 5. 顯示詳細預估表 (仿 Excel 表格)
        st.subheader("3️⃣ 詳細現金流預估表 (Yearly Projection)")
        
        # 製作 DataFrame
        dcf_data = {
            "年份": years,
            "預估成長率": [f"{growth_rate_1_5*100:.1f}%"]*5 + [f"{growth_rate_6_10*100:.1f}%"]*5,
            "預估 FCF (百萬)": [f"${x/1000000:,.0f}" for x in future_fcf],
            "折現因子": [f"{x:.4f}" for x in discount_factors],
            "折現後 FCF (百萬)": [f"${x/1000000:,.0f}" for x in discounted_fcf]
        }
        df_dcf = pd.DataFrame(dcf_data)
        st.dataframe(df_dcf, use_container_width=True)
        
        st.caption(f"終值 (Terminal Value): ${terminal_value/1000000:,.0f} M | 折現後終值: ${terminal_value_discounted/1000000:,.0f} M")

# ------------------------------------------------------------------
# 分頁 3: 模擬庫存 (原本的分頁 2)
# ------------------------------------------------------------------
with tab3:
    st.header("🚀 股票監控儀表板")
    
    try:
        api_key = st.secrets["ALPACA_API_KEY"]
        secret_key = st.secrets["ALPACA_SECRET_KEY"]
    except:
        st.error("⚠️ 請先設定 .streamlit/secrets.toml")
        st.stop()

    # [資料持久化]
    if 'portfolio_df' not in st.session_state:
        st.session_state.portfolio_df = None
    if 'total_val' not in st.session_state:
        st.session_state.total_val = 0

    if st.button("🔄 刷新即時報價", type="primary"):
        with st.spinner("正在連線 Alpaca 抓取最新股價..."):
            df, total_val = get_portfolio_data(api_key, secret_key)
            st.session_state.portfolio_df = df
            st.session_state.total_val = total_val

    # [顯示邏輯]
    if st.session_state.portfolio_df is not None and not st.session_state.portfolio_df.empty:
        
        df = st.session_state.portfolio_df
        total_val = st.session_state.total_val

        st.metric("💰 投資組合總價值", f"${total_val:,.2f}")
        st.markdown("---")

        c1, c2, c3 = st.columns([1, 2, 1])
        with c2: 
            st.subheader("倉位佔比")
            plot_df = df[df['比重 (%)'] > 1].copy()
            other_val = 100 - plot_df['比重 (%)'].sum()
            if other_val > 0:
                new_row = pd.DataFrame([{'代號': 'Others', '比重 (%)': other_val}])
                plot_df = pd.concat([plot_df, new_row], ignore_index=True)
            
            fig, ax = plt.subplots()
            plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial Unicode MS', 'DejaVu Sans', 'sans-serif']
            ax.pie(plot_df['比重 (%)'], labels=plot_df['代號'], autopct='%1.1f%%', 
                   startangle=140, colors=plt.cm.Paired.colors)
            ax.axis('equal') 
            st.pyplot(fig)

        st.markdown("---") 

        st.subheader("詳細庫存清單")
        
        # --- [V2.5 修復] 欄位記憶功能 ---
        
        all_columns = ['代號', '股數', '買進價', '個股買進總價', '現價', '市值', '個股盈虧', '總盈虧', '報酬率 (%)']
        mobile_columns = ['代號', '現價', '市值', '總盈虧', '報酬率 (%)']

        # 初始化
        if 'selected_cols_list' not in st.session_state:
            st.session_state.selected_cols_list = mobile_columns

        # 回呼函數
        def on_mode_change():
            if st.session_state.is_mobile_mode:
                st.session_state.selected_cols_list = mobile_columns
            else:
                st.session_state.selected_cols_list = all_columns

        col_ctrl1, col_ctrl2 = st.columns([1, 2])
        
        with col_ctrl1:
            # 綁定 callback
            st.toggle("📱 手機精簡模式", value=True, key="is_mobile_mode", on_change=on_mode_change)
        
        with col_ctrl2:
            # 綁定 key
            selected_cols = st.multiselect(
                "👁️ 自訂顯示欄位", 
                options=all_columns, 
                key="selected_cols_list" 
            )

        if not selected_cols:
            selected_cols = ['代號']

        def highlight_profit_style(val):
            if isinstance(val, (int, float)):
                if val > 0: return 'color: #ff3333; font-weight: bold' 
                elif val < 0: return 'color: #00cc00; font-weight: bold'
            return 'color: black'

        format_mapping = {
            '股數': '{:.3f}',
            '買進價': '${:.2f}',
            '個股買進總價': '${:,.2f}',
            '現價': '${:.2f}', 
            '市值': '${:,.0f}',
            '個股盈虧': '${:.2f}',
            '總盈虧': '${:.2f}',
            '報酬率 (%)': '{:.2f}%',
            '比重 (%)': '{:.2f}%'
        }
        
        st.dataframe(
            df[selected_cols].style.format(format_mapping).map(
                highlight_profit_style, 
                subset=[c for c in ['總盈虧', '報酬率 (%)', '個股盈虧'] if c in selected_cols]
            ),
            use_container_width=True,
            height=600 
        )
    
    elif st.session_state.portfolio_df is None:
        st.info("👋 請點擊上方「刷新即時報價」按鈕來載入資料。")