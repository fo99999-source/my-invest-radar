import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import time

# 1. 页面配置
st.set_page_config(page_title="Beta Radar Pro", page_icon="📈", layout="wide")

# ==========================================
# 2. 数据持久化逻辑 (Session State)
# ==========================================
DEFAULT_CONFIG = {
    "c124": 1242800,
    "c216": 21600,
    "c320": 320,
    "c274": 27400,
    "c_tqqq": 0,
    "c_cash": 4900000.0,
    "fx_usd": 7.2400,
    "fx_hkd": 0.9250
}

if 'saved_data' not in st.session_state:
    st.session_state.saved_data = DEFAULT_CONFIG.copy()

# ==========================================
# 3. 侧边栏：输入与控制
# ==========================================
with st.sidebar:
    st.header("⚙️ 持仓与设置")
    
    input_c124 = st.number_input("513100.SS 数量", value=st.session_state.saved_data["c124"])
    input_c216 = st.number_input("513300.SS 数量", value=st.session_state.saved_data["c216"])
    input_c320 = st.number_input("2834.HK 数量", value=st.session_state.saved_data["c320"])
    input_c274 = st.number_input("7266.HK 数量", value=st.session_state.saved_data["c274"])
    input_c_tqqq = st.number_input("TQQQ 数量", value=st.session_state.saved_data["c_tqqq"])
    input_c_cash = st.number_input("现金储备 (CNY)", value=st.session_state.saved_data["c_cash"], step=10000.0)
    
    st.markdown("---")
    st.subheader("💱 汇率手动校准")
    st.caption("若发现抓取不准，请在此修改并保存")
    input_fx_usd = st.number_input("USD/CNY", value=st.session_state.saved_data["fx_usd"], format="%.4f")
    input_fx_hkd = st.number_input("HKD/CNY", value=st.session_state.saved_data["fx_hkd"], format="%.4f")

    # 保存按钮
    if st.button("💾 保存当前修改为默认", use_container_width=True, type="primary"):
        st.session_state.saved_data.update({
            "c124": input_c124, "c216": input_c216, "c320": input_c320,
            "c274": input_c274, "c_tqqq": input_c_tqqq, "c_cash": input_c_cash,
            "fx_usd": input_fx_usd, "fx_hkd": input_fx_hkd
        })
        st.success("配置已保存！")
        time.sleep(0.5)
        st.rerun()

    # 恢复按钮
    if st.button("🔄 恢复最初预设", use_container_width=True):
        st.session_state.saved_data = DEFAULT_CONFIG.copy()
        st.rerun()

# 当前生效配置
conf = st.session_state.saved_data

holdings_map = {
    "513100.SS": {"name": "纳指100ETF(A)", "qty": conf["c124"], "lev": 1.0, "cur": "CNY", "tx": "sh513100"},
    "513300.SS": {"name": "纳指ETF(A)",    "qty": conf["c216"], "lev": 1.0, "cur": "CNY", "tx": "sh513300"},
    "2834.HK":   {"name": "纳指ETF(港)",    "qty": conf["c320"], "lev": 1.0, "cur": "HKD", "tx": "hk02834"},
    "7266.HK":   {"name": "两倍纳指(港)",    "qty": conf["c274"], "lev": 2.0, "cur": "HKD", "tx": "hk07266"},
    "TQQQ":      {"name": "三倍纳指(美)",    "qty": conf["c_tqqq"], "lev": 3.0, "cur": "USD", "tx": "usTQQQ"}
}

# ==========================================
# 4. 价格抓取逻辑
# ==========================================
@st.cache_data(ttl=300)
def fetch_prices(config):
    prices = {}
    for ticker, info in config.items():
        p = 0.0
        try:
            resp = requests.get(f"http://qt.gtimg.cn/q={info['tx']}", timeout=1).text.split('~')
            if len(resp) > 3: p = float(resp[3])
        except: pass
        if p == 0:
            try: p = yf.Ticker(ticker).fast_info.get('last_price', 0.0)
            except: p = 1.0
        prices[ticker] = p
    return prices

live_prices = fetch_prices(holdings_map)
fx_final = {"USD": conf["fx_usd"], "HKD": conf["fx_hkd"], "CNY": 1.0}

# ==========================================
# 5. 计算与显示区
# ==========================================
total_mkt_val = sum(live_prices[t] * h['qty'] * fx_final[h['cur']] for t, h in holdings_map.items())
total_assets = total_mkt_val + conf["c_cash"]
curr_beta = sum(live_prices[t] * h['qty'] * fx_final[h['cur']] * h['lev'] for t, h in holdings_map.items()) / total_assets if total_assets > 0 else 0

st.title("🛡️ 纳指平衡监控终端")
st.success(f"💹 **当前计算汇率**: USD/CNY = **{fx_final['USD']:.4f}** | HKD/CNY = **{fx_final['HKD']:.4f}**")

m1, m2, m3 = st.columns(3)
m1.metric("总资产 (CNY)", f"¥{total_assets:,.2f}")
m2.metric("当前 Beta", f"{curr_beta:.3f}")
m3.metric("现金占比", f"{(conf['c_cash']/total_assets*100):.2f}%")

# 持仓表格
df_list = []
for t, h in holdings_map.items():
    v_cny = live_prices[t] * h['qty'] * fx_final[h['cur']]
    df_list.append({
        "名称": h['name'], "代码": t, "持仓": f"{h['qty']:,}",
        "单价": f"{live_prices[t]:.3f}", "市值(CNY)": f"{v_cny:,.0f}",
        "权重": f"{(v_cny/total_assets*100):.2f}%", "杠杆": f"{h['lev']}x"
    })
st.table(pd.DataFrame(df_list))

# ==========================================
# 6. 调仓模拟 (重点更新：增加人民币金额显示)
# ==========================================
st.markdown("---")
st.subheader("🎯 调仓助手")
t_col1, t_col2 = st.columns(2)
with t_col1:
    target_b = st.slider("设定理想 Beta 目标", 0.0, 1.5, 0.9, 0.01)
with t_col2:
    selected_adj = st.selectbox("选择调仓标的", [h['name'] for h in holdings_map.values()], index=3)

# 寻找标的数据
adj_t = next(k for k, v in holdings_map.items() if v['name'] == selected_adj)
h_info = holdings_map[adj_t]
price_native = live_prices[adj_t]
fx_rate = fx_final[h_info['cur']]
price_cny = price_native * fx_rate

if price_cny > 0:
    # 计算 Beta 缺口所需的金额 (CNY)
    gap_beta = target_b - curr_beta
    needed_cny = gap_beta * total_assets / h_info['lev']
    
    # 转换为股数
    shares = round(needed_cny / price_cny)
    
    # 计算对应的原币种金额和人民币金额
    actual_cost_native = abs(shares * price_native)
    actual_cost_cny = abs(shares * price_cny)
    
    if shares != 0:
        action = "买入" if shares > 0 else "卖出"
        color = "orange" if action == "买入" else "blue
