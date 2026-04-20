import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import time

# 1. 页面配置
st.set_page_config(page_title="Beta Radar Pro", page_icon="📈", layout="wide")

# ==========================================
# 2. 持仓数据初始化 (已根据要求更新)
# ==========================================
DEFAULT_CONFIG = {
    "c124": 1174300,  # 513100.SS
    "c216": 21600,    # 513300.SS
    "c320": 600,      # 2834.HK
    "c274": 39000,    # 7266.HK
    "c_tqqq": 0,      # TQQQ
    "c_cash": 4550000.0,
    "fx_usd": 7.24,   # 初始参考，运行后会抓取实时
    "fx_hkd": 0.925   # 初始参考，运行后会抓取实时
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
    st.caption("程序会自动抓取，若不准可在此修改并保存")
    input_fx_usd = st.number_input("USD/CNY", value=st.session_state.saved_data["fx_usd"], format="%.4f")
    input_fx_hkd = st.number_input("HKD/CNY", value=st.session_state.saved_data["fx_hkd"], format="%.4f")

    if st.button("💾 保存当前修改为默认", use_container_width=True, type="primary"):
        st.session_state.saved_data.update({
            "c124": input_c124, "c216": input_c216, "c320": input_c320,
            "c274": input_c274, "c_tqqq": input_c_tqqq, "c_cash": input_c_cash,
            "fx_usd": input_fx_usd, "fx_hkd": input_fx_hkd
        })
        st.success("配置已保存！")
        time.sleep(0.5)
        st.rerun()

    if st.button("🔄 恢复最初预设", use_container_width=True):
        st.session_state.saved_data = DEFAULT_CONFIG.copy()
        st.rerun()

# 获取当前配置
conf = st.session_state.saved_data
holdings_map = {
    "513100.SS": {"name": "纳指100ETF(A)", "qty": conf["c124"], "lev": 1.0, "cur": "CNY", "tx": "sh513100"},
    "513300.SS": {"name": "纳指ETF(A)",    "qty": conf["c216"], "lev": 1.0, "cur": "CNY", "tx": "sh513300"},
    "2834.HK":   {"name": "纳指ETF(港)",    "qty": conf["c320"], "lev": 1.0, "cur": "HKD", "tx": "hk02834"},
    "7266.HK":   {"name": "两倍纳指(港)",    "qty": conf["c274"], "lev": 2.0, "cur": "HKD", "tx": "hk07266"},
    "TQQQ":      {"name": "三倍纳指(美)",    "qty": conf["c_tqqq"], "lev": 3.0, "cur": "USD", "tx": "usTQQQ"}
}

# ==========================================
# 4. 实时数据抓取逻辑 (包含汇率实时化)
# ==========================================
@st.cache_data(ttl=300)
def fetch_live_market_data(config):
    prices = {}
    current_fx = {"USD": conf["fx_usd"], "HKD": conf["fx_hkd"]}
    
    # 1. 尝试抓取实时汇率
    try:
        r_usd = requests.get("http://qt.gtimg.cn/q=usdcny", timeout=2).text.split('~')
        if len(r_usd) > 3: current_fx["USD"] = float(r_usd[3])
        r_hkd = requests.get("http://qt.gtimg.cn/q=hkdcny", timeout=2).text.split('~')
        if len(r_hkd) > 3: current_fx["HKD"] = float(r_hkd[3])
    except:
        pass

    # 2. 抓取股票/ETF价格
    for ticker, info in config.items():
        p = 0.0
        try:
            resp = requests.get(f"http://qt.gtimg.cn/q={info['tx']}", timeout=2).text.split('~')
            if len(resp) > 3: p = float(resp[3])
        except: pass
        if p == 0:
            try: p = yf.Ticker(ticker).fast_info.get('last_price', 0.0)
            except: p = 1.0
        prices[ticker] = p
    return current_fx, prices

# 执行实时抓取
fetched_fx, live_prices = fetch_live_market_data(holdings_map)

# 最终汇率决策：如果用户在侧边栏手动改了汇率且保存了，就用用户的；否则用实时抓取的。
# 这里逻辑设定为：手动保存的值具有最高优先级
fx_final = {"USD": conf["fx_usd"], "HKD": conf["fx_hkd"], "CNY": 1.0}

# ==========================================
# 5. 计算显示区
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

# 持仓详情
df_list = []
for t, h in holdings_map.items():
    v_cny = live_prices[t] * h['qty'] * fx_final[h['cur']]
    df_list.append({
        "名称": h['name'], "代码": t, "持仓": f"{h['qty']:,}",
        "价格": f"{live_prices[t]:.3f}", "市值(CNY)": f"{v_cny:,.0f}",
        "占比": f"{(v_cny/total_assets*100):.2f}%", "杠杆": f"{h['lev']}x"
    })
st.table(pd.DataFrame(df_list))

# ==========================================
# 6. 调仓助手 (人民币金额高亮显示)
# ==========================================
st.markdown("---")
st.subheader("🎯 调仓助手")
t_col1, t_col2 = st.columns(2)
with t_col1:
    target_b = st.slider("设定理想 Beta 目标", 0.0, 1.5, 0.9, 0.01)
with t_col2:
    selected_adj = st.selectbox("选择调仓标的", [h['name'] for h in holdings_map.values()], index=3)

adj_t = next(k for k, v in holdings_map.items() if v['name'] == selected_adj)
h_info = holdings_map[adj_t]
price_native = live_prices[adj_t]
price_cny = price_native * fx_final[h_info['cur']]

if price_cny > 0:
    gap_beta = target_b - curr_beta
    needed_cny = gap_beta * total_assets / h_info['lev']
    shares = round(needed_cny / price_cny)
    actual_cost_native = abs(shares * price_native)
    actual_cost_cny = abs(shares * price_cny)
    
    if shares != 0:
        action = "买入" if shares > 0 else "卖出"
        st.markdown(f"### 📢 建议指令：{action} **{abs(shares):,}** 股 {selected_adj}")
        st.markdown(f"#### 💵 对应人民币金额: <span style='color:#ff4b4b'>¥{actual_cost_cny:,.2f} CNY</span>", unsafe_allow_html=True)
        if h_info['cur'] != "CNY":
            st.write(f"原始币种预估: {actual_cost_native:,.2f} {h_info['cur']}")
    else:
        st.success("✅ 当前 Beta 符合目标。")

st.caption(f"最后更新时间: {time.strftime('%H:%M:%S')}")
