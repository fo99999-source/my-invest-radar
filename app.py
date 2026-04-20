import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import time

# 1. 页面配置
st.set_page_config(page_title="Beta Radar Pro", page_icon="📈", layout="wide")

# ==========================================
# 2. 数据获取引擎
# ==========================================
@st.cache_data(ttl=60)
def get_live_market_data(config):
    # 【已更新】默认兜底汇率
    fx = {"USD": 6.28, "HKD": 0.87, "CNY": 1.0}
    prices = {}
    
    # A. 尝试从 Yahoo Finance 同步实时汇率
    try:
        usd_info = yf.Ticker("USDCNY=X").fast_info
        if 'last_price' in usd_info: fx["USD"] = usd_info['last_price']
        hkd_info = yf.Ticker("HKDCNY=X").fast_info
        if 'last_price' in hkd_info: fx["HKD"] = hkd_info['last_price']
    except:
        pass

    # B. 抓取股价
    for ticker, info in config.items():
        p = 0.0
        # 1. A 股优先使用新浪财经
        if ticker.endswith(".SS"):
            try:
                code = ticker.replace(".SS", "").lower()
                symbol = f"sh{code}"
                resp = requests.get(f"http://hq.sinajs.cn/list={symbol}", timeout=2, headers={'Referer': 'http://finance.sina.com.cn'}).text
                data = resp.split('"')[1].split(',')
                if len(data) > 3: p = float(data[3])
            except: pass
            
        # 2. 港美股或 A 股失败时使用 Yahoo
        if p == 0:
            try:
                p = yf.Ticker(ticker).fast_info.get('last_price', 0.0)
                if p == 0:
                    p = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
            except:
                p = 1.0
        prices[ticker] = p
        
    return fx, prices

# ==========================================
# 3. 持仓与汇率状态初始化
# ==========================================
DEFAULT_CONFIG = {
    "c124": 1174300,    # 513100.SS
    "c216": 21600,      # 513300.SS
    "c320": 600,        # 2834.HK
    "c274": 77600,      # 7266.HK
    "c_tqqq": 0,        
    "c_cash": 3400000.0 
}

# 预加载实时数据用于初始化侧边栏
initial_fx, _ = get_live_market_data({})

if 'saved_data' not in st.session_state:
    st.session_state.saved_data = DEFAULT_CONFIG.copy()
    # 初始手动汇率默认为实时抓取值
    st.session_state.manual_fx = {"USD": initial_fx["USD"], "HKD": initial_fx["HKD"]}

# ==========================================
# 4. 侧边栏：持仓与汇率手动控制
# ==========================================
with st.sidebar:
    st.header("⚙️ 持仓与汇率配置")
    
    # --- 持仓部分 ---
    st.subheader("📦 持仓数量")
    input_c124 = st.number_input("513100.SS", value=st.session_state.saved_data["c124"])
    input_c216 = st.number_input("513300.SS", value=st.session_state.saved_data["c216"])
    input_c320 = st.number_input("2834.HK", value=st.session_state.saved_data["c320"])
    input_c274 = st.number_input("7266.HK", value=st.session_state.saved_data["c274"])
    input_c_tqqq = st.number_input("TQQQ", value=st.session_state.saved_data["c_tqqq"])
    input_c_cash = st.number_input("现金储备 (CNY)", value=st.session_state.saved_data["c_cash"], step=10000.0)
    
    st.markdown("---")
    
    # --- 汇率手动调整部分 ---
    st.subheader("💱 汇率手动干预")
    st.caption("默认显示实时值，修改并保存后将锁定汇率")
    input_fx_usd = st.number_input("USD/CNY 覆盖", value=st.session_state.manual_fx["USD"], format="%.4f")
    input_fx_hkd = st.number_input("HKD/CNY 覆盖", value=st.session_state.manual_fx["HKD"], format="%.4f")
    
    if st.button("💾 保存所有修改", use_container_width=True, type="primary"):
        st.session_state.saved_data.update({
            "c124": input_c124, "c216": input_c216, "c320": input_c320,
            "c274": input_c274, "c_tqqq": input_c_tqqq, "c_cash": input_c_cash
        })
        st.session_state.manual_fx = {"USD": input_fx_usd, "HKD": input_fx_hkd}
        st.success("配置已保存！")
        time.sleep(0.5)
        st.rerun()

