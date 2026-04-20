import streamlit as st
import yfinance as yf
import pandas as pd
import time

# 1. 页面配置
st.set_page_config(page_title="Beta Radar Pro", page_icon="📈", layout="wide")

# ==========================================
# 2. 核心数据抓取 (统一使用 Yahoo Finance)
# ==========================================
@st.cache_data(ttl=120) # 每2分钟尝试同步一次，保证准时
def get_live_market_data(config):
    # 默认兜底汇率 (根据 2026-04 市场校准)
    fx = {"USD": 7.2418, "HKD": 0.9265, "CNY": 1.0}
    prices = {}
    
    try:
        # A. 抓取汇率 - 对应你表格中的 CURRENCY:USDCNY 和 CURRENCY:HKDCNY
        # yfinance 的行情源与 GoogleFinance 基本一致
        usd_data = yf.Ticker("USDCNY=X").fast_info
        if 'last_price' in usd_data:
            fx["USD"] = usd_data['last_price']
            
        hkd_data = yf.Ticker("HKDCNY=X").fast_info
        if 'last_price' in hkd_data:
            fx["HKD"] = hkd_data['last_price']
    except Exception as e:
        st.warning(f"⚠️ 无法同步实时汇率，已使用校准兜底值。")

    # B. 抓取持仓标的价格
    for ticker, info in config.items():
        try:
            # 统一使用 yf 抓取，不再请求腾讯接口
            stock = yf.Ticker(ticker)
            p = stock.fast_info.get('last_price', 0.0)
            
            # 针对国内 A 股和港股的非交易时段兜底逻辑
            if p == 0:
                p = stock.history(period="1d")['Close'].iloc[-1]
        except:
            p = 1.0 # 极端故障保底
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
    "c_cash": 3400000.0 # 现金 3.4M
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
    
    if st.button("💾 保存持仓数据", use_container_width=True, type="primary"):
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

# 执行数据抓取
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
st.info(f"🌐 **实时同步 Yahoo/Google 汇率**: USD/CNY = **{fx_final['USD']:.4f}** | HKD/CNY = **{fx_final['HKD']:.4f}**")

# 指标看板
m1, m2, m3 = st.columns(3)
m1.metric("总资产 (CNY)", f"¥{total_assets:,.2f}")
m2.metric("当前实时 Beta", f"{curr_beta:.3f}")
m3.metric("整体现金占比", f"{(st.session_state.saved_data['c_cash']/total_assets*100):.2f}%")

# 结构占比统计
st.markdown("---")
st.subheader("📊 杠杆资产分布 (含现金)")
p1, p2, p3, p4 = st.columns(4)
p1.write(f"🟢 **1倍资产**: {(lev_sums[1.0]/total_assets*100):.1f}%")
p2.write(f"🟡 **2倍资产**: {(lev_sums[2.0]/total_assets*100):.1f}%")
p3.write(f"🔴 **3倍资产**: {(lev_sums[3.0]/total_assets*100):.1f}%")
p4.write(f"💰 **纯现金位**: {(st.session_state.saved_data['c_cash']/total_assets*100):.1f}%")

# 持仓详情
st.subheader("📋 持仓详情明细")
df_list = []
for t, h in holdings_map.items():
    v_cny = live_prices[t] * h['qty'] * fx_final[h['cur']]
    df_list.append({
        "名称": h['name'], "代码": t, "持仓": f"{h['qty']:,}",
        "实时单价": f"{live_prices[t]:.3f}", "市值(CNY)": f"{v_cny:,.0f}",
        "权重": f"{(v_cny/total_assets*100):.2f}%", "杠杆": f"{h['lev']}x"
    })
st.table(pd.DataFrame(df_list))

# 调仓辅助
st.markdown("---")
st.subheader("🎯 调仓计算器")
t_col1, t_col2 = st.columns(2)
with t_col1:
    target_b = st.slider("设定 Beta 目标", 0.0, 1.5, 0.9, 0.01)
with t_col2:
    selected_adj = st.selectbox("调仓标的", [h['name'] for h in holdings_map.values()], index=3)

adj_t = next(k for k, v in holdings_map.items() if v['name'] == selected_adj)
h_info = holdings_map[adj_t]
price_cny = live_prices[adj_t] * fx_final[h_info['cur']]

if price_cny > 0:
    gap_beta = target_b - curr_beta
    needed_cny = gap_beta * total_assets / h_info['lev']
    shares = round(needed_cny / price_cny)
    
    if shares != 0:
        action = "买入" if shares > 0 else "卖出"
        st.markdown(f"### 📢 指令：{action} **{abs(shares):,}** 股 {selected_adj}")
        st.markdown(f"#### 💵 预估金额: <span style='color:#ff4b4b'>¥{abs(shares * price_cny):,.2f} CNY</span>", unsafe_allow_html=True)

st.caption(f"全量数据源: Yahoo Finance | 缓存刷新率: 120s | 当前时间: {time.strftime('%H:%M:%S')}")
