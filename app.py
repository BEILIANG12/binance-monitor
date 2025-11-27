import streamlit as st
import pandas as pd
import requests
import random

# --- 1. 页面配置 ---
st.set_page_config(page_title="币安内部 Alpha 接口监控", layout="wide")
st.title("🏴‍☠️ 币安 Alpha 内部数据监控 (BAPI版)")
st.warning("⚠️ 注意：此模式使用币安官网内部接口 (BAPI)。如果数据为空，说明云服务器 IP 被币安防火墙拦截，请尝试在本地电脑运行。")

# --- 2. 侧边栏 ---
st.sidebar.header("Alpha 搜索")
target_input = st.sidebar.text_input("输入币种名称 (例如 TIMI, MERL, NOT)", "BTC")
target_coin = target_input.strip().upper()

# --- 3. 核心：调用币安内部 API (BAPI) ---
@st.cache_data(ttl=60)
def get_bapi_data():
    # 这是币安官网前端真正使用的接口，包含所有标签和未完全开放的币种
    url = "https://www.binance.com/bapi/asset/v2/public/asset-service/product/get-products"
    
    # 必须伪装成浏览器，否则会被拦截
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.binance.com/zh-CN/markets/overview",
        "Content-Type": "application/json",
        "client-type": "web"
    }
    
    params = {
        "includeEtf": "true"
    }

    try:
        # 尝试连接
        print(f"正在连接内部接口: {url}")
        resp = requests.get(url, headers=headers, params=params, timeout=5)
        
        if resp.status_code == 200:
            data = resp.json()
            if data['success']:
                return data['data'] # 返回核心数据列表
            else:
                st.error(f"API 返回错误: {data}")
        else:
            st.error(f"HTTP 错误: {resp.status_code} - 可能被防火墙拦截")
            
    except Exception as e:
        st.error(f"连接失败: {e}")
    
    return []

# --- 4. 数据处理与展示 ---
raw_data = get_bapi_data()

if raw_data:
    # BAPI 返回的数据结构很紧凑，我们需要手动映射
    # s: symbol (交易对)
    # c: close price (现价)
    # q: quote asset (计价货币，如 USDT)
    # tags: 标签 (Seed, Monitoring 等)
    
    df = pd.DataFrame(raw_data)
    
    # 1. 筛选：只看 USDT 交易对
    df = df[df['q'] == 'USDT']
    
    # 2. 转换字段名以便阅读
    df = df.rename(columns={
        's': '交易对', 
        'c': '现价', 
        'h': '最高价', 
        'l': '最低价', 
        'v': '成交量', 
        'qv': '成交额',
        'tags': '标签'
    })
    
    # 3. 数值转换
    numeric_cols = ['现价', '最高价', '最低价', '成交额']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col])

    # 4. 计算波动率
    df = df[df['最低价'] > 0]
    df['波动率(%)'] = ((df['最高价'] - df['最低价']) / df['最低价']) * 100
    df['成交额(M)'] = df['成交额'] / 1000000

    # --- 搜索逻辑 ---
    # 支持模糊搜索，只要交易对里包含用户输入的字
    result = df[df['交易对'].str.contains(target_coin)]
    
    if not result.empty:
        st.success(f"✅ 在币安内部库中找到 {len(result)} 个相关结果：")
        
        # 提取标签信息 (List 转 String)
        result['标签'] = result['标签'].apply(lambda x: ', '.join(x) if isinstance(x, list) else str(x))
        
        # 展示表格
        st.dataframe(
            result[['交易对', '现价', '波动率(%)', '标签', '成交额(M)']].style.format({
                "现价": "{:.6f}",
                "波动率(%)": "{:.2f}%",
                "成交额(M)": "{:.2f} M"
            }).background_gradient(subset=['波动率(%)'], cmap='RdYlGn_r'),
            use_container_width=True
        )
        
        # 额外：显示 Alpha 属性提示
        st.info("💡 解读：\n- **Seed / Innovation**: 种子/创新区，高风险 Alpha 代币。\n- **Monitoring**: 观察标签，波动极大。\n- 如果这里还找不到，说明该币种连币安内部数据库都未录入（纯链上项目）。")
        
    else:
        st.error(f"❌ 在币安内部接口也未找到 '{target_coin}'。")
        st.markdown(f"**可能性分析：**\n1. 您输入的币种 ({target_coin}) 尚未上线币安现货，属于 **Web3 钱包** 项目。\n2. 币安 Web3 钱包的数据与交易所是隔离的，无法通过此 API 获取。")
        
else:
    st.info("⏳ 正在尝试连接币安内部网络...")

