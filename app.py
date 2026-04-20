import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import time

# 1. 页面配置
st.set_page_config(page_title="Beta Radar Pro", page_icon="📈", layout="wide")

# ==========================================
# 2. 混合动力数据引擎 (汇率用国际源, A股用国内源)
# ==========================================
@st.cache_data(ttl=60) # 缩短缓存至60秒，提高实时性
def get_live_market_data(config):
    # 2026-04 实时校准兜底汇率
    fx = {"USD": 7.2420, "HKD": 0.9268, "CNY": 1.0}
    prices = {}
    
    # A. 汇率：同步你 Google 表格的国际数据源 (Yahoo Finance)
    try:
        usd_info = yf.Ticker("USDCNY=X").fast_info
        if 'last_price' in usd_info: fx["USD"] = usd_info['last_price']
        hkd_info = yf.Ticker("HKDCNY=X").fast_info
        if 'last_price' in hkd_info: fx["HKD"] = hkd_info['last_price']
    except:
        pass

    # B. 股价：针对不同市场使用最准的接口
    for ticker, info in config.items():
        p = 0.0
        # 1. 如果是 A 股 (.SS)，使用新浪财经实时接口 (最准)
        if ticker.endswith(".SS"):
            try:
                code = ticker.replace(".SS", "").lower()
                symbol = f"sh{code}"
                resp = requests.get(f"http://hq.sinajs.cn/list={symbol}", timeout=2, headers={'Referer': 'http://finance.sina.com.cn'}).text
                # 解析格式: var hq_str_sh513100="...,价格,..."
                data = resp.split('"')[1].split(',')
                if len(data) > 3: p = float(data[3])
            except: pass
            
        # 2. 如果是港股或美股，或者 A 股接口失败，使用 Yahoo
        if p == 0:
            try:
                p = yf.Ticker(ticker).fast_info.get('last_price', 0.0)
                if p == 0: # 盘后处理
                    p = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
            except:
                p = 1.0
        prices[ticker] = p
        
    return fx, prices

# ==========================================
# 3. 持仓数据初始化
# ==========================================
DEFAULT_CONFIG = {
    "c124": 1174300,    # 513100.SS
    "c216": 21600,      # 513300.SS
    "c320": 600,        # 2834.HK
    "c274": 77600,      # 7266.HK
    "c_tqqq": 0,        
    "c_cash": 3250000.0 
}

if 'saved_data' not in st.session_state:
    st.session_state.saved_data = DEFAULT_CONFIG.copy()

# ==========================================
# 4. 侧边栏
# ==========================================
with st.sidebar:
    st.header("⚙️ 持仓配置")
    input_c124 = st.number_input("513100.SS 数量", value=st.session_state.saved_data["c124"])
    input_c216 = st.number_input("513300.SS 数量", value=st.session_state.saved_data["c216"])
    input_c320 = st.number_input("2834.HK 数量", value=st.session_state.saved_data["c320"])
    input_c274 = st.number_input("7266.HK 数量", value=st.session_state.saved_data["c274"])
    input_c_tqqq = st.number_input("TQQQ 数量", value=st.session_state.saved_data["c_tqqq"])
    st.markdown("---")
    input_c_cash = st.number_input("现金储备 (CNY)", value=st.session_state.saved_data["c_cash"], step=10000.0)
    
    if st.button("💾 保存并更新数据", use_container_width=True, type="primary"):
        st.session_state.saved_data.update({
            "c124": input_c124, "c216": input_c216, "c320": input_c320,
            "c274": input_c274, "c_tqqq": input_c_tqqq, "c_cash": input_c_cash
        })
        st.rerun()

holdings_map = {
    "513100.SS": {"name": "纳指100ETF(A)", "qty": st.session_state.saved_data["c124"], "lev": 1.0, "cur": "CNY"},
    "513300.SS": {"name": "纳指ETF(A)",    "qty": st.session_state.saved_data["c216"], "lev": 1.0, "cur": "CNY"},
    "2834.HK":   {"name": "纳指ETF(港)",    "qty": st.session_state.saved_data["c320"], "lev": 1.0, "cur": "HKD"},
    "7266.HK":   {"name": "两倍纳指(港)",    "qty": st.session_state.saved_data["c274"], "lev": 2.0, "cur": "HKD"},
    "TQQQ":      {"name": "三倍纳指(美)",    "qty": st.session_state.saved_data["c_tqqq"], "lev": 3.0, "cur": "USD"}
}

fx_final, live_prices = get_live_market_data(holdings_map)

# ==========================================
# 5. 计算逻辑
# ==========================================
lev_sums = {1.0: 0.0, 2.0: 0.0, 3.0: 0.0}
for t, h in holdings_map.items():
    val_cny = live_prices[t] * h['qty'] * fx_final[h['cur']]
    lev_sums[h['lev']] += val_cny

total_mkt_val = sum(lev_sums.values())
total_assets = total_mkt_val + st.session_state.saved_data["c_cash"]
curr_beta = sum(live_prices[t] * h['qty'] * fx_final[h['cur']] * h['lev'] for t, h in holdings_map.items()) / total_assets if total_assets > 0 else 0

# ==========================================
# 6. UI 展现
# ==========================================
st.title("🛡️ 纳指平衡监控终端")
st.info(f"🌐 **汇率源 (Yahoo/Google)**: USD/CNY = **{fx_final['USD']:.4f}** | HKD/CNY = **{fx_final['HKD']:.4f}**")

m1, m2, m3 = st.columns(3)
m1.metric("总资产 (CNY)", f"¥{total_assets:,.2f}")
m2.metric("当前实时 Beta", f"{curr_beta:.3f}")
m3.metric("整体现金占比", f"{(st.session_state.saved_data['c_cash']/total_assets*100):.2f}%")

st.markdown("---")
st.subheader("📊 资产结构占比")
p1, p2, p3, p4 = st.columns(4)
p1.write(f"🟢 **1倍资产**: {(lev_sums[1.0]/total_assets*100):.1f}%")
p2.write(f"🟡 **2倍资产**: {(lev_sums[2.0]/total_assets*100):.1f}%")
p3.write(f"🔴 **3倍资产**: {(lev_sums[3.0]/total_assets*100):.1f}%")
p4.write(f"💰 **纯现金位**: {(st.session_state.saved_data['c_cash']/total_assets*100):.1f}%")

st.subheader("📋 持仓详情")
df_list = []
for t, h in holdings_map.items():
    v_cny = live_prices[t] * h['qty'] * fx_final[h['cur']]
    df_list.append({
        "名称": h['name'], "代码": t, "持仓": f"{h['qty']:,}",
        "实时单价": f"{live_prices[t]:.3f}", "市值(CNY)": f"{v_cny:,.0f}",
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
price_cny = live_prices[adj_t] * fx_final[h_info['cur']]

if price_cny > 0:
    gap_beta = target_b - curr_beta
    needed_cny = gap_beta * total_assets / h_info['lev']
    shares = round(needed_cny / price_cny)
    
    if shares != 0:
        action = "买入" if shares > 0 else "卖出"
        st.markdown(f"### 📢 建议指令：{action} **{abs(shares):,}** 股 {selected_adj}")
        st.markdown(f"#### 💵 预估人民币金额: <span style='color:#ff4b4b'>¥{abs(shares * price_cny):,.2f} CNY</span>", unsafe_allow_html=True)

st.caption(f"混合源: A股(新浪财经) / 港美股&汇率(Yahoo Finance) | 更新时间: {time.strftime('%H:%M:%S')}")
