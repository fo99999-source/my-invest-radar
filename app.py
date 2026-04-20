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
# 默认配置模板
DEFAULT_CONFIG = {
    "c124": 1242800,
    "c216": 21600,
    "c320": 320,
    "c274": 27400,
    "c_tqqq": 0,
    "c_cash": 4900000.0,
    "fx_usd": 7.24,
    "fx_hkd": 0.925
}

# 初始化会话数据
if 'saved_data' not in st.session_state:
    st.session_state.saved_data = DEFAULT_CONFIG.copy()

# ==========================================
# 3. 侧边栏：输入与控制
# ==========================================
with st.sidebar:
    st.header("⚙️ 持仓与设置")
    
    # 手动输入区域
    input_c124 = st.number_input("513100.SS 数量", value=st.session_state.saved_data["c124"])
    input_c216 = st.number_input("513300.SS 数量", value=st.session_state.saved_data["c216"])
    input_c320 = st.number_input("2834.HK 数量", value=st.session_state.saved_data["c320"])
    input_c274 = st.number_input("7266.HK 数量", value=st.session_state.saved_data["c274"])
    input_c_tqqq = st.number_input("TQQQ 数量", value=st.session_state.saved_data["c_tqqq"])
    input_c_cash = st.number_input("现金储备 (CNY)", value=st.session_state.saved_data["c_cash"], step=10000.0)
    
    st.markdown("---")
    st.subheader("💱 汇率微调")
    input_fx_usd = st.number_input("USD/CNY 汇率", value=st.session_state.saved_data["fx_usd"], format="%.4f")
    input_fx_hkd = st.number_input("HKD/CNY 汇率", value=st.session_state.saved_data["fx_hkd"], format="%.4f")

    # 核心按钮：保存
    if st.button("💾 保存并应用当前修改", use_container_width=True, type="primary"):
        st.session_state.saved_data.update({
            "c124": input_c124, "c216": input_c216, "c320": input_c320,
            "c274": input_c274, "c_tqqq": input_c_tqqq, "c_cash": input_c_cash,
            "fx_usd": input_fx_usd, "fx_hkd": input_fx_hkd
        })
        st.success("数据已锁定！")
        time.sleep(0.5)
        st.rerun()

    # 核心按钮：恢复默认
    if st.button("🔄 恢复到默认设置", use_container_width=True):
        st.session_state.saved_data = DEFAULT_CONFIG.copy()
        st.rerun()

# 定义当前生效的配置
current_conf = st.session_state.saved_data

holdings_map = {
    "513100.SS": {"name": "纳指100ETF(A)", "qty": current_conf["c124"], "lev": 1.0, "cur": "CNY", "tx": "sh513100"},
    "513300.SS": {"name": "纳指ETF(A)",    "qty": current_conf["c216"], "lev": 1.0, "cur": "CNY", "tx": "sh513300"},
    "2834.HK":   {"name": "纳指ETF(港)",    "qty": current_conf["c320"], "lev": 1.0, "cur": "HKD", "tx": "hk02834"},
    "7266.HK":   {"name": "两倍纳指(港)",    "qty": current_conf["c274"], "lev": 2.0, "cur": "HKD", "tx": "hk07266"},
    "TQQQ":      {"name": "三倍纳指(美)",    "qty": current_conf["c_tqqq"], "lev": 3.0, "cur": "USD", "tx": "usTQQQ"}
}

# ==========================================
# 4. 数据抓取逻辑 (增加汇率自动校准)
# ==========================================
@st.cache_data(ttl=300)
def fetch_prices(config):
    prices = {}
    # 尝试自动更新汇率 (仅作参考)
    auto_fx = {"USD": current_conf["fx_usd"], "HKD": current_conf["fx_hkd"]}
    try:
        r_usd = requests.get("http://qt.gtimg.cn/q=usdcny", timeout=1).text.split('~')
        if len(r_usd) > 3: auto_fx["USD"] = float(r_usd[3])
        r_hkd = requests.get("http://qt.gtimg.cn/q=hkdcny", timeout=1).text.split('~')
        if len(r_hkd) > 3: auto_fx["HKD"] = float(r_hkd[3])
    except: pass

    for ticker, info in config.items():
        p = 0.0
        # 优先国内接口
        try:
            resp = requests.get(f"http://qt.gtimg.cn/q={info['tx']}", timeout=1).text.split('~')
            if len(resp) > 3: p = float(resp[3])
        except: pass
        
        # 备选雅虎
        if p == 0:
            try: p = yf.Ticker(ticker).fast_info.get('last_price', 0.0)
            except: p = 1.0
        prices[ticker] = p
    return auto_fx, prices

# 执行抓取
auto_fx_val, live_prices = fetch_prices(holdings_map)

# 汇率策略：如果用户没有手动改过汇率，就用自动抓取的；如果手动改了，就以手动为准。
# 注意：本程序目前以侧边栏显示的数值为最终计算准则。
fx_final = {"USD": current_conf["fx_usd"], "HKD": current_conf["fx_hkd"], "CNY": 1.0}

# ==========================================
# 5. 计算显示区
# ==========================================
total_mkt_val = sum(live_prices[t] * h['qty'] * fx_final[h['cur']] for t, h in holdings_map.items())
total_assets = total_mkt_val + current_conf["c_cash"]
curr_beta = sum(live_prices[t] * h['qty'] * fx_final[h['cur']] * h['lev'] for t, h in holdings_map.items()) / total_assets if total_assets > 0 else 0

st.success(f"💹 **生效汇率**: USD={fx_final['USD']:.4f} | HKD={fx_final['HKD']:.4f} (若不准请在左侧手动修改并保存)")

m1, m2, m3 = st.columns(3)
m1.metric("总资产 (CNY)", f"¥{total_assets:,.2f}")
m2.metric("当前 Beta", f"{curr_beta:.3f}")
m3.metric("现金占比", f"{(current_conf['c_cash']/total_assets*100):.1f}%")

# 持仓表
df_list = []
for t, h in holdings_map.items():
    v_cny = live_prices[t] * h['qty'] * fx_final[h['cur']]
    df_list.append({
        "名称": h['name'], "代码": t, "持仓": f"{h['qty']:,}",
        "价格": f"{live_prices[t]:.3f}", "市值(CNY)": f"{v_cny:,.0f}",
        "占比": f"{(v_cny/total_assets*100):.2f}%", "杠杆": f"{h['lev']}x"
    })
st.table(pd.DataFrame(df_list))

# 调仓建议
st.markdown("---")
st.subheader("🎯 调仓模拟")
t_col1, t_col2 = st.columns(2)
with t_col1:
    target_b = st.slider("目标 Beta", 0.0, 1.5, 0.9, 0.01)
with t_col2:
    selected_adj = st.selectbox("调仓标的", [h['name'] for h in holdings_map.values()], index=3)

# 计算
adj_t = next(k for k, v in holdings_map.items() if v['name'] == selected_adj)
t_p_cny = live_prices[adj_t] * fx_final[holdings_map[adj_t]['cur']]
if t_p_cny > 0:
    gap = (target_b - curr_beta) * total_assets
    shares = round(gap / (holdings_map[adj_t]['lev'] * t_p_cny))
    if shares != 0:
        st.warning(f"指令：{'买入' if shares > 0 else '卖出'} {abs(shares):,} 股 {selected_adj}")
        st.write(f"金额：{abs(shares * live_prices[adj_t]):,.2f} {holdings_map[adj_t]['cur']}")
