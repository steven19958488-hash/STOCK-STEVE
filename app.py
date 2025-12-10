import streamlit as st
import yfinance as yf
import pandas as pd
import mplfinance as mpf
import time
import requests
from bs4 import BeautifulSoup
import numpy as np

# ==========================================
# 1. 資料抓取函數 (v3.1)
# ==========================================
@st.cache_data(ttl=3600)
def get_stock_data_v3(stock_code):
    stock_code = str(stock_code).strip()
    suffixes = [".TW", ".TWO"]
    
    df = pd.DataFrame()
    found_ticker = ""

    for suffix in suffixes:
        try:
            ticker = f"{stock_code}{suffix}"
            stock = yf.Ticker(ticker)
            temp_df = stock.history(start="2023-01-01", auto_adjust=False)
            
            if not temp_df.empty:
                df = temp_df
                found_ticker = ticker
                break
            time.sleep(0.5) 
        except Exception:
            continue

    if df.empty:
        return pd.DataFrame(), ""

    try:
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        df.columns = [str(c).lower() for c in df.columns]
        df.index.name = 'date'
        return df, found_ticker
    except Exception:
        return pd.DataFrame(), ""

# ==========================================
# 2. 獲取公司名稱 (混合版)
# ==========================================
@st.cache_data(ttl=86400)
def get_stock_name(stock_code):
    code = str(stock_code).strip()
    
    # 內建熱門股字典
    stock_map = {
        "0050": "元大台灣50", "0056": "元大高股息", "00878": "國泰永續高股息", "00929": "復華台灣科技優息",
        "00919": "群益台灣精選高息", "006208": "富邦台50", "00713": "元大台灣高息低波",
        "2330": "台積電", "2454": "聯發科", "2303": "聯電", "2317": "鴻海",
        "2308": "台達電", "3711": "日月光投控", "2382": "廣達", "3231": "緯創",
        "6669": "緯穎", "2357": "華碩", "2356": "英業達", "3008": "大立光",
        "3034": "聯詠", "2379": "瑞昱", "3037": "欣興", "3035": "智原",
        "3443": "創意", "3661": "世芯-KY", "5269": "祥碩", "2408": "南亞科",
        "2344": "華邦電", "5347": "世界先進", "6770": "力積電", "2353": "宏碁",
        "2324": "仁寶", "3017": "奇鋐", "3324": "雙鴻", "2376": "技嘉", "2377": "微星",
        "3293": "鈊象", "2603": "長榮", "2609": "陽明", "2615": "萬海", "2618": "長榮航",
        "2610": "華航", "2002": "中鋼", "1101": "台泥", "1102": "亞泥", "1605": "華新",
        "6505": "台塑化", "1301": "台塑", "1303": "南亞", "1326": "台化",
        "2881": "富邦金", "2882": "國泰金", "2891": "中信金", "2886": "兆豐金",
        "2884": "玉山金", "2885": "元大金", "2880": "華南金", "2883": "開發金",
        "2892": "第一金", "2890": "永豐金", "2887": "台新金", "5880": "合庫金"
    }
    if code in stock_map:
        return stock_map[code]

    # 爬取網頁 Title
    try:
        url = f"https://tw.stock.yahoo.com/quote/{code}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            title_text = soup.title.string
            if title_text and "(" in title_text:
                return title_text.split("(")[0].strip()
            return title_text
    except Exception:
        pass

    return code

# ==========================================
# 3. 指標計算 (新增 RSI, 布林通道)
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

        # --- 新增：RSI (14日) ---
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        # --- 新增：布林通道 (20日, 2倍標準差) ---
        df['BB_Mid'] = df['close'].rolling(window=20).mean()
        df['BB_Std'] = df['close'].rolling(window=20).std()
        df['BB_Up'] = df['BB_Mid'] + 2 * df['BB_Std']
        df['BB_Low'] = df['BB_Mid'] - 2 * df['BB_Std']

    except: pass
    return df

