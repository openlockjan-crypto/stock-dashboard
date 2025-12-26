import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from alpaca_trade_api.rest import REST

# --- 版本控制 ---
VERSION = "2.4 (Fix Refresh Bug)"

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

    # 連線設定
    api = REST(api_key, secret_key, base_url='https://paper-api.alpaca.markets')
    
    # --- 持股清單 ---
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
    
    # 開始計算
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

            # 計算各項數值
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

# 建立分頁
tab1, tab2 = st.tabs(["📊 個股分析", "💼 模擬庫存"])

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

                # 顯示基本股價資訊
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

                # DDM 模型
                st.subheader("💰 合理價值評估 (DDM模型範例)")
                d_rate = st.slider("折現率", 0.05, 0.15, 0.09)
                g_rate = st.slider("成長率", 0.01, 0.10, 0.03)
                try:
                    div = info.get('dividendRate', 0)
                    if div > 0 and d_rate > g_rate:
                        fv = (div * (1 + g_rate)) / (d_rate - g_rate)
                        st.metric("計算出的合理價", f"${fv:.2f}")
                    else:
                        st.info("不適用 DDM 模型")
                except: pass

        except Exception as e:
            st.error(f"錯誤: {e}")

# ------------------------------------------------------------------
# 分頁 2: 模擬庫存
# ------------------------------------------------------------------
with tab2:
    st.header("🚀 股票監控儀表板")
    
    # 讀取 Secrets
    try:
        api_key = st.secrets["ALPACA_API_KEY"]
        secret_key = st.secrets["ALPACA_SECRET_KEY"]
    except:
        st.error("⚠️ 請先設定 .streamlit/secrets.toml")
        st.stop()

    # [FIX] 使用 session_state 來儲存資料，防止互動後畫面重置
    if 'portfolio_df' not in st.session_state:
        st.session_state.portfolio_df = None
    if 'total_val' not in st.session_state:
        st.session_state.total_val = 0

    # 按鈕只負責「更新資料」，不負責「顯示畫面」
    if st.button("🔄 刷新即時報價", type="primary"):
        with st.spinner("正在連線 Alpaca 抓取最新股價..."):
            df, total_val = get_portfolio_data(api_key, secret_key)
            # 將資料存入 session_state
            st.session_state.portfolio_df = df
            st.session_state.total_val = total_val

    # [FIX] 只要 session_state 裡面有資料，就顯示出來
    # 這樣即使你動了開關 (重跑程式)，因為資料還在 session_state 裡，所以不會消失
    if st.session_state.portfolio_df is not None and not st.session_state.portfolio_df.empty:
        
        df = st.session_state.portfolio_df
        total_val = st.session_state.total_val

        # 1. 顯示總價值
        st.metric("💰 投資組合總價值", f"${total_val:,.2f}")
        st.markdown("---")

        # 2. 圓餅圖 (置中)
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

        # 3. 表格 (手機優化版)
        st.subheader("詳細庫存清單")
        
        # --- [功能] 手機版面優化與欄位篩選 ---
        
        all_columns = ['代號', '股數', '買進價', '個股買進總價', '現價', '市值', '個股盈虧', '總盈虧', '報酬率 (%)']
        mobile_columns = ['代號', '現價', '市值', '總盈虧', '報酬率 (%)']
        
        col_ctrl1, col_ctrl2 = st.columns([1, 2])
        
        with col_ctrl1:
            is_mobile_mode = st.toggle("📱 手機精簡模式", value=True)
        
        with col_ctrl2:
            default_cols = mobile_columns if is_mobile_mode else all_columns
            selected_cols = st.multiselect(
                "👁️ 自訂顯示欄位", 
                options=all_columns, 
                default=default_cols
            )

        if not selected_cols:
            selected_cols = ['代號']

        # --- 樣式設定 ---
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
    
    # 這裡只在「完全沒資料」且「還沒按過按鈕」時才顯示提示
    elif st.session_state.portfolio_df is None:
        st.info("👋 請點擊上方「刷新即時報價」按鈕來載入資料。")