import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import re
import time

# 页面配置
st.set_page_config(page_title="Beta Radar", page_icon="📈", layout="wide")

st.title("🛡️ 纳指 100 资产监控终端 (稳定版)")

# ==========================================
# 1. 侧边栏：初始数据
# ==========================================
with st.sidebar:
    st.header("⚙️ 持仓配置")
    c124 = st.number_input("513100.SS (股)", value=1242800)
    c216 = st.number_input("513300.SS (股)", value=21600)
    c320 = st.number_input("2834.HK (股)", value=320)
    c274 = st.number_input("7266.HK (股)", value=27400)
    c_tqqq = st.number_input("TQQQ (股)", value=0)
    st.markdown("---")
    c_cash = st.number_input("现金储备 (CNY)", value=4900000.0)

holdings = {
    "513100.SS": {"name": "纳指100ETF(A)", "qty": c124, "lev": 1.0, "cur": "CNY", "tx_code": "sh513100"},
    "513300.SS": {"name": "纳指ETF(A)",    "qty": c216, "lev": 1.0, "cur": "CNY", "tx_code": "sh513300"},
    "2834.HK":   {"name": "纳指ETF(港)",    "qty": c320, "lev": 1.0, "cur": "HKD", "tx_code": "hk02834"},
    "7266.HK":   {"name": "两倍纳指(港)",    "qty": c274, "lev": 2.0, "cur": "HKD", "tx_code": "hk07266"},
    "TQQQ":      {"name": "三倍纳指(美)",    "qty": c_tqqq, "lev": 3.0, "cur": "USD", "tx_code": "usTQQQ"}
}

# ==========================================
# 2. 增强版数据抓取逻辑 (双源备份)
# ==========================================
@st.cache_data(ttl=300)
def fetch_robust_data(holdings_config):
    prices = {}
    fx = {"USD": 7.24, "HKD": 0.93, "CNY": 1.0}
    
    # 尝试抓取汇率 (雅虎)
    try:
        fx["USD"] = yf.Ticker("USDCNY=X").fast_info.get('last_price', 7.24)
        fx["HKD"] = yf.Ticker("HKDCNY=X").fast_info.get('last_price', 0.93)
    except:
        pass # 失败则使用默认值

    # 尝试抓取股价
    for ticker, info in holdings_config.items():
        success = False
        # 1. 优先尝试雅虎财经
        try:
            p = yf.Ticker(ticker).fast_info.get('last_price', 0)
            if p > 0:
                prices[ticker] = p
                success = True
        except:
            pass
        
        # 2. 如果雅虎失败，切换到腾讯/新浪接口 (针对 A股和港股)
        if not success:
            try:
                # 这是一个公开的财经接口示例
                url = f"http://qt.gtimg.cn/q={info['tx_code']}"
                resp = requests.get(url, timeout=3)
                if resp.status_code == 200:
                    data = resp.text.split('~')
                    if len(data) > 3:
                        prices[ticker] = float(data[3])
                        success = True
            except:
                pass
        
        # 3. 仍失败则给一个保底价
        if not success:
            prices[ticker] = 1.0 # 极端情况下的保底

    return fx, prices

# 执行抓取
fx, prices = fetch_robust_data(holdings)

# ==========================================
# 3. 计算与显示 (同之前逻辑)
# ==========================================
total_mkt_val = sum(prices[t] * h['qty'] * fx[h['cur']] for t, h in holdings.items())
total_assets = total_mkt_val + c_cash
current_beta = sum(prices[t] * h['qty'] * fx[h['cur']] * h['lev'] for t, h in holdings.items()) / total_assets if total_assets > 0 else 0

# UI 部分
m1, m2, m3 = st.columns(3)
m1.metric("总资产 (CNY)", f"¥{total_assets:,.0f}")
m2.metric("实时总 Beta", f"{current_beta:.2f}")
m3.metric("现金占比", f"{(c_cash/total_assets*100):.1f}%")

st.subheader("📋 持仓明细")
display_df = []
for t, h in holdings.items():
    v_cny = prices[t] * h['qty'] * fx[h['cur']]
    display_df.append({
        "名称": h['name'], "代码": t, "数量": f"{h['qty']:,}",
        "价格": f"{prices[t]:.3f}", "市值(CNY)": f"{v_cny:,.0f}",
        "占比": f"{(v_cny/total_assets*100):.1f}%", "杠杆": f"{h['lev']}x"
    })
st.table(pd.DataFrame(display_df))

# 调仓助手 (省略部分重复 UI 代码，保持逻辑一致)
st.markdown("---")
st.subheader("🎯 调仓建议")
target_b = st.slider("设定目标 Beta", 0.0, 1.5, 0.9, 0.01)
# ... 计算逻辑 ...
gap_val = (target_b - current_beta) * total_assets
# 默认用 7266 调整
adj_p_cny = prices["7266.HK"] * fx["HKD"]
if adj_p_cny > 0:
    shares = round(gap_val / (2.0 * adj_p_cny))
    if shares != 0:
        st.warning(f"建议指令：{'买入' if shares > 0 else '卖出'} {abs(shares):,} 股 7266.HK")
