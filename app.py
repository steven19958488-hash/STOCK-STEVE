import streamlit as st
import yfinance as yf
import pandas as pd
import mplfinance as mpf
import twstock

# 設定頁面
st.set_page_config(layout="wide", page_title="史帝夫的股市分析室")

# --- 0. 輔助功能 ---
def get_stock_name(code):
    try:
        if code in twstock.codes:
            return twstock.codes[code].name
        return ""
    except:
        return ""

# --- 1. 抓取資料 ---
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
    df['min_low'] = df['Low'].rolling(9).min()
    df['max_high'] = df['High'].rolling(9).max()
    df['RSV'] = (df['Close'] - df['min_low']) / (df['max_high'] - df['min_low']) * 100
    df['K'] = df['RSV'].ewm(com=2, adjust=False).mean()
    df['D'] = df['K'].ewm(com=2, adjust=False).mean()
    
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

# --- 3. 🕵️ K線型態偵測 (超級加強版 - 8種型態) ---
def check_k_patterns(df):
    if len(df) < 3: return []
    
    # 取得最後三天資料
    d1 = df.iloc[-3] # 前前天
    d2 = df.iloc[-2] # 昨天
    d3 = df.iloc[-1] # 今天 (最新)
    
    signals = []
    
    # 輔助變數：計算實體長度與影線
    def get_features(row):
        open_p = row['Open']
        close_p = row['Close']
        high_p = row['High']
        low_p = row['Low']
        
        is_red = close_p > open_p
        body = abs(close_p - open_p)
        upper_shadow = high_p - max(close_p, open_p)
        lower_shadow = min(close_p, open_p) - low_p
        return is_red, body, upper_shadow, lower_shadow

    # 取得三天的特徵
    red1, body1, up1, low1 = get_features(d1)
    red2, body2, up2, low2 = get_features(d2)
    red3, body3, up3, low3 = get_features(d3)
    
    # --- 1. 🔥 多方砲 (Bullish Cannon) ---
    # 紅-黑-紅，且今天收盤突破前天收盤
    if red1 and (not red2) and red3:
        if d3['Close'] > d1['Close']:
            signals.append("🔥 **多方砲** (中繼再漲)：多頭強勢整理結束")

    # --- 2. ❄️ 空方砲 (Bearish Cannon) ---
    # 黑-紅-黑，且今天收盤跌破前天收盤
    if (not red1) and red2 and (not red3):
        if d3['Close'] < d1['Close']:
            signals.append("❄️ **空方砲** (中繼再跌)：空頭反彈結束")

    # --- 3. 🐂 多方吞噬 (Bullish Engulfing) ---
    # 昨天黑，今天紅，今天實體包住昨天實體
    if (not red2) and red3:
        if d3['Close'] > d2['Open'] and d3['Open'] < d2['Close']:
            signals.append("🐂 **多方吞噬** (底部反轉)：一舉吃掉昨天的賣壓")

    # --- 4. 🐻 空方吞噬 (Bearish Engulfing) ---
    # 昨天紅，今天黑，今天實體包住昨天實體
    if red2 and (not red3):
        if d3['Close'] < d2['Open'] and d3['Open'] > d2['Close']:
            signals.append("🐻 **空方吞噬** (頭部反轉)：賣壓湧現吃掉買盤")
            
    # --- 5. 🔨 錘子線 (Hammer) ---
    # 發生在下跌趨勢(簡單判斷昨天是黑K)，下影線長(實體2倍以上)，上影線短
    # 這裡只看今天是否符合
    if (not red2) and (low3 > body3 * 2) and (up3 < body3 * 0.5):
        signals.append("🔨 **錘子線** (探底回升)：低檔出現長下影線，有人抄底")

    # --- 6. 🌠 流星線 (Shooting Star) ---
    # 發生在依樣趨勢(昨天紅K)，上影線長，下影線短
    if red2 and (up3 > body3 * 2) and (low3 < body3 * 0.5):
        signals.append("🌠 **流星線** (高檔變盤)：高檔出現長上影線，有人倒貨")

    # --- 7. 🌅 晨星 (Morning Star) ---
    # 第一根長黑，第二根小實體(星)，第三根長紅插入第一根實體內
    # 這是非常強的底部訊號
    if (not red1) and (body1 > d1['Open']*0.015) and \
       (body2 < body1 * 0.3) and \
       red3 and (d3['Close'] > (d1['Open'] + d1['Close'])/2):
        signals.append("🌅 **晨星轉折** (強力見底)：黑K後跳空整理再大漲")

    # --- 8. 🌃 夜星 (Evening Star) ---
    # 第一根長紅，第二根小實體，第三根長黑
    if red1 and (body1 > d1['Open']*0.015) and \
       (body2 < body1 * 0.3) and \
       (not red3) and (d3['Close'] < (d1['Open'] + d1['Close'])/2):
        signals.append("🌃 **夜星轉折** (強力見頂)：紅K後跳空整理再大跌")
        
    # --- 9. 💂 紅三兵 (Three White Soldiers) ---
    # 連續三根紅K，且收盤價一底比一底高
    if red1 and red2 and red3:
        if d3['Close'] > d2['Close'] > d1['Close']:
             signals.append("💂 **紅三兵** (多頭進攻)：連續三天上漲")
             
    # --- 10. 🐦 黑三鴉 (Three Black Crows) ---
    # 連續三根黑K
    if (not red1) and (not red2) and (not red3):
        if d3['Close'] < d2['Close'] < d1['Close']:
             signals.append("🐦 **黑三鴉** (空頭殺盤)：連續三天殺盤")

    return signals

