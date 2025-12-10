import streamlit as st
import twstock
import pandas as pd
import mplfinance as mpf

# 設定網頁寬度為寬版，比較好看
st.set_page_config(layout="wide", page_title="史帝夫的股市分析室")

st.title("📊 史帝夫股市分析 (豪華完整版)")
st.caption("包含：K線圖、KD/MACD指標、黃金分割率分析、即時數據表格")

# --- 1. 抓取資料 (快取加速) ---
@st.cache_data(ttl=3600)
def get_data(code):
    try:
        stock = twstock.Stock(code)
        # 抓取近 180 天 (約半年) 的資料，這樣黃金分割率比較準
        data = stock.fetch_from(2024, 1)
        
        if not data:
            return None
            
        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # 轉成數字格式
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        return df
    except:
        return None

# --- 2. 計算指標 (KD, MACD, 黃金分割) ---
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

def calculate_golden_ratio(df):
    # 計算最近一段時間的最高與最低 (區間高低點)
    highest = df['high'].max()
    lowest = df['low'].min()
    diff = highest - lowest
    
    # 黃金分割率係數
    ratios = [0.191, 0.382, 0.5, 0.618, 0.809]
    levels = {}
    for r in ratios:
        levels[f"{r}"] = lowest + (diff * r)
        
    return highest, lowest, levels

# --- 3. 側邊欄設定 ---
with st.sidebar:
    st.header("⚙️ 設定參數")
    code = st.text_input("輸入股票代碼", "2330")
    st.markdown("---")
    st.write("選擇要顯示的技術指標：")
    show_vol = st.checkbox("成交量 (Volume)", value=True)
    show_kd = st.checkbox("KD 指標", value=True)
    show_macd = st.checkbox("MACD 指標", value=False)

# --- 4. 主畫面邏輯 ---
if code:
    df = get_data(code)
    
    if df is not None and len(df) > 0:
        df = add_indicators(df)
        
        # --- A. 顯示即時數據 (最上方一排) ---
        last_close = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        change = last_close - prev_close
        pct_change = (change / prev_close) * 100
        last_vol = df['volume'].iloc[-1]
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("收盤價", f"{last_close}", f"{change:.2f}")
        col2.metric("漲跌幅", f"{pct_change:.2f}%", delta_color="normal")
        col3.metric("成交量", f"{int(last_vol):,}")
        col4.metric("K值 (最新)", f"{df['K'].iloc[-1]:.2f}")

        # --- B. 繪製 K 線圖 (包含指標) ---
        st.subheader(f"📈 {code} K線走勢圖")
        
        add_plots = []
        panels = [4] # 主圖高度
        pid = 0
        
        if show_vol:
            pid += 1
            panels.append(1)
        
        if show_kd:
            pid += 1
            panels.append(1.5)
            add_plots.append(mpf.make_addplot(df['K'], panel=pid, color='orange', title='KD'))
            add_plots.append(mpf.make_addplot(df['D'], panel=pid, color='blue'))
            
        if show_macd:
            pid += 1
            panels.append(1.5)
            add_plots.append(mpf.make_addplot(df['MACD'], panel=pid, color='red', title='MACD'))
            add_plots.append(mpf.make_addplot(df['Signal'], panel=pid, color='blue'))
            add_plots.append(mpf.make_addplot(df['Hist'], type='bar', panel=pid, color='gray', alpha=0.5))

        fig, ax = mpf.plot(
            df, 
            type='candle', 
            style='yahoo', 
            volume=show_vol, 
            addplot=add_plots, 
            panel_ratios=panels, 
            returnfig=True, 
            figsize=(12, 8) # 圖表變大一點
        )
        st.pyplot(fig)
        
        # --- C. 黃金分割率分析 (表格) ---
        st.markdown("---")
        st.subheader("🏆 黃金分割率 (支撐/壓力位)")
        
        high, low, levels = calculate_golden_ratio(df)
        
        # 製作表格資料
        golden_data = {
            "位置": ["最高點 (High)", "0.809", "0.618 (強壓力/支撐)", "0.500 (中關)", "0.382 (弱支撐/壓力)", "0.191", "最低點 (Low)"],
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
        
        # 顯示漂亮的表格
        col_l, col_r = st.columns([1, 2])
        with col_l:
            st.dataframe(golden_df.style.format({"價格": "{:.2f}"}), use_container_width=True)
        with col_r:
            st.info("""
            **💡 黃金分割率使用說明：**
            * **0.618** 與 **0.382** 是最重要的回檔或反彈位置。
            * 當股價回檔至 0.618 附近未跌破，通常視為強勢整理。
            * 當股價跌破 0.5 甚至 0.382，代表趨勢可能轉弱。
            """)
            
    else:
        st.error("❌ 查無資料。原因可能是：股票代碼錯誤，或是雲端主機 IP 被證交所阻擋 (twstock 常見限制)。請稍後再試。")