# ==========================================
# 4. 訊號分析 (大幅增強)
# ==========================================
def analyze_signals(df):
    if len(df) < 2: return ["資料不足"]
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    signals = []

    # 1. 均線排列與交叉
    if 'MA5' in df.columns and 'MA20' in df.columns:
        # 均線排列
        if last['MA5'] > last['MA20'] > last['MA60']: 
            signals.append("🔥 **趨勢**：多頭排列 (短中長期均線向上)。")
        elif last['MA5'] < last['MA20'] < last['MA60']: 
            signals.append("❄️ **趨勢**：空頭排列 (短中長期均線向下)。")
        
        # 均線黃金交叉 (5日穿過20日)
        if prev['MA5'] < prev['MA20'] and last['MA5'] > last['MA20']:
            signals.append("✨ **均線黃金交叉**：5日線向上突破月線，短線轉強。")
        # 均線死亡交叉
        elif prev['MA5'] > prev['MA20'] and last['MA5'] < last['MA20']:
            signals.append("💀 **均線死亡交叉**：5日線跌破月線，短線轉弱。")

    # 2. KD指標
    if 'K' in df.columns and 'D' in df.columns:
        if last['K'] > last['D'] and prev['K'] < prev['D']:
            val = f"(K={last['K']:.1f})"
            if last['K'] < 30:
                signals.append(f"📈 **KD低檔黃金交叉** {val}：強烈反彈訊號。")
            else:
                signals.append(f"📈 **KD黃金交叉** {val}：短線買進訊號。")
        elif last['K'] < last['D'] and prev['K'] > prev['D']:
            val = f"(K={last['K']:.1f})"
            if last['K'] > 80:
                signals.append(f"📉 **KD高檔死亡交叉** {val}：過熱修正訊號，留意回檔。")
            else:
                signals.append(f"📉 **KD死亡交叉** {val}：短線賣出訊號。")

    # 3. MACD指標
    if 'Hist' in df.columns:
        if last['Hist'] > 0 and prev['Hist'] < 0:
            signals.append("🟢 **MACD 翻紅**：空轉多，買方力道增強。")
        elif last['Hist'] < 0 and prev['Hist'] > 0:
            signals.append("🔴 **MACD 翻綠**：多轉空，賣方力道增強。")

    # 4. RSI 指標 (新增)
    if 'RSI' in df.columns and not pd.isna(last['RSI']):
        rsi_val = last['RSI']
        if rsi_val > 70:
            signals.append(f"⚠️ **RSI 過熱 ({rsi_val:.1f})**：短線可能過熱，隨時準備回檔。")
        elif rsi_val < 30:
            signals.append(f"💎 **RSI 超賣 ({rsi_val:.1f})**：股價可能超跌，有機會反彈。")

    # 5. 布林通道 (新增)
    if 'BB_Up' in df.columns:
        if last['close'] > last['BB_Up']:
            signals.append("🚀 **突破布林上軌**：股價極強勢，但也可能面臨拉回。")
        elif last['close'] < last['BB_Low']:
            signals.append("🌊 **跌破布林下軌**：股價極弱勢，但也可能出現乖離過大反彈。")

    # 6. K線型態 (新增：判斷當日紅黑棒)
    open_p = last['open']
    close_p = last['close']
    pct_change = (close_p - open_p) / open_p * 100
    
    if pct_change > 3:
        signals.append("🐂 **長紅K棒**：今日大漲超過 3%，買盤強勁。")
    elif pct_change < -3:
        signals.append("🐻 **長黑K棒**：今日大跌超過 3%，賣壓沉重。")
    elif abs(pct_change) < 0.2:
        signals.append("⚖️ **十字線/變盤線**：多空力道均衡，關注明日方向。")

    return signals if signals else ["⚖️ 目前盤勢震盪，無明顯單一訊號。"]

# ==========================================
# 5. 黃金分割
# ==========================================
def calculate_fibonacci(df):
    subset = df.tail(120)
    high = subset['high'].max()
    low = subset['low'].min()
    diff = high - low
    return {
        '0.0 (低)': low, '0.382 (支撐)': low + diff * 0.382,
        '0.5 (中關)': low + diff * 0.5, '0.618 (壓力)': low + diff * 0.618,
        '1.0 (高)': high
    }

# ==========================================
# 6. 主程式介面
# ==========================================
st.title("📈 股票技術分析儀表板")

col1, col2 = st.columns([1, 2])
with col1:
    stock_code = st.text_input("輸入代碼", "2330")

try:
    df, valid_ticker = get_stock_data_v3(stock_code)
