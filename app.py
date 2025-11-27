import streamlit as st
import pandas as pd
import requests
import time
import random

# --- 1. 页面配置 ---
st.set_page_config(page_title="币安 Web3 Alpha 监控", layout="wide")
st.title("🦄 币安 Web3 Alpha 代币监控系统")
st.markdown("数据源：**Binance Web3 Wallet (Alpha Section)** | 核心指标：**24H 波动率**")

# --- 2. 伪装请求头 (关键) ---
# 必须伪装成浏览器，否则 BAPI 会直接拒绝连接 (403 Forbidden)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.binance.com/en/web3/wallet/alpha",
    "Origin": "https://www.binance.com",
    "Content-Type": "application/json",
    "client-type": "web"
}

# --- 3. 获取代币列表 ---
@st.cache_data(ttl=300) # 列表 5 分钟刷新一次
def get_alpha_token_list():
    url = "https://www.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/cex/alpha/all/token/list"
    try:
        # 这是一个 POST 请求还是 GET？通常 list 是 GET，但也可能是 POST。
        # BAPI 很多都是 POST，这里先尝试 POST，带空 payload
        response = requests.post(url, headers=HEADERS, json={}, timeout=10)
        
        # 如果 POST 不行，尝试 GET
        if response.status_code != 200:
            response = requests.get(url, headers=HEADERS, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                # 提取列表，根据实际返回结构调整
                return data.get("data", [])
            else:
                st.error(f"API 业务逻辑错误: {data}")
        else:
            st.error(f"HTTP 请求失败: {response.status_code}")
    except Exception as e:
        st.error(f"连接列表接口出错: {e}")
    return []

# --- 4. 获取 K 线数据 (计算波动) ---
def get_token_klines(symbol):
    """
    查询指定币种的日线数据，计算波动率
    """
    url = "https://www.binance.com/bapi/defi/v1/public/alpha-trade/klines"
    
    # 参数猜测：通常需要 symbol 和 interval
    # 针对 Alpha 接口，通常 interval=1D 代表日线
    params = {
        "symbol": symbol,
        "interval": "1d",
        "limit": 1 # 只需要最新的一根 K 线
    }
    
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("data"):
                # 解析 K 线数据
                # 通常结构是: [Open Time, Open, High, Low, Close, Volume, ...]
                kline = data["data"][0] 
                
                # 注意：Web3 接口返回的数值可能是字符串，需要转换
                high = float(kline[2])
                low = float(kline[3])
                close = float(kline[4])
                
                return {
                    "high": high,
                    "low": low,
                    "close": close
                }
    except Exception as e:
        # 默默失败，不打断主循环
        pass
    return None

# --- 5. 主逻辑控制 ---

# 侧边栏设置
st.sidebar.header("⚙️ 设置")
max_items = st.sidebar.slider("分析代币数量 (防止请求过多卡死)", 5, 50, 20)

# 执行按钮
if st.button("🚀 开始加载 Alpha 数据"):
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    status_text.info("正在获取 Alpha 代币名单...")
    token_list_raw = get_alpha_token_list()
    
    if token_list_raw:
        st.success(f"成功获取名单，共 {len(token_list_raw)} 个代币。正在分析前 {max_items} 个...")
        
        results = []
        
        # 截取前 N 个代币进行分析
        target_tokens = token_list_raw[:max_items]
        
        for i, item in enumerate(target_tokens):
            # 不同的接口返回的 key 可能不同，这里做兼容处理
            # 假设返回里有 'symbol' 或者 'tokenSymbol'
            symbol = item.get("symbol") or item.get("baseAsset")
            
            if symbol:
                status_text.text(f"正在分析 ({i+1}/{len(target_tokens)}): {symbol} ...")
                
                # 获取 K 线
                kline_data = get_token_klines(symbol)
                
                if kline_data:
                    # 计算波动率
                    high = kline_data['high']
                    low = kline_data['low']
                    
                    volatility = 0
                    if low > 0:
                        volatility = ((high - low) / low) * 100
                    
                    results.append({
                        "代币": symbol,
                        "现价": kline_data['close'],
                        "24h最高": high,
                        "24h最低": low,
                        "波动率(%)": volatility,
                        # 保留原始信息以便查看
                        "全名": item.get("tokenName", symbol)
                    })
                
                # 关键：防封号，每请求一次休息一下
                time.sleep(random.uniform(0.1, 0.5))
            
            # 更新进度条
            progress_bar.progress((i + 1) / len(target_tokens))
            
        status_text.text("✅ 分析完成！")
        
        if results:
            df = pd.DataFrame(results)
            
            # 排序：默认按波动率从小到大
            df = df.sort_values("波动率(%)", ascending=True)
            
            # 展示
            st.subheader("📊 Alpha 代币稳定性排行榜")
            
            st.dataframe(
                df.style.format({
                    "现价": "{:.6f}",
                    "24h最高": "{:.6f}",
                    "24h最低": "{:.6f}",
                    "波动率(%)": "{:.2f}%"
                }).background_gradient(subset=['波动率(%)'], cmap='RdYlGn_r'),
                use_container_width=True,
                height=700
            )
        else:
            st.warning("虽然获取了名单，但无法获取 K 线数据。可能原因：接口参数校验严格或 IP 被限制。")
            
    else:
        st.error("获取代币名单失败。如果是在 Streamlit Cloud 运行，可能是 IP 被墙。请尝试在本地运行。")

else:
    st.info("点击上方按钮开始抓取数据。")


