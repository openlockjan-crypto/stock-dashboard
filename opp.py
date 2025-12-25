import streamlit as st
import yfinance as yf
import pandas as pd

# --- 設定網頁配置 ---
st.set_page_config(page_title="AI 價值投資儀表板", layout="wide")

# --- 側邊欄：輸入區 ---
st.sidebar.header("🔍 股票篩選")
ticker = st.sidebar.text_input("輸入美股代號 (例如: KO, AAPL, NVDA)", value="KO").upper()
analysis_btn = st.sidebar.button("開始分析")

# --- 核心函數：取得資料 ---
@st.cache_data # 快取資料，避免重複下載變慢
def get_data(symbol):
    stock = yf.Ticker(symbol)
    # 取得歷史股價
    hist = stock.history(period="5y")
    return stock, hist

# --- 主程式邏輯 ---
st.title(f"📊 {ticker} 投資決策中心")
st.markdown("---")

if analysis_btn or ticker:
    try:
        with st.spinner('正在下載財報數據與分析中...'):
            stock, hist = get_data(ticker)
            info = stock.info
            
            # 如果抓不到股價，通常是代號錯誤
            if hist.empty:
                st.error("找不到該股票資料，請確認代號是否正確。")
                st.stop()

            # --- 1. 頂部資訊欄 ---
            col1, col2, col3, col4 = st.columns(4)
            current_price = hist['Close'].iloc[-1]
            prev_price = hist['Close'].iloc[-2]
            delta = current_price - prev_price
            
            col1.metric("目前股價", f"${current_price:.2f}", f"{delta:.2f}")
            col2.metric("公司名稱", info.get('longName', 'N/A'))
            col3.metric("產業", info.get('industry', 'N/A'))
            col4.metric("Beta (波動率)", info.get('beta', 'N/A'))

            # --- 2. 品質分數計算 (Quality Score) ---
            st.subheader("🛡️ 企業體質評分 (Quality Score)")
            
            score = 0
            reasons = []
            
            # 規則 A: ROE > 15%
            roe = info.get('returnOnEquity', 0)
            if roe and roe > 0.15:
                score += 20
                reasons.append(f"✅ ROE 表現優異 ({roe:.2%})")
            else:
                reasons.append(f"❌ ROE 偏低 ({roe:.2%} < 15%)")
            
            # 規則 B: 營益率 > 10%
            om = info.get('operatingMargins', 0)
            if om and om > 0.10:
                score += 20
                reasons.append(f"✅ 本業獲利能力佳 (營益率 {om:.2%})")
            else:
                reasons.append(f"❌ 營益率偏低")

            # 規則 C: 股息是否成長 (簡易判斷)
            div_rate = info.get('dividendRate', 0)
            if div_rate > 0:
                score += 20
                reasons.append(f"✅ 公司有配發股息 (殖利率 {info.get('dividendYield',0):.2%})")
            else:
                reasons.append(f"⚠️ 公司不配發股息 (略過股息評分)")

            # 規則 D: 自由現金流 (FCF) - 這裡簡單用是否有現金流替代
            fcf = info.get('freeCashflow', 0)
            if fcf and fcf > 0:
                score += 20
                reasons.append("✅ 自由現金流為正")
            else:
                reasons.append("❌ 自由現金流為負或資料缺失")
                
            # 規則 E: 毛利率 > 30% (護城河指標)
            gm = info.get('grossMargins', 0)
            if gm and gm > 0.3:
                score += 20
                reasons.append(f"✅ 毛利率高 ({gm:.2%}) 具競爭優勢")
            else:
                reasons.append(f"❌ 毛利率較低 ({gm:.2%})")

            # 顯示分數儀表
            q_col1, q_col2 = st.columns([1, 2])
            with q_col1:
                if score >= 80:
                    st.success(f"總分: {score} 分 (優異)")
                elif score >= 60:
                    st.warning(f"總分: {score} 分 (普通)")
                else:
                    st.error(f"總分: {score} 分 (需注意)")
            with q_col2:
                for r in reasons:
                    st.caption(r)

            st.markdown("---")

            # --- 3. 合理價估值 (Valuation) ---
            st.subheader("💰 合理價值評估 (DDM模型範例)")
            
            # 讓使用者可以在網頁上調整假設參數！
            v_col1, v_col2 = st.columns(2)
            with v_col1:
                discount_rate = st.slider("設定折現率 (期望報酬)", 0.05, 0.15, 0.09, 0.01)
                growth_rate = st.slider("設定股息成長率預估", 0.01, 0.10, 0.03, 0.01)
            
            # 計算邏輯
            try:
                # 預估明年股息
                current_div = info.get('dividendRate', 0)
                if current_div > 0 and discount_rate > growth_rate:
                    fair_value = (current_div * (1 + growth_rate)) / (discount_rate - growth_rate)
                    upside = (fair_value - current_price) / current_price
                    
                    with v_col2:
                        st.metric("計算出的合理價", f"${fair_value:.2f}", f"潛在漲幅 {upside:.2%}")
                        if current_price < fair_value:
                            st.success("目前股價處於【低估】區間")
                        else:
                            st.error("目前股價處於【高估】區間")
                else:
                    with v_col2:
                        st.info("此公司不發股息，或成長率設定高於折現率，不適用 DDM 模型。")
            except:
                st.write("計算錯誤，資料不足。")

            # --- 4. 股價走勢圖 ---
            st.subheader("📈 歷史股價走勢")
            st.line_chart(hist['Close'])

            # --- 5. 基本資料表 ---
            with st.expander("查看詳細財務數據"):
                st.dataframe(stock.financials)

    except Exception as e:
        st.error(f"發生錯誤: {e}")

# 頁尾
st.markdown("---")
st.caption("⚠️ 免責聲明：本系統僅供學習與參考，不構成投資建議。")