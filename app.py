import streamlit as st
import pandas as pd
import requests
import time
import random

st.set_page_config(page_title="币安 Alpha 深度监控", layout="wide")
st.title("🦄 币安 Alpha 监控 (Debug 修复版)")

# --- 核心配置 ---
# 必须伪装，否则 403
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.binance.com/en/web3/wallet/alpha",
    "Origin": "https://www.binance.com",
    "Content-Type": "application/json",
    "client-type": "web"
}

# --- 1. 获取名单 ---
@st.cache_data(ttl=300)
def get_alpha_list():
    url = "https://www.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/cex/alpha/all/token/list"
    try:
        # 尝试 POST 
        resp = requests.post(url, headers=HEADERS, json={}, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("data", [])
    except Exception as e:
        st.error(f"名单获取出错: {e}")
    return []

# --- 2. 获取 K 线 (修复核心) ---
def get_kline_debug(symbol_raw):
    url = "https://www.binance.com/bapi/defi/v1/public/alpha-trade/klines"
    
    # 修复逻辑 A: 确保是交易对格式 (TIMI -> TIMIUSDT)
    symbol_pair = f"{symbol_raw}USDT".upper()
    
    # 修复逻辑 B: 尝试更完整的参数组合
    params = {
        "symbol": symbol_pair,
        "interval": "1d",     # 日线
        "limit": "1",         # 只要1根
        "marketType": "SPOT"  # 关键：显式告诉接口是现货
    }
    
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=5)
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success"):
                kline = data["data"][0]
                # 数据通常是 [time, open, high, low, close, vol...]
                return {
                    "pair": symbol_pair,
                    "high": float(kline[2]),
                    "low": float(kline[3]),
                    "close": float(kline[4]),
                    "success": True
                }
            else:
                # 失败时返回具体的错误信息
                return {"success": False, "msg": f"API拒绝: {data}"}
        else:
            return {"success": False, "msg": f"HTTP状态: {resp.status_code}"}
            
    except Exception as e:
        return {"success": False, "msg": f"报错: {str(e)}"}

# --- 3. 主程序 ---
if st.button("🚀 开始诊断与分析"):
    st.info("正在获取 Alpha 名单...")
    token_list = get_alpha_list()
    
    if token_list:
        st.success(f"✅ 名单获取成功！共找到 {len(token_list)} 个代币。开始尝试获取 K 线...")
        
        # 仅测试前 5 个，方便快速看到错误原因
        test_batch = token_list[:10] 
        results = []
        errors = []
        
        progress = st.progress(0)
        status_box = st.empty()
        
        for i, item in enumerate(test_batch):
            # 提取 symbol
            symbol = item.get("symbol") or item.get("baseAsset")
            
            status_box.text(f"正在请求: {symbol}USDT ...")
            
            # 请求数据
            k_data = get_kline_debug(symbol)
            
            if k_data["success"]:
                # 计算波动率
                high, low = k_data['high'], k_data['low']
                vol = ((high - low) / low * 100) if low > 0 else 0
                
                results.append({
                    "代币": symbol,
                    "现价": k_data['close'],
                    "波动率(%)": vol,
                    "Debug": "成功"
                })
            else:
                errors.append(f"{symbol}: {k_data['msg']}")
            
            time.sleep(0.3) # 防封
            progress.progress((i+1)/len(test_batch))
            
        status_box.empty()
        
        # 展示成功的数据
        if results:
            st.subheader("📊 成功获取的数据")
            df = pd.DataFrame(results)
            st.dataframe(df.style.format({"现价": "{:.4f}", "波动率(%)": "{:.2f}%"}), use_container_width=True)
        
        # ⚠️ 关键：展示失败原因，方便你告诉我
        if errors:
            st.subheader("❌ 失败诊断日志 (请截图这一部分)")
            st.warning("部分 K 线获取失败，原因如下：")
            st.json(errors)
            
            st.markdown("---")
            st.info("💡 如果错误提示是 'IllegalParameter'，说明该币种可能没有 USDT 交易对，或者接口参数还需要调整。")
            
    else:
        st.error("无法获取名单。")


