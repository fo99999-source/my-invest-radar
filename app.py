import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import time

# 1. 页面配置
st.set_page_config(page_title="Beta Radar Pro", page_icon="📈", layout="wide")

# ==========================================
# 2. 数据获取函数 (完全实时化)
# ==========================================
@st.cache_data(ttl=300) # 每5分钟强制刷新
def get_live_market_data(config):
    # 默认汇率兜底
    fx = {"USD": 7.24, "HKD": 0.925, "CNY": 1.0}
    prices = {}
    
    # A. 抓取实时汇率 (腾讯接口)
    try:
        r_usd = requests.get("http://qt.gtimg.cn/q=usdcny", timeout=2).text.split('~')
        if len(r_usd) > 3: fx["USD"] = float(r_usd[3])
        r_hkd = requests.get("http://qt.gtimg.cn/q=hkdcny", timeout=2).text.split('~')
        if len(r_hkd) > 3: fx["HKD"] = float(r_hkd[3])
    except:
        pass

    # B. 抓取实时股价
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
        
    return fx, prices

# ==========================================
# 3. 持仓数据初始化 (现金已更正为 3.4M)
# ==========================================
DEFAULT_CONFIG = {
    "c124": 1174300,  # 513100.SS
    "c216": 21600,    # 513300.SS
    "c320": 600,      # 2834.HK
    "c274": 77600,    # 7266.HK
    "c_tqqq": 0,      
    "c_cash": 3250000.0 # 已更新
}

if 'saved_data' not in st.session_state:
    st.session_state.saved_data = DEFAULT_CONFIG.copy()

# ==========================================
# 4. 侧边栏：交互输入
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
    
    if st.button("💾 保存并锁定当前持仓", use_container_width=True, type="primary"):
        st.session_state.saved_data.update({
            "c124": input_c124, "c216": input_c216, "c320": input_c320,
            "c274": input_c274, "c_tqqq": input_c_tqqq, "c_cash": input_c_cash
        })
        st.success("数据已成功保存为默认！")
        time.sleep(0.5)
        st.rerun()

# 核心映射配置
holdings_map = {
    "513100.SS": {"name": "纳指100ETF(A)", "qty": st.session_state.saved_data["c124"], "lev": 1.0, "cur": "CNY", "tx": "sh513100"},
    "513300.SS": {"name": "纳指ETF(A)",    "qty": st.session_state.saved_data["c216"], "lev": 1.0, "cur": "CNY", "tx": "sh513300"},
    "2834.HK":   {"name": "纳指ETF(港)",    "qty": st.session_state.saved_data["c320"], "lev": 1.0, "cur": "HKD", "tx": "hk02834"},
    "7266.HK":   {"name": "两倍纳指(港)",    "qty": st.session_state.saved_data["c274"], "lev": 2.0, "cur": "HKD", "tx": "hk07266"},
    "TQQQ":      {"name": "三倍纳指(美)",    "qty": st.session_state.saved_data["c_tqqq"], "lev": 3.0, "cur": "USD", "tx": "usTQQQ"}
}

# 抓取实时数据
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
st.info(f"📊 **实时汇率已获取**: USD/CNY = {fx_final['USD']:.4f} | HKD/CNY = {fx_final['HKD']:.4f}")

# 第一行：核心宏观指标
m1, m2, m3 = st.columns(3)
m1.metric("总资产 (CNY)", f"¥{total_assets:,.2f}")
m2.metric("当前实时 Beta", f"{curr_beta:.3f}")
m3.metric("整体现金占比", f"{(st.session_state.saved_data['c_cash']/total_assets*100):.2f}%")

# 第二行：杠杆分布比例
st.markdown("---")
st.subheader("📊 资产结构占比 (含现金)")
p1, p2, p3, p4 = st.columns(4)
p1.write(f"🟢 **1倍资产**: {(lev_sums[1.0]/total_assets*100):.1f}%")
p2.write(f"🟡 **2倍资产**: {(lev_sums[2.0]/total_assets*100):.1f}%")
p3.write(f"🔴 **3倍资产**: {(lev_sums[3.0]/total_assets*100):.1f}%")
p4.write(f"💰 **纯现金位**: {(st.session_state.saved_data['c_cash']/total_assets*100):.1f}%")

# 第三行：持仓详情
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

# 第四行：调仓助手
st.markdown("---")
st.subheader("🎯 调仓助手")
t_col1, t_col2 = st.columns(2)
with t_col1:
    target_b = st.slider("设定理想 Beta 目标", 0.0, 1.5, 0.9, 0.01)
with t_col2:
    selected_adj = st.selectbox("选择调仓标的", [h['name'] for h in holdings_map.values()], index=3)

# 调仓计算逻辑
adj_t = next(k for k, v in holdings_map.items() if v['name'] == selected_adj)
h_info = holdings_map[adj_t]
price_cny = live_prices[adj_t] * fx_final[h_info['cur']]

if price_cny > 0:
    gap_beta = target_b - curr_beta
    needed_cny = gap_beta * total_assets / h_info['lev']
    shares = round(needed_cny / price_cny)
    
    if shares != 0:
        action = "买入" if shares > 0 else "卖出"
        st.markdown(f"### 📢 建议操作：{action} **{abs(shares):,}** 股 {selected_adj}")
        st.markdown(f"#### 💵 对应金额: <span style='color:#ff4b4b'>¥{abs(shares * price_cny):,.2f} CNY</span>", unsafe_allow_html=True)
    else:
        st.success("✅ 当前 Beta 比例理想，无需调整。")

st.caption(f"数据更新时间: {time.strftime('%H:%M:%S')} (自动抓取行情与汇率)")
