import streamlit as st
import pandas as pd
import requests
import time

# --- 1. 页面配置 ---
st.set_page_config(
    page_title="Binance Alpha Volume Monitor",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义 CSS 让表格更像 alpha-volume 网站的风格
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: white; }
    div[data-testid="stMetricValue"] { font-size: 1.2rem; }
</style>
""", unsafe_allow_html=True)

st.title("⚡ Binance Alpha Volume Monitor")
st.caption("基于 Binance Alpha 名单 + 实时现货聚合数据")

# --- 2. 核心函数 ---

# (A) 获取 Alpha 名单 (使用 BAPI)
@st.cache_data(ttl=300)
def get_alpha_list():
    url = "https://www.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/cex/alpha/all/token/list"
    headers = {
        "User-Agent": "Mozilla/5.0", 
        "client-type": "web"
    }
    try:
        # 尝试 POST (有些地区 POST 成功率高)
        resp = requests.post(url, headers=headers, json={}, timeout=5)
        if resp.status_code != 200:
             # 如果失败尝试 GET
            resp = requests.get(url, headers=headers, timeout=5)
            
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success"):
                # 提取 symbol 列表
                raw_list = data.get("data", [])
                # 我们只需要 symbol 字段，清洗一下
                symbols = set()
                for item in raw_list:
                    # 兼容不同字段名
                    s = item.get("symbol") or item.get("baseAsset") or item.get("tokenSymbol")
                    if s:
                        symbols.add(s.upper())
                return list(symbols)
    except Exception as e:
        st.error(f"名单获取失败: {e}")
    return []

# (B) 获取全市场行情 (使用公共 API - 稳定！)
@st.cache_data(ttl=10) # 10秒刷新一次价格
def get_market_ticker():
    # 使用公共接口一次性拉取所有币种，效率最高
    url = "https://api.binance.com/api/v3/ticker/24hr"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return pd.DataFrame(resp.json())
    except:
        # 备用节点
        try:
            resp = requests.get("https://api.binance.us/api/v3/ticker/24hr", timeout=5)
            if resp.status_code == 200:
                return pd.DataFrame(resp.json())
        except:
            pass
    return pd.DataFrame()

# --- 3. 主逻辑 ---

# 侧边栏
st.sidebar.header("⚙️ 筛选配置")
min_vol = st.sidebar.number_input("最小成交额 (百万 USDT)", value=1.0, step=0.5)
search_txt = st.sidebar.text_input("🔍 搜索币种", "").upper()

if st.button("🚀 刷新数据", type="primary"):
    with st.spinner("正在同步 Alpha 名单与市场数据..."):
        
        # 1. 获取名单
        alpha_symbols = get_alpha_list()
        
        if not alpha_symbols:
            st.error("⚠️ 无法获取 Alpha 名单，请检查网络或稍后再试。")
        else:
            # 2. 获取行情
            df_market = get_market_ticker()
            
            if df_market.empty:
                st.error("⚠️ 无法获取市场行情。")
            else:
                # --- 数据融合 ---
                
                # 构造需要匹配的 symbol (例如: 名单里是 TIMI -> 匹配 TIMIUSDT)
                # 并在 df_market 中筛选
                
                # 预处理行情数据
                df_market = df_market[df_market['symbol'].str.endswith('USDT')]
                
                # 核心匹配逻辑：
                # 只要 ticker 的 symbol 包含了 alpha 名单里的名字，就保留
                # (这种方式比精准匹配更安全，防止漏掉 1000SATS 这种带前缀的)
                
                # 为了速度，我们先把 market 里的 symbol 变成 "Base Asset"
                # 例如 BTCUSDT -> BTC
                df_market['base_asset'] = df_market['symbol'].str.replace('USDT', '')
                
                # 筛选：保留 base_asset 在 alpha_symbols 里的行
                df_final = df_market[df_market['base_asset'].isin(alpha_symbols)].copy()
                
                # --- 4. 数据计算与美化 ---
                if not df_final.empty:
                    # 类型转换
                    cols = ['lastPrice', 'priceChangePercent', 'quoteVolume', 'highPrice', 'lowPrice']
                    for c in cols:
                        df_final[c] = pd.to_numeric(df_final[c])
                    
                    # 计算指标
                    df_final['成交额(M)'] = df_final['quoteVolume'] / 1_000_000
                    
                    # 波动率 (High - Low) / Low
                    df_final['波动率(%)'] = ((df_final['highPrice'] - df_final['lowPrice']) / df_final['lowPrice']) * 100
                    
                    # 生成交易链接
                    def make_link(symbol):
                        return f"https://www.binance.com/zh-CN/trade/{symbol}?type=spot"
                    
                    df_final['交易链接'] = df_final['symbol'].apply(make_link)

                    # --- 筛选 ---
                    # 1. 成交额过滤
                    df_final = df_final[df_final['成交额(M)'] >= min_vol]
                    
                    # 2. 搜索过滤
                    if search_txt:
                        df_final = df_final[df_final['symbol'].str.contains(search_txt)]
                    
                    # 排序 (默认按波动率倒序，模仿 alpha-volume 寻找异动)
                    df_final = df_final.sort_values("波动率(%)", ascending=False)
                    
                    # 重置索引，让排名从1开始
                    df_final = df_final.reset_index(drop=True)
                    df_final.index += 1
                    
                    # 整理展示列
                    show_cols = ['symbol', 'lastPrice', 'priceChangePercent', '波动率(%)', '成交额(M)', '交易链接']
                    df_show = df_final[show_cols]
                    
                    # 修改列名
                    df_show.columns = ['币种', '现价', '24h涨跌(%)', '波动率(%)', '成交额(M)', '链接']

                    st.success(f"✅ 成功聚合 {len(df_show)} 个 Alpha 代币数据")
                    
                    # --- 展示表格 ---
                    st.data_editor(
                        df_show,
                        column_config={
                            "链接": st.column_config.LinkColumn(
                                "前往交易", 
                                help="点击跳转到币安现货交易",
                                display_text="Trade ↗️"
                            ),
                            "24h涨跌(%)": st.column_config.NumberColumn(
                                "24h 涨跌",
                                format="%.2f%%",
                            ),
                            "波动率(%)": st.column_config.ProgressColumn(
                                "24h 波动率",
                                format="%.2f%%",
                                min_value=0,
                                max_value=max(df_show['波动率(%)'].max(), 20), # 动态最大值
                            ),
                            "成交额(M)": st.column_config.NumberColumn(
                                "成交额 (M)",
                                format="$ %.2f M",
                            ),
                             "现价": st.column_config.NumberColumn(
                                "现价",
                                format="%.4f",
                            )
                        },
                        hide_index=False,
                        use_container_width=True,
                        height=800
                    )
                    
                else:
                    st.warning("名单匹配完成，但没有找到对应的 USDT 现货交易对。")
                    st.write("Alpha 名单样本:", alpha_symbols[:5])

# 首次加载提示
else:
    st.info("👋 点击左侧的 **'🚀 刷新数据'** 按钮开始监控。")
    st.markdown("### 🛠️ 工作原理")
    st.markdown("""
    1. **获取名单**: 从币安 Web3 Alpha 接口 (`.../token/list`) 获取最新推荐列表。
    2. **获取行情**: 从币安现货接口 (`/api/v3/ticker/24hr`) 获取全量数据。
    3. **交叉匹配**: 筛选出名单中正在交易的 USDT 币种。
    4. **计算指标**: 算出波动率与成交额，并生成交易链接。
    """)