# 定义持仓结构
holdings_map = {
    "513100.SS": {"name": "纳指100ETF(A)", "qty": st.session_state.saved_data["c124"], "lev": 1.0, "cur": "CNY"},
    "513300.SS": {"name": "纳指ETF(A)",    "qty": st.session_state.saved_data["c216"], "lev": 1.0, "cur": "CNY"},
    "2834.HK":   {"name": "纳指ETF(港)",    "qty": st.session_state.saved_data["c320"], "lev": 1.0, "cur": "HKD"},
    "7266.HK":   {"name": "两倍纳指(港)",    "qty": st.session_state.saved_data["c274"], "lev": 2.0, "cur": "HKD"},
    "TQQQ":      {"name": "三倍纳指(美)",    "qty": st.session_state.saved_data["c_tqqq"], "lev": 3.0, "cur": "USD"}
}

# 获取实时价格
_, live_prices = get_live_market_data(holdings_map)
# 汇率使用手动覆盖值（默认为实时抓取，除非您在侧边栏修改）
final_fx = {"USD": st.session_state.manual_fx["USD"], "HKD": st.session_state.manual_fx["HKD"], "CNY": 1.0}

# ==========================================
# 5. 计算逻辑
# ==========================================
lev_sums = {1.0: 0.0, 2.0: 0.0, 3.0: 0.0}
for t, h in holdings_map.items():
    val_cny = live_prices[t] * h['qty'] * final_fx[h['cur']]
    lev_sums[h['lev']] += val_cny

total_mkt_val = sum(lev_sums.values())
total_assets = total_mkt_val + st.session_state.saved_data["c_cash"]
curr_beta = sum(live_prices[t] * h['qty'] * final_fx[h['cur']] * h['lev'] for t, h in holdings_map.items()) / total_assets if total_assets > 0 else 0

# ==========================================
# 6. UI 展现
# ==========================================
st.title("🛡️ 纳指平衡监控终端")
st.info(f"📊 **当前应用汇率**: USD/CNY = **{final_fx['USD']:.4f}** | HKD/CNY = **{final_fx['HKD']:.4f}**")

m1, m2, m3 = st.columns(3)
m1.metric("总资产 (CNY)", f"¥{total_assets:,.2f}")
m2.metric("当前实时 Beta", f"{curr_beta:.3f}")
m3.metric("整体现金占比", f"{(st.session_state.saved_data['c_cash']/total_assets*100):.2f}%")

st.markdown("---")
st.subheader("📋 持仓详情 (基于当前汇率)")
df_list = []
for t, h in holdings_map.items():
    v_cny = live_prices[t] * h['qty'] * final_fx[h['cur']]
    df_list.append({
        "名称": h['name'], "持仓": f"{h['qty']:,}",
        "单价": f"{live_prices[t]:.3f}", "市值(CNY)": f"{v_cny:,.0f}",
        "权重": f"{(v_cny/total_assets*100):.2f}%", "杠杆": f"{h['lev']}x"
    })
st.table(pd.DataFrame(df_list))

st.markdown("---")
st.subheader("🎯 调仓助手")
t_col1, t_col2 = st.columns(2)
with t_col1:
    target_b = st.slider("设定理想 Beta 目标", 0.0, 1.5, 0.9, 0.01)
with t_col2:
    selected_adj = st.selectbox("选择调仓标的", [h['name'] for h in holdings_map.values()], index=3)

adj_t = next(k for k, v in holdings_map.items() if v['name'] == selected_adj)
h_info = holdings_map[adj_t]
price_cny = live_prices[adj_t] * final_fx[h_info['cur']]

if price_cny > 0:
    gap_beta = target_b - curr_beta
    needed_cny = gap_beta * total_assets / h_info['lev']
    shares = round(needed_cny / price_cny)
    
    if shares != 0:
        action = "买入" if shares > 0 else "卖出"
        st.markdown(f"### 📢 建议指令：{action} **{abs(shares):,}** 股 {selected_adj}")
        st.markdown(f"#### 💵 对应金额: <span style='color:#ff4b4b'>¥{abs(shares * price_cny):,.2f} CNY</span>", unsafe_allow_html=True)

st.caption(f"数据源: 混合接口 | 默认兜底: 美元6.28, 港币0.87 | 更新时间: {time.strftime('%H:%M:%S')}")
