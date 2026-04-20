import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import time

# 1. 页面配置
st.set_page_config(page_title="Beta Radar Pro", page_icon="📈", layout="wide")

# ==========================================
# 2. 持仓数据持久化逻辑 (核心改善：记住手动输入)
# ==========================================
# 定义初始默认值
default_values = {
    "c124": 1242800,
    "c216": 21600,
    "c320": 320,
    "c274": 27400,
    "c_tqqq": 0,
    "c_cash": 4900000.0
}

# 如果是第一次运行，或者手动点击了重置，初始化 session_state
if '持仓' not in st.session_state:
    st.session_state['持仓'] = default_values.copy()

# ==========================================
# 3. 侧边栏：交互输入
# ==========================================
with st.sidebar:
    st.header("⚙️ 持仓配置")
    st.markdown("在此处修改的数量将自动保存为计算基准")
    
    # 将输入框直接绑定到 session_state
    st.session_state['持仓']["c124"] = st.number_input("513100.SS 数量", value=st.session_state['持仓']["c124"])
    st.session_state['持仓']["c216"] = st.number_input("513300.SS 数量", value=st.session_state['持仓']["c216"])
    st.session_state['持仓']["c320"] = st.number_input("2834.HK 数量", value=st.session_state['持仓']["c320"])
    st.session_state['持仓']["c274"] = st.number_input("7266.HK 数量", value=st.session_state['持仓']["c274"])
    st.session_state['持仓']["c_tqqq"] = st.number_input("TQQQ 数量", value=st.session_state['持仓']["c_tqqq"])
    st.markdown("---")
    st.session_state['持仓']["c_cash"] = st.number_input("现金储备 (CNY)", value=st.session_state['持仓']["c_cash"], step=10000.0)
    
    if st.button("🔄 恢复最初默认值"):
        st.session_state['持仓'] = default_values.copy()
        st.rerun()

# 根据保存的数据构建配置
holdings_config = {
    "513100.SS": {"name": "纳指100ETF(A)", "qty": st.session_state['持仓']["c124"], "lev": 1.0, "cur": "CNY", "tx_code": "sh513100"},
    "513300.SS": {"name": "纳指ETF(A)",    "qty": st.session_state['持仓']["c216"], "lev": 1.0, "cur": "CNY", "tx_code": "sh513300"},
    "2834.HK":   {"name": "纳指ETF(港)",    "qty": st.session_state['持仓']["c320"], "lev": 1.0, "cur": "HKD", "tx_code": "hk02834"},
    "7266.HK":   {"name": "两倍纳指(港)",    "qty": st.session_state['持仓']["c274"], "lev": 2.0, "cur": "HKD", "tx_code": "hk07266"},
    "TQQQ":      {"name": "三倍纳指(美)",    "qty": st.session_state['持仓']["c_tqqq"], "lev": 3.0, "cur": "USD", "tx_code": "usTQQQ"}
}

# ==========================================
# 4. 数据抓取 (核心改善：实时腾讯汇率接口)
# ==========================================
@st.cache_data(ttl=300) # 每5分钟更新一次行情
def get_live_market_data(config):
    # 默认值
    fx = {"USD": 7.24, "HKD": 0.925, "CNY": 1.0}
    prices = {}
    
    # 尝试抓取更准确的国内财经汇率接口
    try:
        # 腾讯财经实时汇率
        r_usd = requests.get("http://qt.gtimg.cn/q=usdcny", timeout=2)
        if r_usd.status_code == 200:
            fx["USD"] = float(r_usd.text.split('~')[3])
            
        r_hkd = requests.get("http://qt.gtimg.cn/q=hkdcny", timeout=2)
        if r_hkd.status_code == 200:
            fx["HKD"] = float(r_hkd.text.split('~')[3])
    except:
        pass # 备用雅虎接口在下方循环中处理

    for ticker, info in config.items():
        success = False
        # 国内标的优先使用腾讯接口，更准更快
        if "SS" in ticker or "HK" in ticker:
            try:
                resp = requests.get(f"http://qt.gtimg.cn/q={info['tx_code']}", timeout=2)
                data = resp.text.split('~')
                if len(data) > 3:
                    prices[ticker] = float(data[3])
                    success = True
            except: pass
        
        # 美股或国内接口失败时尝试雅虎
        if not success:
            try:
                p = yf.Ticker(ticker).fast_info.get('last_price', 0)
                if p > 0:
                    prices[ticker] = p
                    success = True
            except: pass
            
        if not success: prices[ticker] = 1.0 # 极端保底
        
    return fx, prices

fx, prices = get_live_market_data(holdings_config)

# ==========================================
# 5. 计算与显示
# ==========================================
total_mkt_val = sum(prices[t] * h['qty'] * fx[h['cur']] for t, h in holdings_config.items())
total_assets = total_mkt_val + st.session_state['持仓']["c_cash"]
current_beta = sum(prices[t] * h['qty'] * fx[h['cur']] * h['lev'] for t, h in holdings_config.items()) / total_assets if total_assets > 0 else 0

st.title("🛡️ 纳指平衡监控终端")
st.info(f"💹 **实时汇率参考**: 1 USD = {fx['USD']:.4f} CNY | 1 HKD = {fx['HKD']:.4f} CNY (已更新)")

m1, m2, m3 = st.columns(3)
m1.metric("总资产值 (CNY)", f"¥{total_assets:,.2f}")
m2.metric("实时总 Beta", f"{current_beta:.3f}")
m3.metric("现金占比", f"{(st.session_state['持仓']['c_cash']/total_assets*100):.2f}%")

st.subheader("📋 实时持仓明细")
df_data = []
for t, h in holdings_config.items():
    v_cny = prices[t] * h['qty'] * fx[h['cur']]
    df_data.append({
        "标的": h['name'], "代码": t, "持仓": f"{h['qty']:,}",
        "价格": f"{prices[t]:.3f}", "价值(CNY)": f"{v_cny:,.0f}",
        "权重": f"{(v_cny/total_assets*100):.2f}%", "杠杆": f"{h['lev']}x"
    })
st.table(pd.DataFrame(df_data))

# ==========================================
# 6. 调仓交互 (修复：增加标的选择)
# ==========================================
st.markdown("---")
st.subheader("🎯 调仓助手")
c1, c2 = st.columns(2)
with c1:
    target_b = st.slider("设定目标 Beta 值", 0.0, 1.5, 0.9, 0.01)
with c2:
    # 自动识别代码前缀，方便选择
    choice_map = {h['name']: t for t, h in holdings_config.items()}
    selected_name = st.selectbox("选择调整标的", list(choice_map.keys()), index=3) # 默认选7266
    adj_ticker = choice_map[selected_name]

t_info = holdings_config[adj_ticker]
t_p_cny = prices[adj_ticker] * fx[t_info['cur']]

if t_p_cny > 0:
    gap = (target_b - current_beta) * total_assets
    shares = round(gap / (t_info['lev'] * t_p_cny))
    cost_orig = abs(shares * prices[adj_ticker])
    
    if shares != 0:
        st.warning(f"### 指令: {'买入' if shares > 0 else '卖出'} {abs(shares):,} 股 {t_info['name']}")
        st.write(f"成交币种金额: **{cost_orig:,.2f} {t_info['cur']}** (约 {abs(shares)*t_p_cny:,.2f} CNY)")
    else:
        st.success("✅ 当前 Beta 已符合目标。")

st.caption(f"行情更新于: {time.strftime('%H:%M:%S')} | 数据源: QQ/Yahoo Finance")
