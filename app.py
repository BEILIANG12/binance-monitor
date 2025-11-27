import streamlit as st
import pandas as pd
import requests
import re

# --- 1. 页面配置 ---
st.set_page_config(page_title="币安 Alpha 监控系统", layout="wide")
st.title("🛡️ 币安 Alpha 代币稳定度监控")

# --- 2. 侧边栏设置 ---
st.sidebar.header("⚙️ 监控设置")

# 模式选择
mode = st.sidebar.radio(
    "选择模式：",
    ("🚀 监控所有 USDT 币种", "🎯 仅监控指定币种 (Alpha)")
)

# 如果选择了“指定币种”，显示输入框
target_coins = []
if "仅监控" in mode:
    st.sidebar.markdown("---")
    user_input = st.sidebar.text_area(
        "在此粘贴币种名称 (用空格或逗号分开)",
        value="BTC ETH SOL MERL POPCAT", # 默认示例
        height=150,
        help="例如从网页上复制：BTC, ETH, BNB"
    )
    # 处理用户输入的文本：将逗号、换行都替换为空格，然后转大写
    clean_input = re.sub(r'[,\n]', ' ', user_input).upper()
    target_coins = [c for c in clean_input.split(' ') if c]

st.sidebar.markdown("---")
min_vol = st.sidebar.slider("过滤：最小成交额 (百万 USDT)", 0.0, 100.0, 1.0)

# --- 3. 获取数据函数 (带多节点容灾) ---
@st.cache_data(ttl=60)
def get_binance_data():
    urls = [
        "https://api.binance.us/api/v3/ticker/24hr", # 美国节点（抗封锁）
        "https://api.binance.com/api/v3/ticker/24hr",
        "https://data-api.binance.vision/api/v3/ticker/24hr"
    ]
    status_msg = st.empty()
    
    for url in urls:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                status_msg.empty()
                return response.json()
        except:
            continue
            
    status_msg.error("无法连接币安接口，请检查网络。")
    return []

# --- 4. 主逻辑 ---
data = get_binance_data()

if data:
    df = pd.DataFrame(data)
    
    # 基础清洗：只看 USDT 交易对
    df = df[df['symbol'].str.endswith('USDT')]
    
    # 类型转换
    cols = ['lastPrice', 'highPrice', 'lowPrice', 'quoteVolume']
    for c in cols:
        df[c] = pd.to_numeric(df[c])

    # --- 核心逻辑：根据模式筛选 ---
    if "仅监控" in mode and target_coins:
        # 构建正则匹配：比如用户输入 "BTC"，我们匹配 "BTCUSDT"
        # 这里的逻辑是：只要交易对包含用户输入的任何一个词，就保留
        pattern = '|'.join(target_coins)
        # 严格匹配：确保是 "BTC" + "USDT"，防止输入 "T" 匹配到 "USDT"
        # 简单起见，我们筛选 symbol 包含 (用户输入币种 + USDT)
        
        filtered_dfs = []
        for coin in target_coins:
            # 尝试精准匹配，例如 BTC -> BTCUSDT
            match = df[df['symbol'] == f"{coin}USDT"]
            if not match.empty:
                filtered_dfs.append(match)
        
        if filtered_dfs:
            df = pd.concat(filtered_dfs)
        else:
            st.warning(f"⚠️ 未找到您输入的币种数据。请确保这些币（{user_input}）已在币安现货交易上线。")
            df = pd.DataFrame() # 空表

    if not df.empty:
        # 计算波动率
        df = df[df['lowPrice'] > 0]
        df['波动率(%)'] = ((df['highPrice'] - df['lowPrice']) / df['lowPrice']) * 100
        df['成交额(M)'] = df['quoteVolume'] / 1000000
        
        # 应用成交额过滤
        df_show = df[df['成交额(M)'] >= min_vol].copy()
        
        # 排序
        df_show = df_show.sort_values("波动率(%)")
        
        # 显示结果信息
        st.subheader(f"📊 监控报告：共 {len(df_show)} 个币种")
        
        # 绘制表格
        st.dataframe(
            df_show[['symbol', 'lastPrice', '波动率(%)', '成交额(M)']].style.format({
                "lastPrice": "{:.4f}",
                "波动率(%)": "{:.2f}%",
                "成交额(M)": "{:.2f} M"
            }).background_gradient(subset=['波动率(%)'], cmap='RdYlGn_r'),
            use_container_width=True,
            height=800
        )
    else:
        if "仅监控" not in mode:
            st.warning("数据为空，请检查网络。")
