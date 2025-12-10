import streamlit as st
import yfinance as yf
import pandas as pd
import mplfinance as mpf

# 設定寬版頁面，讓圖表更清楚
st.set_page_config(layout="wide", page_title="史帝夫的股市分析室")

st.title("📊 史帝夫股市分析 (Yahoo 豪華版)")
st.caption("使用 Yahoo Finance 資料源，解決雲端 IP 阻擋問題，包含完整技術分析功能。")

# --- 1. 抓取資料 (Yahoo 版) ---
@st.cache_data(ttl=3600)
def get_data(code):
    # 先嘗試上市股票 (.TW)
    stock_id = f"{code}.TW"
    try:
        ticker = yf.Ticker(stock_id)
        df = ticker.history(period="1y") # 抓一年份資料
        
        # 如果抓不到資料 (DataFrame 是空的)，嘗試上櫃股票 (.TWO)
        if df.empty:
            stock_id = f"{code}.TWO"
            ticker = yf.Ticker(stock_id)
            df = ticker.history(period="1y")
        
        # 如果還是空的，回傳失敗
        if df.empty:
            return None
        
        # Yahoo 的資料索引已經是 datetime，不需要轉換
        # 欄位名稱通常是 Open, High, Low, Close, Volume (首字大寫)
        return df
    except Exception as e:
        return None

# --- 2. 計算指標 (配合 Yahoo 的大寫欄位) ---
def add_indicators(df):
    # 注意：Yahoo 的欄位是 'High', 'Low', 'Close' (大寫開頭)
    
    # --- KD 指標 ---
    # RSV = (今日收盤 - 9日低) / (9日高 - 9日低) * 100
    df['min_low'] = df['Low'].rolling(9).min()
    df['max_high'] = df['High'].rolling(9).max()
    df['RSV'] = (df['Close'] - df['min_low']) / (df['max_high'] - df['min_low']) * 100
    df['K'] = df['RSV'].ewm(com=2, adjust=False).mean()
    df['D'] = df['K'].ewm(com=2, adjust=False).mean()
    
    # --- MACD 指標 ---
    exp12 = df['Close'].ewm(span=12, adjust=False).mean()
    exp26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp12 - exp26
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['Hist'] = df['MACD'] - df['Signal']
    
    return df

def calculate_golden_ratio(df):
    # 計算黃金分割率 (使用最近半年的高低點)
    # 取最近 120 天來算比較準
    recent_df = df.tail(120)
    highest = recent_df['High'].max()
    lowest = recent_df['Low'].min()
    diff = highest - lowest
    
    ratios = [0.191, 0.382, 0.5, 0.618, 0.809]
    levels = {}
    for r in ratios:
        levels[f"{r}"] = lowest + (diff * r)
        
    return highest, lowest, levels

# --- 3. 側邊欄設定 ---
with st.sidebar:
    st.header("⚙️ 參數設定")
    code = st.text_input("輸入股票代碼", "2330")
    st.markdown("---")
    st.write("顯示指標：")
    show_vol = st.checkbox("成交量 (Volume)", value=True)
    show_kd = st.checkbox("KD 指標", value=True)
    show_macd = st.checkbox("MACD 指標", value=False)

# --- 4. 主畫面顯示 ---
if code:
    df = get_data(code)
    
    if df is not None and len(df) > 0:
        df = add_indicators(df)
        
        # --- A. 顯示即時數據 ---
        last_close = df['Close'].iloc[-1]
        prev_close = df['Close'].iloc[-2]
        change = last_close - prev_close
        pct_change = (change / prev_close) * 100
        last_vol = df['Volume'].iloc[-1]
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("最新收盤", f"{last_close:.2f}", f"{change:.2f}")
        col2.metric("漲跌幅", f"{pct_change:.2f}%")
        col3.metric("成交量", f"{int(last_vol):,}")
        col4.metric("K值", f"{df['K'].iloc[-1]:.2f}")

        # --- B. 繪製 K 線圖 ---
        st.subheader(f"📈 {code} 走勢圖")
        
        add_plots = []
        panels = [4] # 主圖高度
        pid = 0
        
        # 處理圖層
        if show_vol:
            pid += 1
            panels.append(1)
            
        if show_kd:
            pid += 1
            panels.append(1.5)
            # KD 線
            add_plots.append(mpf.make_addplot(df['K'], panel=pid, color='orange', title='KD'))
            add_plots.append(mpf.make_addplot(df['D'], panel=pid, color='blue'))
            
        if show_macd:
            pid += 1
            panels.append(1.5)
            # MACD
            add_plots.append(mpf.make_addplot(df['MACD'], panel=pid, color='red', title='MACD'))
            add_plots.append(mpf.make_addplot(df['Signal'], panel=pid, color='blue'))
            add_plots.append(mpf.make_addplot(df['Hist'], type='bar', panel=pid, color='gray', alpha=0.5))

        # 畫圖 (mplfinance 預設就會吃 Open, High, Low, Close 這些大寫欄位)
        fig, ax = mpf.plot(
            df, 
            type='candle', 
            style='yahoo', 
            volume=show_vol, 
            addplot=add_plots, 
            panel_ratios=panels, 
            returnfig=True, 
            figsize=(12, 8)
        )
        st.pyplot(fig)
        
        # --- C. 黃金分割率表格 ---
        st.markdown("---")
        st.subheader("🏆 黃金分割率 (支撐壓力分析)")
        
        high, low, levels = calculate_golden_ratio(df)
        
        golden_data = {
            "關鍵位置": ["波段高點", "0.809", "0.618 (強力支撐/壓力)", "0.500 (中關)", "0.382 (弱關)", "0.191", "波段低點"],
            "價格": [
                high,
                levels['0.809'],
                levels['0.618'],
                levels['0.5'],
                levels['0.382'],
                levels['0.191'],
                low
            ]
        }
        golden_df = pd.DataFrame(golden_data)
        
        col_l, col_r = st.columns([1, 2])
        with col_l:
            st.dataframe(golden_df.style.format({"價格": "{:.2f}"}), use_container_width=True)
        with col_r:
            st.info("""
            **使用說明：**
            * 這是根據最近 120 天的高低點計算出來的。
            * **0.618** 通常是最強的支撐或壓力位。
            * 如果股價跌破 0.5，通常代表趨勢轉弱。
            """)
            
    else:
        st.error(f"找不到代碼 {code} 的資料。請確認代碼是否正確 (Yahoo 也能抓上櫃股票喔！)")
