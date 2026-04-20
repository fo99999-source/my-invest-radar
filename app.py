import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import json
import os
import time

# 1. 配置文件路径（储存在当前目录下）
DB_FILE = "portfolio_data.json"

# 2. 页面配置
st.set_page_config(page_title="Beta Radar Pro", page_icon="📈", layout="wide")

# ==========================================
# 3. 存储功能函数
# ==========================================
def load_data():
    """从本地文件加载数据"""
    # 初始默认数据
    default = {
        "holdings": {
            "c124": 1174300, "c216": 21600, "c320": 600, "c274": 77600, "c_tqqq": 0, "c_cash": 3400000.0
        },
        "fx": {"USD": 6.28, "HKD": 0.87}
    }
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except:
            return default
    return default

def save_data(holdings, fx):
    """保存数据到本地文件"""
    data = {"holdings": holdings, "fx": fx}
    with open(DB_FILE, "w") as f:
        json.dump(data, f)

# ==========================================
# 4. 数据获取引擎
# ==========================================
@st.cache_data(ttl=60)
def get_live_market_data(config):
    # 默认贴底汇率
    fx = {"USD": 6.28, "HKD": 0.87, "CNY": 1.0}
    prices = {}
    try:
        usd_info = yf.Ticker("USDCNY=X").fast_info
        if 'last_price' in usd_info: fx["USD"] = usd_info['last_price']
        hkd_info = yf.Ticker("HKDCNY=X").fast_info
        if 'last_price' in hkd_info: fx["HKD"] = hkd_info['last_price']
    except: pass

    for ticker, info in config.items():
        p = 0.0
        if ticker.endswith(".SS"):
            try:
                code = ticker.replace(".SS", "").lower()
                resp = requests.get(f"http://hq.sinajs.cn/list=sh{code}", timeout=2, headers={'Referer': 'http://finance.sina.com.cn'}).text
                data = resp.split('"')[1].split(',')
                if len(data) > 3: p = float(data[3])
            except: pass
        if p == 0:
            try:
                p = yf.Ticker(ticker).fast_info.get('last_price', 0.0)
                if p == 0: p = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
            except: p = 1.0
        prices[ticker] = p
    return fx, prices

# ==========================================
# 5. 初始化状态 (优先读取本地文件)
# ==========================================
persisted_data = load_data()

if 'saved_data' not in st.session_state:
    st.session_state.saved_data = persisted_data["holdings"]
    st.session_state.manual_fx = persisted_data["fx"]

# ==========================================
# 6. 侧边栏
# ==========================================
with st.sidebar:
    st.header("⚙️ 配置管理")
    
    st.subheader("📦 持仓数量")
    input_c124 = st.number_input("513100.SS", value=st.session_state.saved_data["c124"])
    input_c216 = st.number_input("513300.SS", value=st.session_state.saved_data["c216"])
    input_c320 = st.number_input("2834.HK", value=st.session_state.saved_data["c320"])
    input_c274 = st.number_input("7266.HK", value=st.session_state.saved_data["c274"])
    input_c_tqqq = st.number_input("TQQQ", value=st.session_state.saved_data["c_tqqq"])
    input_c_cash = st.number_input("现金储备 (CNY)", value=st.session_state.saved_data["c_cash"], step=10000.0)
    
    st.markdown("---")
    st.subheader("💱 汇率干预")
    input_fx_usd = st.number_input("USD/CNY 覆盖", value=st.session_state.manual_fx["USD"], format="%.4f")
    input_fx_hkd = st.number_input("HKD/CNY 覆盖", value=st.session_state.manual_fx["HKD"], format="%.4f")
    
    if st.button("💾 永久保存到本地", use_container_width=True, type="primary"):
        new_holdings = {
            "c124": input_c124, "c216": input_c216, "c320": input_c320,
            "c274": input_c274, "c_tqqq": input_c_tqqq, "c_cash": input_c_cash
        }
        new_fx = {"USD": input_fx_usd, "HKD": input_fx_hkd}
        
        # 写入文件
        save_data(new_holdings, new_fx)
        # 更新当前 Session
        st.session_state.saved_data = new_holdings
        st.session_state.manual_fx = new_fx
        
        st.success("数据已写入本地文件，下次打开将自动加载！")
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

_, live_prices = get_live_market_data(holdings_map)
final_fx = {"USD": st.session_state.manual_fx["USD"], "HKD": st.session_state.manual_fx["HKD"], "CNY": 1.0}

# ==========================================
# 7. 计算与 UI
# ==========================================
lev_sums = {1.0: 0.0, 2.0: 0.0, 3.0: 0.0}
for t, h in holdings_map.items():
    val_cny = live_prices[t] * h['qty'] * final_fx[h['cur']]
    lev_sums[h['lev']] += val_cny

total_mkt_val = sum(lev_sums.values())
total_assets = total_mkt_val + st.session_state.saved_data["c_cash"]
curr_beta = sum(live_prices[t] * h['qty'] * final_fx[h['cur']] * h['lev'] for t, h in holdings_map.items()) / total_assets if total_assets > 0 else 0

st.title("🛡️ 纳指平衡监控终端 (持久化版)")
st.info(f"📊 **当前应用汇率**: USD/CNY = **{final_fx['USD']:.4f}** | HKD/CNY = **{final_fx['HKD']:.4f}**")

m1, m2, m3 = st.columns(3)
m1.metric("总资产 (CNY)", f"¥{total_assets:,.2f}")
m2.metric("当前实时 Beta", f"{curr_beta:.3f}")
m3.metric("整体现金占比", f"{(st.session_state.saved_data['c_cash']/total_assets*100):.2f}%")

st.markdown("---")
df_list = []
for t, h in holdings_map.items():
    v_cny = live_prices[t] * h['qty'] * final_fx[h['cur']]
    df_list.append({
        "名称": h['name'], "持仓": f"{h['qty']:,}",
        "单价": f"{live_prices[t]:.3f}", "市值(CNY)": f"{v_cny:,.0f}",
        "权重": f"{(v_cny/total_assets*100):.2f}%", "杠杆": f"{h['lev']}x"
    })
st.table(pd.DataFrame(df_list))

# 调仓助手
st.subheader("🎯 调仓助手")
t_col1, t_col2 = st.columns(2)
with t_col1:
    target_b = st.slider("设定理想 Beta 目标", 0.0, 1.5, 0.9, 0.01)
with t_col2:
    selected_adj = st.selectbox("选择调仓标的", [h['name'] for h in holdings_map.values()], index=3)

adj_t = next(k for k, v in holdings_map.items() if v['name'] == selected_adj)
price_cny = live_prices[adj_t] * final_fx[holdings_map[adj_t]['cur']]

if price_cny > 0:
    gap_beta = target_b - curr_beta
    needed_cny = gap_beta * total_assets / holdings_map[adj_t]['lev']
    shares = round(needed_cny / price_cny)
    if shares != 0:
        action = "买入" if shares > 0 else "卖出"
        st.markdown(f"### 📢 指令：{action} **{abs(shares):,}** 股 {selected_adj}")
        st.markdown(f"#### 预估金额: ¥{abs(shares * price_cny):,.2f} CNY")

st.caption(f"本地存储已激活 | 数据文件: {DB_FILE} | 更新时间: {time.strftime('%H:%M:%S')}")
