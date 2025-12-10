import streamlit as st
import yfinance as yf
import pandas as pd
import mplfinance as mpf

# ==========================================
# 1. 資料抓取函數
# ==========================================
@st.cache_data
def get_stock_data(stock_code):
    try:
        ticker = f"{stock_code}.TW"
        df = yf.download(ticker, start="2023-01-01", auto_adjust=False)
        
        if df.empty:
            return pd.DataFrame()

        # 處理 MultiIndex (移除第一層)
        if isinstance(df.columns, pd.MultiIndex):
             df.columns = df.columns.get_level_values(0)
        
        # 轉小寫
        df.columns = [str(c).lower() for c in df.columns]
        
        # 處理索引與時區
        df.index.name = 'date'
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        return df

    except Exception as e:
        st.error(f"Error: {e}")
        return pd.DataFrame()

# ==========================================
# 2. 指標計算函數
# ==========================================
def calculate_indicators(df):
    df = df.copy()
    try:
        # --- 均線 ---
        if len(df) >= 5: df['MA5'] = df['close'].rolling(5).mean()
        if len(df) >= 10: df['MA10'] = df['close'].rolling(10).mean()
        if len(df) >= 20: df['MA20'] = df['close'].rolling(20).mean()
        if len(df) >= 60: df['MA60'] = df['close'].rolling(60).mean()

        # --- KD ---
        rsv_min = df['low'].rolling(9).min()
        rsv_max = df['high'].rolling(9).max()
        df['RSV'] = (df['close'] - rsv_min) / (rsv_max - rsv_min) * 100
        df['K'] = df['RSV'].ewm(com=2).mean()
        df['D'] = df['K'].ewm(com=2).mean()

        # --- MACD ---
        exp12 = df['close'].ewm(span=12, adjust=False).mean()
        exp26 = df['close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp12 - exp26
        df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['Hist'] = df['MACD'] - df['Signal']
    except Exception:
        pass
    
    return df

# ==========================================
# 3. 訊號判斷邏輯
# ==========================================
def analyze_signals(df):
    if len(df) < 2: return ["資料不足，無法分析"]
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    signals = []

    # 1. 均線排列
    check_ma = 'MA5' in df.columns and 'MA20' in df.columns and 'MA60' in df.columns
    if check_ma:
        if last['MA5'] > last['MA20'] and last['MA20'] > last['MA60']:
            signals.append("🔥 **均線多頭排列**：短中長期均線向上，趨勢偏多。")
        elif last['MA5'] < last['MA20'] and last['MA20'] < last['MA60']:
            signals.append("❄️ **均線空頭排列**：短中長期均線向下，趨勢偏空。")

    # 2. KD 指標
    if not pd.isna(last['K']) and not pd.isna(last['D']):
        if last['K'] > last['D'] and prev['K'] < prev['D']:
            signals.append("📈 **KD黃金交叉**：K值向上突破D值。")
        elif last['K'] < last['D'] and prev['K'] > prev['D']:
            signals.append("📉 **KD死亡交叉**：K值向下跌破D值。")
    
    # 3. MACD 指標
    if not pd.isna(last['Hist']):
        if last['Hist'] > 0 and prev['Hist'] < 0:
            signals.append("🟢 **MACD 翻紅**：柱狀體轉正，買氣增強。")
        elif last['Hist'] < 0 and prev['Hist'] > 0:
            signals.append("🔴 **MACD 翻綠**：柱狀體轉負，賣壓增強。")

    if not signals:
        signals.append("⚖️ 目前無明顯技術訊號。")

    return signals

# ==========================================
# 4. 黃金分割率
# ==========================================
def calculate_fibonacci(df):
    subset = df.tail(120)
    high = subset['high'].max()
    low = subset['low'].min()
    diff = high - low
    
    levels = {}
    levels['0.0 (近期低點)'] = low
    levels['0.382 (強支撐)'] = low + diff * 0.382
    levels['0.5 (中關)'] = low + diff * 0.5
    levels['0.618 (壓力)'] = low + diff * 0.618
    levels['1.0 (近期高點)'] = high
    return levels

# ==========================================
# 5. 主程式介面
# ==========================================
st.title("📈 股票技術分析儀表板")

col1, col2 = st.columns([1, 2])
with col1:
    stock_code = st.text_input("輸入股票代碼", "2330")
with col2:
    st.caption("請輸入代碼 (例如: 2330, 0050)")

if stock_code:
    df = get_stock_data(stock_code)
    
    if df.empty:
        st.error("找不到資料，請檢查代碼。")
    else:
        df = calculate_indicators(df)
        tab1, tab2, tab3 = st.tabs(["📊 K線圖", "💡 訊號", "📐 黃金分割"])

        # === Tab 1: K線圖 ===
        with tab1:
            c1, c2 = st.columns(2)
            with c1:
                mas = st.multiselect("均線", ["MA5","MA10","MA20","MA60"], ["MA5","MA20","MA60"])
            with c2:
                inds = st.multiselect("副圖", ["Volume","KD","MACD"], ["Volume","KD"])

            add_plots = []
            ma_colors = {'MA5':'orange', 'MA10':'cyan', 'MA20':'purple', 'MA60':'green'}
            
            # 加入均線
            for ma in mas:
                if ma in df.columns:
                    # 使用變數拆分，避免語法錯誤
                    ap = mpf.make_addplot(df[ma], panel=0, color=ma_colors[ma], width=1.0)
                    add_plots.append(ap)

            panel_id = 0
            show_vol = False
            
            if "Volume" in inds:
                panel_id += 1
                show_vol = True
            
            if "KD" in inds:
                panel_id += 1
                add_plots.append(mpf.make_addplot(df['K'], panel=panel_id, color='orange'))
                add_plots.append(mpf.make_addplot(df['D'], panel=panel_id, color='blue'))

            if "MACD" in inds:
                panel_id += 1
                # 拆成短行，防止錯誤
                ap_macd = mpf.make_addplot(df['MACD'], panel=panel_id, color='red')
                add_plots.append(ap_macd)
                
                ap_signal = mpf.make_addplot(df['Signal'], panel=panel_id, color='blue')
                add_plots.append(ap_signal)
                
                ap_hist = mpf.make_addplot(df['Hist'], type='bar', panel=panel_id, color='gray', alpha=0.5)
                add_plots.append(ap_hist)

            ratios = [2] + [1] * panel_id

            try:
                fig, ax = mpf.plot(
                    df, type='candle', style='yahoo', volume=show_vol, 
                    addplot=add_plots, returnfig=True,
                    panel_ratios=tuple(ratios), figsize=(10, 8),
                    title=f"{stock_code}"
                )
                st.pyplot(fig)
            except Exception as e:
                st.error(f"繪圖錯誤: {e}")

        # === Tab 2: 訊號 ===
        with tab2:
            st.subheader("技術面解讀")
            signals = analyze_signals(df)
            for s in signals:
                st.write(s)
            st.metric("最新收盤價", f"{df.iloc[-1]['close']:.2f}")

        # === Tab 3: 黃金分割 ===
        with tab3:
            st.subheader("黃金分割率")
            fib = calculate_fibonacci(df)
            
            fib_data = []
            for k, v in fib.items():
                fib_data.append
