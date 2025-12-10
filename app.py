import streamlit as st

st.title("環境測試模式")
st.write("✅ Streamlit 正常運作中")

try:
    import yfinance as yf
    st.write(f"✅ yfinance 版本: {yf.__version__}")
except ImportError:
    st.error("❌ yfinance 沒有安裝成功！請檢查 requirements.txt")

try:
    import mplfinance as mpf
    st.write(f"✅ mplfinance 版本: {mpf.__version__}")
except ImportError:
    st.error("❌ mplfinance 沒有安裝成功！請檢查 requirements.txt")

st.write("如果不論如何都全白，代表是原本的程式碼縮排有問題。")
