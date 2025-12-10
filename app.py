import streamlit as st
import twstock
import pandas as pd
import mplfinance as mpf

st.title("📈 股票技術分析 (經典版)")

# --- 1. 抓取資料 ---
@st.cache_data(ttl=3600)
def get_data(code):
    try:
        stock = twstock.Stock(code)
        data = stock.fetch_from(2024, 1)
        if not data: return None
        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        return df
    except: return None

# --- 2. 計算指標 ---
def add_indicators(df):
    # KD
    df['min_low'] = df['low'].rolling(9).min()
    df['max_high'] = df['high'].rolling(9).max()
    df['RSV'] = (df['close'] - df['min_low']) / (df['max_high'] - df['min_low']) * 100
    df['K'] = df['RSV'].ewm(com=2).mean()
    df['D'] = df['K'].ewm(com=2).mean()
    # MACD
    exp12 = df['close'].ewm(span=12).mean()
    exp26 = df['close'].ewm(span=26).mean()
    df['MACD'] = exp12 - exp26
    df['Signal'] = df['MACD'].ewm(span=9).mean()
    df['Hist'] = df['MACD'] - df['Signal']
    return df

# --- 3. 介面 ---
code = st.text_input("輸入股票代碼", "2330")
opts = st.multiselect("選擇指標", ["Volume", "KD", "MACD"], ["Volume", "KD"])

if code:
    df = get_data(code)
    if df is not None and len(df) > 0:
        df = add_indicators(df)
        
        add_plots = []
        panels = [4]
        pid = 0
        
        if "Volume" in opts:
            pid += 1; panels.append(1)
        if "KD" in opts:
            pid += 1; panels.append(1.5)
            add_plots.append(mpf.make_addplot(df['K'], panel=pid, color='orange', title='KD'))
            add_plots.append(mpf.make_addplot(df['D'], panel=pid, color='blue'))
        if "MACD" in opts:
            pid += 1; panels.append(1.5)
            add_plots.append(mpf.make_addplot(df['MACD'], panel=pid, color='red', title='MACD'))
            add_plots.append(mpf.make_addplot(df['Signal'], panel=pid, color='blue'))
            add_plots.append(mpf.make_addplot(df['Hist'], type='bar', panel=pid, color='gray', alpha=0.5))

        fig, ax = mpf.plot(df, type='candle', style='yahoo', volume=("Volume" in opts), addplot=add_plots, panel_ratios=panels, returnfig=True, figsize=(10, 8))
        st.pyplot(fig)
    else:
        st.error("查無資料")
