import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import time

# 1. 页面配置
st.set_page_config(page_title="Beta Radar Pro", page_icon="📈", layout="wide")

# ==========================================
# 2. 会话状态初始化 (确保手动输入不被重置)
# ==========================================
if 'init_data' not in st.session_state:
    st.session_state.init_data = {
        "c124": 1242800,
        "c216": 21600,
        "c320": 320,
        "c274": 27400,
        "c_tqqq": 0,
        "c_cash": 4900000.0
    }

# ==========================================
# 3. 侧边栏：数据录入 (联动 Session State)
# ==========================================
with st.sidebar:
    st.header("⚙️ 持仓配置")
    # 使用 session_state 作为默认值，并更新回 session_state
    st.session_state.init_data["c124"] = st.number_input("513100.SS 数量", value=st.session_state.init_data["c124"])
    st.session_state.init_data["c216"] = st.number_input("513300.SS 数量", value=st.session_state.init_data["c216"])
    st.session_state.init_data["c320"] = st.number_input("2834.HK 数量", value=st.session_state.init_data["c320"])
    st.session_state.init_data["c274"] = st.number_input("7266.HK 数量", value=st.session_state.init_data["c274"])
    st.session_state.init_data["c_tqqq"] = st.number_input("TQQQ 数量", value=st.session_state.init_data["c_tqqq"])
    st.markdown("---")
    st.session_state.init_data["c_cash"] = st.number_input("现金储备 (CNY)", value=st.session_state.init_data["c_cash"], step=10000.0)
    
    if st.button("🔄 重置为默认模板"):
        st.session_state.clear()
        st.rerun()

# 定义配置
holdings_config = {
    "513100.SS": {"name": "纳指100ETF(A)", "qty": st.session_state.init_data["c124"], "lev": 1.0, "cur": "CNY", "tx_code": "sh513100"},
    "513300.SS": {"name": "纳指ETF(A)",    "qty": st.session_state.init_data["c216"], "lev": 1.0, "cur": "CNY", "tx_code": "sh513300"},
    "2834.HK":   {"name": "纳指ETF(港)",    "qty": st.session_state.init_data["c320"], "lev": 1.0, "cur": "HKD", "tx_code": "hk02834"},
    "7266.HK":   {"name": "两倍纳指(港)",    "qty": st.session_state.init_data["c274"], "lev": 2.0, "cur": "HKD", "tx_code": "hk07266"},
    "TQQQ":      {"name": "三倍纳指(美)",    "qty": st.session_state.init_data["c_tqqq"], "lev": 3.0, "cur": "USD", "tx_code": "usTQQQ"}
}

# ==========================================
# 4. 数据抓取 (汇率聚合逻辑)
# ==========================================
@st.cache_data(ttl=300)
def get_market_data(config):
    fx = {"USD": 7.24, "HKD": 0.925, "CNY": 1.0}
    prices = {}
    
    # 汇率多源验证
    try:
        # 1. 尝试从腾讯接口获取实时汇率 (通常对国内用户更准)
        resp_usd = requests.get("http://qt.gtimg.cn/q=usdcny", timeout=2)
        if "USDCNY" in resp_usd.text:
            fx["USD"] = float(resp_usd.text.split('~')[3])
        
        resp_hkd = requests.get("http://qt.gtimg.cn/q=hkdcny", timeout=2)
        if "HKDCNY" in resp_hkd.text:
            fx["HKD"] = float(resp_hkd.text.split('~')[3])
            
        # 2. 如果腾讯没拿到，尝试 yfinance 补位
        if fx["USD"] == 7.24:
            fx["USD"] = yf.Ticker("USDCNY=X").fast_info.get('last_price', 7.24)
    except:
        pass

    # 股价抓取
    for ticker, info in config.items():
        success = False
        try:
            # 优先尝试 yf
            p = yf.Ticker(ticker).fast_info.get('last_price', 0)
            if p > 0: 
                prices[ticker] = p
                success = True
        except: pass
        
        if not success:
            try:
                resp = requests.get(f"http://qt.gtimg.cn/q={info['tx_code']}", timeout=2)
                data = resp.text.split('~')
                if len(data) > 3:
                    prices[ticker] = float(data[3])
                    success = True
            except: pass
        
        if not success: prices[ticker] = 1.0
        
    return fx, prices

fx, prices = get_market_data(holdings_config)

# ==========================================
# 5. 计算逻辑
# ==========================================
total_mkt_val = sum(prices[t] * h['qty'] * fx[h['cur']] for t, h in holdings_config.items())
total_assets = total_mkt_val + st.session_state.init_data["c_cash"]
current_beta = sum(prices[t] * h['qty'] * fx[h['cur']] * h['lev'] for t, h in holdings_config.items()) / total_assets if total_assets > 0 else 0

# ==========================================
# 6. UI 展现
# ==========================================
st.title("🛡️ 纳指平衡监控终端")

# 汇率条
st.success(f"💹 **实时汇率**: 1 USD = {fx['USD']:.4f} CNY | 1 HKD = {fx['HKD']:.4f} CNY")

m1, m2, m3 = st.columns(3)
m1.metric("总资产 (CNY)", f"¥{total_assets:,.2f}")
m2.metric("当前实时 Beta", f"{current_beta:.3f}")
m3.metric("现金占比", f"{(st.session_state.init_data['c_cash']/total_assets*100):.2f}%")

st.subheader("📋 持仓资产详情")
df_data = []
for t, h in holdings_config.items():
    v_cny = prices[t] * h['qty'] * fx[h['cur']]
    df_data.append({
        "标的": h['name'], "代码": t, "持仓": f"{h['qty']:,}",
        "单价": f"{prices[t]:.3f}", "价值(CNY)": f"{v_cny:,.0f}",
        "权重": f"{(v_cny/total_assets*100):.2f}%", "杠杆": f"{h['lev']}x"
    })
st.table(pd.DataFrame(df_data))

# 调仓助手
st.markdown("---")
st.subheader("🎯 调仓计算器")
c1, c2 = st.columns(2)
with c1:
    target_b = st.slider("目标 Beta", 0.0, 1.5, 0.9, 0.01)
with c2:
    adj_name = st.selectbox("调仓标的", [h['name'] for h in holdings_config.values()], index=3)

adj_ticker = next(k for k, v in holdings_config.items() if v['name'] == adj_name)
t_h = holdings_config[adj_ticker]
t_p_cny = prices[adj_ticker] * fx[t_h['cur']]

if t_p_cny > 0:
    gap = (target_b - current_beta) * total_assets
    shares = round(gap / (t_h['lev'] * t_p_cny))
    cost_orig = abs(shares * prices[adj_ticker])
    
    if shares != 0:
        st.warning(f"### 指令: {'买入' if shares > 0 else '卖出'} {abs(shares):,} 股 {t_h['name']}")
        st.write(f"预计成交: **{cost_orig:,.2f} {t_h['cur']}** (约 {abs(shares)*t_p_cny:,.0f} CNY)")