# --- 4. 介面設定 ---
with st.sidebar:
    st.header("⚙️ 參數設定")
    code = st.text_input("輸入股票代碼", "2330")
    stock_name = get_stock_name(code)
    if stock_name:
        st.success(f"已選取：{stock_name}")
    
    st.markdown("---")
    st.write("顯示指標：")
    show_vol = st.checkbox("成交量", value=True)
    show_kd = st.checkbox("KD 指標", value=True)
    show_macd = st.checkbox("MACD 指標", value=False)

if stock_name:
    st.title(f"📊 {code} {stock_name} - 全方位分析")
else:
    st.title("📊 史帝夫股市分析 (Yahoo 豪華版)")

# --- 5. 主畫面 ---
if code:
    df = get_data(code)
    if df is not None and len(df) > 0:
        df = add_indicators(df)
        
        # A. 數據看板
        last_close = df['Close'].iloc[-1]
        change = last_close - df['Close'].iloc[-2]
        pct = (change / df['Close'].iloc[-2]) * 100
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("收盤價", f"{last_close:.2f}", f"{change:.2f}")
        c2.metric("漲跌幅", f"{pct:.2f}%")
        c3.metric("成交量", f"{int(df['Volume'].iloc[-1]):,}")
        c4.metric("K值", f"{df['K'].iloc[-1]:.2f}")

        # --- B. 🕵️ K線型態偵測 (新版) ---
        st.markdown("### 🕵️ K線型態偵測 (AI 訊號)")
        signals = check_k_patterns(df)
        
        if signals:
            for sig in signals:
                # 簡單判斷顏色：多/紅/晨/錘 顯示綠色，空/黑/夜/流星 顯示紅色
                if any(x in sig for x in ["多", "紅", "晨", "錘", "Bullish"]):
                    st.success(f"✅ {sig}")
                else:
                    st.error(f"⚠️ {sig}")
        else:
            st.info("💡 目前近三日無明顯特殊型態 (無連續大漲/大跌或反轉訊號)")

        # C. K線圖
        st.subheader(f"📈 走勢圖")
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
        
        # D. 黃金分割率
        st.markdown("---")
        st.subheader("🏆 黃金分割率")
        high, low, levels = calculate_golden_ratio(df)
        g_data = {
            "位置": ["波段高點", "0.809", "0.618 (強關)", "0.500 (中關)", "0.382 (弱關)", "0.191", "波段低點"],
            "價格": [high, levels['0.809'], levels['0.618'], levels['0.5'], levels['0.382'], levels['0.191'], low]
        }
        st.dataframe(pd.DataFrame(g_data).style.format({"價格": "{:.2f}"}), use_container_width=True)
            
    else:
        st.error("查無資料，請確認代碼。")
