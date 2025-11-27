import streamlit as st
import pandas as pd
import requests
import re

st.set_page_config(page_title="币安 Alpha 监控系统", layout="wide")
st.title("🛡️ 币安 Alpha 代币稳定度监控 (宽容搜索版)")

# --- 侧边栏 ---
st.sidebar.header("⚙️ 监控设置")
mode = st.sidebar.radio(
    "选择模式：",
    ("🚀 监控所有 USDT 币种", "🎯 仅监控指定币种 (Alpha)")
)

target_coins = []
if "仅监控" in mode:
    st.sidebar.markdown("---")
    st.sidebar.info("💡 提示：如果搜不到，说明该币种可能尚未在币安【现货交易所】上市，属于 Web3 链上币种。")
    user_input = st.sidebar.text_area(
        "在此粘贴币种名称",
        value="BTC ETH DOGE NEIRO", 
        height=100
    )
    clean_input = re.sub(r'[,\n]', ' ', user_input).upper()
    target_coins = [c for c in clean_input.split(' ') if c]

st.sidebar.markdown("---")
min_vol = st.sidebar.slider("过滤：最小成交额 (百万 USDT)", 0.0, 100.0, 0.0) # 默认设为0以防过滤掉小币

# --- 获取数据 ---
@st.cache_data(ttl=60)
def get_binance_data():
    urls = [
        "https://api.binance.us/api/v3/ticker/24hr",
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
    status_msg.error("无法连接数据源")
    return []

# --- 主程序 ---
data = get_binance_data()

if data:
    df = pd.DataFrame(data)
    
    # 这里我们先不急着过滤 USDT，保留所有数据以便模糊搜索
    # 转换数值
    cols = ['lastPrice', 'highPrice', 'lowPrice', 'quoteVolume']
    for c in cols:
        df[c] = pd.to_numeric(df[c])

    # 结果容器
    result_df = pd.DataFrame()

    if "仅监控" in mode and target_coins:
        found_frames = []
        not_found_list = []

        for coin in target_coins:
            # 1. 尝试精准匹配 USDT 对 (最常用)
            exact_match = df[df['symbol'] == f"{coin}USDT"]
            
            # 2. 如果没找到，尝试“模糊匹配” (包含这个名字的任何对)
            fuzzy_match = df[df['symbol'].str.contains(coin)]
            
            if not exact_match.empty:
                found_frames.append(exact_match)
            elif not fuzzy_match.empty:
                # 如果找到了模糊匹配（比如输入 DOGE 找到了 DOGETRY），也加进去
                found_frames.append(fuzzy_match)
            else:
                not_found_list.append(coin)
        
        # 显示找不到的名单
        if not_found_list:
            st.error(f"❌ 以下币种在币安现货未找到 (可能是 Web3/链上币): {', '.join(not_found_list)}")
            
        if found_frames:
            result_df = pd.concat(found_frames).drop_duplicates()
    else:
        # 全量模式，默认只看 USDT
        result_df = df[df['symbol'].str.endswith('USDT')]

    # --- 展示逻辑 ---
    if not result_df.empty:
        # 计算逻辑
        result_df = result_df[result_df['lowPrice'] > 0]
        result_df['波动率(%)'] = ((result_df['highPrice'] - result_df['lowPrice']) / result_df['lowPrice']) * 100
        result_df['成交额(M)'] = result_df['quoteVolume'] / 1000000
        
        # 再次过滤成交额
        final_show = result_df[result_df['成交额(M)'] >= min_vol].sort_values("波动率(%)")
        
        st.subheader(f"📊 监控报告：找到 {len(final_show)} 个交易对")
        
        st.dataframe(
            final_show[['symbol', 'lastPrice', '波动率(%)', '成交额(M)']].style.format({
                "lastPrice": "{:.6f}", # 增加小数位，防止小币种显示为0
                "波动率(%)": "{:.2f}%",
                "成交额(M)": "{:.2f} M"
            }).background_gradient(subset=['波动率(%)'], cmap='RdYlGn_r'),
            use_container_width=True,
            height=800
        )
    elif "仅监控" in mode:
        st.warning("您输入的币种全都没有找到。")

