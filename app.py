import streamlit as st
import yfinance as yf
import pandas as pd
import mplfinance as mpf
import time
import requests
from bs4 import BeautifulSoup
import numpy as np

# ==========================================
# 1. 資料抓取函數
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
            temp_df = stock.history(period="500d", auto_adjust=False)
            
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
# 2. 獲取公司名稱
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
