import streamlit as st
import yfinance as yf  # 改用這個
import pandas as pd
import mplfinance as mpf

# ---------------------------------------------------------
# 1. 改用 yfinance 抓取資料 (解決 SSL 錯誤與連線不穩)
# ---------------------------------------------------------
@st.cache_data
def get_stock_data(stock_code):
    try:
        # 台股代碼在 Yahoo Finance 需要加上 ".TW" (例如 2330.TW)
        ticker = f"{stock_code}.TW"
        
        # 抓取從 2023 年初至今的資料
        # auto_adjust=False 確保我們拿到的是原始的 OHLC，而不是調整後的
        df = yf.download(ticker, start="2023-01-01", auto_adjust=False)
        
        if df.empty:
            st.warning(f"找不到 {stock_code} 的資料，請確認代碼是否正確。")
            return pd.DataFrame()

        # --- 資料整理 ---
        # Yahoo Finance 的欄位名稱通常是首字大寫 (Open, High...)
        # 但我們後面的程式碼都用小寫 (open, high...)，所以這裡要統一轉小寫
        df.columns = [c.lower() for c in df.columns]
        
        # 確保索引名稱是 date (yfinance 預設索引就是 Date)
        df.index.name = 'date'
        
        # 處理可能的 MultiIndex (某些新版 yfinance 會有多層欄位)
        if isinstance(df.columns, pd.MultiIndex):
             df.columns = df.columns.get_level_values(0)

        # 轉換時區 (Yahoo 有時會帶時區，mplfinance 不喜歡時區)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        return df

    except Exception as e:
        st.error(f"資料抓取失敗: {e}")
        return pd.DataFrame()

# ---------------------------------------------------------
# 2. 計算指標的函數 (維持不變，已包含均線)
# ---------------------------------------------------------
def calculate_indicators(df):
    # --- 計算均線 (MA) ---
    df['MA5'] = df['close'].rolling(window=5).mean()
    df['MA10'] = df['close'].rolling(window=10).mean()
    df['MA20'] = df['close'].rolling(window=20).mean()
    df['MA60'] = df['close'].rolling(window=60).mean()

    # --- 計算 KD (隨機指標) ---
    df['RSV'] = (df['close'] - df['low'].rolling(9).min()) / (df['high'].rolling(9).max() - df['low'].rolling(9).min()) * 100
    df['K'] = df['RSV'].ewm(com=2).mean()
    df['D'] = df['K'].ewm(com=2).mean()

    # --- 計算 MACD ---
    exp12 = df['close'].ewm(span=12, adjust=False).mean()
    exp26 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp12 - exp26
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['Hist'] = df['MACD'] - df['Signal']
    
    return df

# ---------------------------------------------------------
# 3. 主程式介面 (維持不變)
# ---------------------------------------------------------
st.title("股票技術分析儀表板")
stock_code = st.text_input("輸入股票代碼", "2330")

if stock_code:
    # 步驟 A: 下載資料
    df = get_stock_data(stock_code)
    
    if not df.empty:
        # 步驟 B: 計算指標
        df = calculate_indicators(df)

        # 步驟 C: 介面控制
        col1, col2 = st.columns(2)
        with col1:
            selected_mas = st.multiselect("選擇均線 (MA)", ["MA5", "MA10", "MA20", "MA60"], default=["MA5", "MA20", "MA60"])
        with col2:
            options = st.multiselect("選擇副圖指標", ["Volume", "KD", "MACD"], default=["Volume", "KD"])

        # -----------------------------------------------------
        # 4. 核心畫圖邏輯
        # -----------------------------------------------------
        add_plots = []
        
        # 均線顏色設定
        ma_colors = {'MA5': 'orange', 'MA10': 'cyan', 'MA20': 'purple', 'MA60': 'green'}
        for ma in selected_mas:
            if ma in df.columns: # 確保有算出來才畫
                add_plots.append(mpf.make_addplot(df[ma], panel=0, color=ma_colors[ma], width=1.0))

        # 副圖設定
        panel_id = 0 
        
        # 判斷成交量
        show_vol = False
        if "Volume" in options:
            panel_id += 1
            show_vol = True
            
        # 判斷 KD
        if "KD" in options:
            panel_id += 1
            add_plots.append(mpf.make_addplot(df['K'], panel=panel_id, color='orange', title='KD'))
            add_plots.append(mpf.make_addplot(df['D'], panel=panel_id, color='blue'))

        # 判斷 MACD
        if "MACD" in options:
            panel_id += 1
            add_plots.append(mpf.make_addplot(df['MACD'], panel=panel_id, color='red', title='MACD'))
            add_plots.append(mpf.make_addplot(df['Signal'], panel=panel_id, color='blue'))
            add_plots.append(mpf.make_addplot(df['Hist'], type='bar', panel=panel_id, color='gray', alpha=0.5))

        # 調整比例
        current_ratios = [2] + [1] * panel_id

        st.write(f"目前顯示: {stock_code} (來源: Yahoo Finance)")
        
        # 畫圖
        fig, axlist = mpf.plot(
            df, 
            type='candle', 
            style='yahoo', 
            volume=show_vol, 
            addplot=add_plots, 
            returnfig=True,
            panel_ratios=tuple(current_ratios),
            figsize=(10, 8),
            title=f"{stock_code} Daily Chart"
        )
        st.pyplot(fig)