except:
    st.error("系統忙碌中，請稍後再試")
    df = pd.DataFrame()

with col2:
    if not df.empty:
        name = get_stock_name(stock_code)
        last = df.iloc[-1]['close']
        prev = df.iloc[-2]['close']
        change = last - prev
        pct = (change / prev) * 100
        st.metric(label=f"{name} ({stock_code})", value=f"{last:.2f}", delta=f"{change:.2f} ({pct:.2f}%)")
    else:
        st.caption("請輸入代碼並按 Enter")

if not df.empty:
    df = calculate_indicators(df)
    tab1, tab2, tab3 = st.tabs(["📊 K線圖", "💡 訊號診斷", "📐 黃金分割"])

    with tab1:
        c1, c2 = st.columns(2)
        with c1: mas = st.multiselect("均線", ["MA5","MA10","MA20","MA60"], ["MA5","MA20","MA60"])
        with c2: inds = st.multiselect("副圖", ["Volume","KD","MACD","RSI"], ["Volume","KD"]) # 新增 RSI 選項

        add_plots = []
        colors = {'MA5':'orange', 'MA10':'cyan', 'MA20':'purple', 'MA60':'green'}
        
        for ma in mas:
            if ma in df.columns:
                add_plots.append(mpf.make_addplot(df[ma], panel=0, color=colors[ma], width=1.0))

        # 布林通道 (如果使用者想看，也可以加，這裡先預設不畫以免太亂，重點在訊號文字)
        
        pid = 0
        vol = False
        if "Volume" in inds: pid+=1; vol=True
        
        if "KD" in inds and 'K' in df.columns:
            pid+=1
            add_plots.append(mpf.make_addplot(df['K'], panel=pid, color='orange'))
            add_plots.append(mpf.make_addplot(df['D'], panel=pid, color='blue'))
            
        if "MACD" in inds and 'MACD' in df.columns:
            pid+=1
            add_plots.append(mpf.make_addplot(df['MACD'], panel=pid, color='red'))
            add_plots.append(mpf.make_addplot(df['Signal'], panel=pid, color='blue'))
            add_plots.append(mpf.make_addplot(df['Hist'], type='bar', panel=pid, color='gray', alpha=0.5))

        if "RSI" in inds and 'RSI' in df.columns:
            pid+=1
            add_plots.append(mpf.make_addplot(df['RSI'], panel=pid, color='#9b59b6', title='RSI'))
            # 畫出 70/30 參考線
            line_70 = [70] * len(df)
            line_30 = [30] * len(df)
            add_plots.append(mpf.make_addplot(line_70, panel=pid, color='gray', linestyle='dashed', width=0.8))
            add_plots.append(mpf.make_addplot(line_30, panel=pid, color='gray', linestyle='dashed', width=0.8))

        try:
            fig, ax = mpf.plot(
                df, type='candle', style='yahoo', volume=vol, 
                addplot=add_plots, returnfig=True,
                panel_ratios=tuple([2]+[1]*pid), figsize=(10, 8),
                title=f"Stock Code: {stock_code}",
                warn_too_much_data=10000
            )
            st.pyplot(fig)
        except Exception as e: st.error(f"Error: {e}")

    with tab2:
        st.subheader("🤖 AI 技術指標診斷")
        signals = analyze_signals(df)
        
        # 使用不同顏色區塊來顯示訊號
        for s in signals:
            if "多" in s or "黃金" in s or "紅" in s or "強" in s or "買" in s:
                st.success(s) # 綠色/好消息
            elif "空" in s or "死亡" in s or "綠" in s or "弱" in s or "賣" in s:
                st.error(s)   # 紅色/壞消息
            else:
                st.info(s)    # 藍色/中性消息
        
        st.divider()
        st.caption("說明：RSI > 70 為超買，< 30 為超賣。KD 黃金交叉代表短線轉強。")

    with tab3:
        st.subheader("黃金分割")
        fib = calculate_fibonacci(df)
        st.table(pd.DataFrame([{"位置":k, "價格":f"{v:.2f}"} for k,v in fib.items()]))
        st.info(f"觀察：{fib['0.382 (支撐)']:.2f} 為強支撐；跌破 {fib['0.5 (中關)']:.2f} 轉弱")
