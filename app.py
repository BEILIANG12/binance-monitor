import streamlit as st
import pandas as pd
import requests

# 页面配置
st.set_page_config(page_title="币安 Alpha 监控", layout="wide")

# 缓存数据函数
@st.cache_data(ttl=60)
def get_data():
    # 尝试使用不同节点，防止云服务器 IP 被屏蔽
    urls = [
        "https://api.binance.com/api/v3/ticker/24hr",
        "https://api1.binance.com/api/v3/ticker/24hr",
        "https://data-api.binance.vision/api/v3/ticker/24hr"
    ]
    for url in urls:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return response.json()
        except:
            continue
    return []

# 主标题
st.title("🛡️ 币安 Alpha 代币稳定度监控")

# 获取数据
data = get_data()

if not data:
    st.error("无法连接到币安数据源，可能是云服务器 IP 限制。")
else:
    # 数据处理
    df = pd.DataFrame(data)
    # 筛选 USDT 对
    df = df[df['symbol'].str.endswith('USDT')]
    
    # 转换数值
    cols = ['lastPrice', 'highPrice', 'lowPrice', 'quoteVolume']
    for c in cols:
        df[c] = pd.to_numeric(df[c])
    
    # 计算波动率
    df = df[df['lowPrice'] > 0]
    df['波动率(%)'] = ((df['highPrice'] - df['lowPrice']) / df['lowPrice']) * 100
    df['成交额(M)'] = df['quoteVolume'] / 1000000

    # 侧边栏筛选
    st.sidebar.header("筛选选项")
    min_vol = st.sidebar.slider("最小成交额 (百万 USDT)", 0.0, 500.0, 10.0)
    
    # 过滤与排序
    df_show = df[df['成交额(M)'] >= min_vol].sort_values("波动率(%)")
    
    # 展示
    st.dataframe(
        df_show[['symbol', 'lastPrice', '波动率(%)', '成交额(M)']].style.format({
            "lastPrice": "{:.4f}",
            "波动率(%)": "{:.2f}%",
            "成交额(M)": "{:.2f} M"
        }).background_gradient(subset=['波动率(%)'], cmap='RdYlGn_r'),
        use_container_width=True,
        height=800
    )
