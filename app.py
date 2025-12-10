import streamlit as st
import yfinance as yf
import pandas as pd
import mplfinance as mpf
import twstock

# 設定頁面寬度
st.set_page_config(layout="wide", page_title="史帝夫的股市分析室")

# --- 0. 輔助功能：取得股票中文名稱 ---
def get_stock_name(code):
    try:
        # 使用 twstock 的內建字典查代碼，這不需要連網，所以不會被擋
        if code in twstock.codes:
            return twstock.codes[code].name
        return ""
    except:
        return ""

# --- 1. 抓取資料 (Yahoo Finance) ---
@st.cache_data(ttl=3600)
def get_data(code):
    stock_id = f"{code}.TW"
    try:
        ticker = yf.Ticker(stock_id)
        df = ticker.history(period="1y")
        
        if df.empty:
            stock_id = f"{code}.TWO"
            ticker = yf.Ticker(stock_id)
            df = ticker.history(period="1y")
        
        if df.empty: return None
        return df
    except: return None

# --- 2. 計算指標 ---
def add_indicators(df):
    # KD
    df['min_low'] = df['Low'].rolling(9).min()
    df['max_high'] = df['High'].rolling(9).max()
    df['RSV'] = (df['Close'] - df['min_low']) / (df['max_high'] - df['min_low']) * 100
    df['K'] = df['RSV'].ewm(com=2, adjust=False).mean()
    df['D'] = df['K'].ewm(com=2, adjust=False).mean()
    
    # MACD
    exp12 = df['Close'].ewm(span=12, adjust=False).mean()
    exp26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp12 - exp26
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['Hist'] = df['MACD'] - df['Signal']
    return df

def calculate_golden_ratio(df):
    recent_df = df.tail(120)
    highest = recent_df['High'].max()
    lowest = recent_df['Low'].min()
    diff = highest - lowest
    ratios = [0.191, 0.382, 0.5, 0.618, 0.809]
    levels = {}
    for r in ratios: levels[f"{r}"] = lowest + (diff * r)
    return highest, lowest, levels

# --- 3. 側邊欄與標題 ---
with st.sidebar:
    st.header("⚙️ 參數設定")
    code = st.text_input("輸入股票代碼", "2330")
    
    # 在側邊欄也顯示名字，確認有沒有抓到
    stock_name = get_stock_name(code)
    if stock_name:
        st.success(f"已選取：{stock_name}")
    
    st.markdown("---")
    st.write("顯示指標：")
    show_vol = st.checkbox("成交量 (Volume)", value=True)
    show_kd = st.checkbox("KD 指標", value=True)
    show_macd = st.checkbox("MACD 指標", value=False)

# 主標題 (動態顯示：2330 台積電)
if stock_name:
    st.title(f"📊 {code} {stock_name} - 技術分析")
else:
    st.title("📊 史帝夫股市分析 (Yahoo 豪華版)")

# --- 4. 主畫面邏輯 ---
if code:
    df = get_data(code)
    if df is not None and len(df) > 0:
        df = add_indicators(df)
        
        # A. 數據看板
        last_close = df['Close'].iloc[-1]
        prev_close = df['Close'].iloc[-2]
        change = last_close - prev_close
        pct_change = (change / prev_close) * 100
        last_vol = df['Volume'].iloc[-1]
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("收盤價", f"{last_close:.2f}", f"{change:.2f}")
        col2.metric("漲跌幅", f"{pct_change:.2f}%")
        col3.metric("成交量", f"{int(last_vol):,}")
        col4.metric("K值", f"{df['K'].iloc[-1]:.2f}")

        # B. 畫圖
        st.subheader(f"📈 {stock_name} ({code}) 走勢圖")
        add_plots = []
        panels = [4]
        pid = 0
        
        if show_vol: pid += 1; panels.append(1)
        
        if show_kd:
            pid += 1; panels.append(1.5)
            add_plots.append(mpf.make_addplot(df['K'], panel=pid, color='orange', title='KD'))
            add_plots.append(mpf.make_addplot(df['D'], panel=pid, color='blue'))
            
        if show_macd:
            pid += 1; panels.append(1.5)
            add_plots.append(mpf.make_addplot(df['MACD'], panel=pid, color='red', title='MACD'))
            add_plots.append(mpf.make_addplot(df['Signal'], panel=pid, color='blue'))
            add_plots.append(mpf.make_addplot(df['Hist'], type='bar', panel=pid, color='gray', alpha=0.5))

        fig, ax = mpf.plot(df, type='candle', style='yahoo', volume=show_vol, addplot=add_plots, panel_ratios=panels, returnfig=True, figsize=(12, 8))
        st.pyplot(fig)
        
        # C. 黃金分割率
        st.markdown("---")
        st.subheader(f"🏆 {stock_name} 黃金分割率分析")
        high, low, levels = calculate_golden_ratio(df)
        golden_data = {
            "關鍵位置": ["波段高點", "0.809", "0.618 (支撐/壓力)", "0.500 (中關)", "0.382", "0.191", "波段低點"],
            "價格": [high, levels['0.809'], levels['0.618'], levels['0.5'], levels['0.382'], levels['0.191'], low]
        }
        st.dataframe(pd.DataFrame(golden_data).style.format({"價格": "{:.2f}"}), use_container_width=True)
            
    else:
        st.error(f"找不到 {code} 的資料，請確認代碼。")
