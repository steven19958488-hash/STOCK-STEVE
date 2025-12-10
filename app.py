import streamlit as st
import yfinance as yf
import pandas as pd
import mplfinance as mpf

# ==========================================
# 1. 資料抓取函數 (回傳 DataFrame 與 股票代號)
# ==========================================
@st.cache_data(ttl=3600)
def get_stock_data_v2(stock_code):
    stock_code = str(stock_code).strip()
    suffixes = [".TW", ".TWO"]
    
    df = pd.DataFrame()
    found_ticker = ""

    for suffix in suffixes:
        try:
            ticker = f"{stock_code}{suffix}"
            temp_df = yf.download(ticker, start="2023-01-01", progress=False)
            
            if not temp_df.empty:
                df = temp_df
                found_ticker = ticker # 記住成功的代號
                break
        except Exception:
            continue

    if df.empty:
        return pd.DataFrame(), ""

    # --- 資料清洗 ---
    try:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        df.columns = [str(c).lower() for c in df.columns]
        
        df.index.name = 'date'
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
            
        return df, found_ticker
    except Exception as e:
        return pd.DataFrame(), ""

# ==========================================
# 2. 獲取公司名稱 (新增功能)
# ==========================================
@st.cache_data(ttl=86400) # 名稱快取存一天
def get_stock_info(ticker_symbol):
    try:
        t = yf.Ticker(ticker_symbol)
        info = t.info
        # 嘗試抓取長名稱或短名稱
        return info.get('longName') or info.get('shortName') or ticker_symbol
    except:
        return ticker_symbol

# ==========================================
# 3. 指標計算函數
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
        rsv_den = rsv_max - rsv_min
        rsv_den[rsv_den == 0] = 1 
        
        df['RSV'] = (df['close'] - rsv_min) / rsv_den * 100
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
# 4. 訊號判斷邏輯
# ==========================================
def analyze_signals(df):
    if len(df) < 2: return ["資料不足，無法分析"]
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    signals = []

    # 均線
    check_ma = 'MA5' in df.columns and 'MA20' in df.columns and 'MA60' in df.columns
    if check_ma:
        if last['MA5'] > last['MA20'] and last['MA20'] > last['MA60']:
            signals.append("🔥 **均線多頭排列**：趨勢偏多。")
        elif last['MA5'] < last['MA20'] and last['MA20'] < last['MA60']:
            signals.append("❄️ **均線空頭排列**：趨勢偏空。")

    # KD
    if 'K' in df.columns and 'D' in df.columns:
        if last['K'] > last['D'] and prev['K'] < prev['D']:
            signals.append("📈 **KD黃金交叉**：短線轉強。")
        elif last['K'] < last['D'] and prev['K'] > prev['D']:
            signals.append("📉 **KD死亡交叉**：短線轉弱。")
    
    # MACD
    if 'Hist' in df.columns:
        if last['Hist'] > 0 and prev['Hist'] < 0:
            signals.append("🟢 **MACD 翻紅**：買氣增強。")
        elif last['Hist'] < 0 and prev['Hist'] > 0:
            signals.append("🔴 **MACD 翻綠**：賣壓增強。")

    if not signals:
        signals.append("⚖️ 目前無明顯技術訊號。")
    return signals

# ==========================================
# 5. 黃金分割率
# ==========================================
def calculate_fibonacci(df):
    subset = df.tail(120)
    high = subset['high'].max()
    low = subset['low'].min()
    diff = high - low
    levels = {}
    levels['0.0 (低)'] = low
    levels['0.382 (支撐)'] = low + diff * 0.382
    levels['0.5 (中關)'] = low + diff * 0.5
    levels['0.618 (壓力)'] = low + diff * 0.618
    levels['1.0 (高)'] = high
    return levels

# ==========================================
# 6. 主程式介面
# ==========================================
st.title("📈 股票技術分析儀表板")

# --- 版面調整 ---
col1, col2 = st.columns([1, 2])

with col1:
    stock_code = st.text_input("輸入股票代碼", "2330")

# 先抓取資料，才能決定 col2 要顯示什麼
df, valid_ticker = get_stock_data_v2(stock_code)

with col2:
    if not df.empty and valid_ticker:
        # 抓取名稱與計算漲跌
        stock_name = get_stock_info(valid_ticker)
        last_price = df.iloc[-1]['close']
        prev_price = df.iloc[-2]['close']
        change = last_price - prev_price
        pct_change = (change / prev_price) * 100
        
        # 顯示大字體資訊 (公司名稱 + 股價 + 漲跌幅)
        st.metric(
            label=f"{stock_name} ({stock_code})",
            value=f"{last_price:.2f}",
            delta=f"{change:.2f} ({pct_change:.2f}%)"
        )
    else:
        # 沒資料時顯示提示
        st.info("請輸入代碼 (如: 2330, 0050) 並按 Enter")

if not df.empty:
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
        
        for ma in mas:
            if ma in df.columns:
                add_plots.append(mpf.make_addplot(df[ma], panel=0, color=ma_colors[ma], width=1.0))

        panel_id = 0
        show_vol = False
        
        if "Volume" in inds:
            panel_id += 1
            show_vol = True
        
        if "KD" in inds and 'K' in df.columns:
            panel_id += 1
            add_plots.append(mpf.make_addplot(df['K'], panel=panel_id, color='orange'))
            add_plots.append(mpf.make_addplot(df['D'], panel=panel_id, color='blue'))

        if "MACD" in inds and 'MACD' in df.columns:
            panel_id += 1
            add_plots.append(mpf.make_addplot(df['MACD'], panel=panel_id, color='red'))
            add_plots.append(mpf.make_addplot(df['Signal'], panel=panel_id, color='blue'))
            add_plots.append(mpf.make_addplot(df['Hist'], type='bar', panel=panel_id, color='gray', alpha=0.5))

        ratios = [2] + [1] * panel_id

        try:
            fig, ax = mpf.plot(
                df, type='candle', style='yahoo', volume=show_vol, 
                addplot=add_plots, returnfig=True,
                panel_ratios=tuple(ratios), figsize=(10, 8),
                title=f"{stock_code} - {stock_name}"
            )
            st.pyplot(fig)
        except Exception as e:
            st.error(f"繪圖錯誤: {e}")

    # === Tab 2: 訊號 (移除重複的收盤價) ===
    with tab2:
        st.subheader("技術面解讀")
        signals = analyze_signals(df)
        for s in signals:
            st.write(s)

    # === Tab 3: 黃金分割 ===
    with tab3:
        st.subheader("黃金分割率")
        fib = calculate_fibonacci(df)
        
        fib_data = [{"位置": k, "價格": f"{v:.2f}"} for k, v in fib.items()]
        st.table(pd.DataFrame(fib_data))
        
        p382 = fib['0.382 (支撐)']
        p500 = fib['0.5 (中關)']
        st.info(f"回檔 {p382:.2f} 不破為強；跌破 {p500:.2f} 轉弱。")
