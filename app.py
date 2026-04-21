import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import json
import os
from datetime import datetime, timedelta, timezone

# 1. 配置文件路径
DB_FILE = "portfolio_data.json"

# 2. 页面配置
st.set_page_config(page_title="Beta Radar Pro", page_icon="🛡️", layout="wide")

# ==========================================
# 3. 时间工具：北京时间 (UTC+8)
# ==========================================
def get_beijing_time():
    tz_utc_8 = timezone(timedelta(hours=8))
    return datetime.now(tz_utc_8)

# ==========================================
# 4. 存储功能函数
# ==========================================
def load_data():
    default = {
        "holdings": {
            "c124": 1174300, "c216": 21600, "c320": 600, "c274": 77600, "c_tqqq": 0, "c_cash": 3400000
        },
        "fx": {"USD": 7.24, "HKD": 0.92}
    }
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except:
            return default
    return default

def save_data(holdings, fx):
    data = {"holdings": holdings, "fx": fx}
    with open(DB_FILE, "w") as f:
        json.dump(data, f)

# ==========================================
# 5. 数据获取引擎
# ==========================================
@st.cache_data(ttl=60)
def get_live_market_data(config, manual_fx):
    fx = {"USD": manual_fx["USD"], "HKD": manual_fx["HKD"], "CNY": 1.0}
    status = {"USD": "手动保底", "HKD": "手动保底"}
    prices = {}
    header = {'Referer': 'http://finance.sina.com.cn'}
    
    try:
        resp_u = requests.get("http://hq.sinajs.cn/list=fx_susdcny", timeout=2, headers=header).text
        data_u = resp_u.split('"')[1].split(',')
        if len(data_u) > 1: 
            fx["USD"] = float(data_u[1])
            status["USD"] = "实时"
    except: pass
        
    try:
        resp_h = requests.get("http://hq.sinajs.cn/list=fx_shkdcny", timeout=2, headers=header).text
        data_h = resp_h.split('"')[1].split(',')
        if len(data_h) > 1: 
            fx["HKD"] = float(data_h[1])
            status["HKD"] = "实时"
    except: pass 

    for ticker, info in config.items():
        p = 0.0
        if ticker.endswith(".SS"):
            try:
                code = ticker.replace(".SS", "").lower()
                resp = requests.get(f"http://hq.sinajs.cn/list=sh{code}", timeout=2, headers=header).text
                data = resp.split('"')[1].split(',')
                if len(data) > 3: p = float(data[3])
            except: pass
        if p == 0:
            try:
                p = yf.Ticker(ticker).fast_info.get('last_price', 0.0)
                if p == 0: p = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
            except: p = 1.0
        prices[ticker] = p
    return fx, status, prices

# ==========================================
# 6. 初始化状态
# ==========================================
persisted_data = load_data()
if 'saved_data' not in st.session_state:
    st.session_state.saved_data = persisted_data["holdings"]
    st.session_state.manual_fx = persisted_data["fx"]

# ==========================================
# 7. 侧边栏
# ==========================================
with st.sidebar:
    st.header("⚙️ 配置管理")
    st.subheader("📦 持仓数量")
    input_c124 = st.text_input("513100.SS", value=str(int(st.session_state.saved_data["c124"])))
    input_c216 = st.text_input("513300.SS", value=str(int(st.session_state.saved_data["c216"])))
    input_c320 = st.text_input("2834.HK", value=str(int(st.session_state.saved_data["c320"])))
    input_c274 = st.text_input("7266.HK", value=str(int(st.session_state.saved_data["c274"])))
    input_c_tqqq = st.text_input("TQQQ", value=str(int(st.session_state.saved_data["c_tqqq"])))
    input_c_cash = st.text_input("现金储备 (CNY)", value=str(int(st.session_state.saved_data["c_cash"])))
    
    st.markdown("---")
    st.subheader("💱 汇率覆盖 (保底用)")
    input_fx_usd = st.number_input("USD/CNY 覆盖", value=st.session_state.manual_fx["USD"], format="%.4f")
    input_fx_hkd = st.number_input("HKD/CNY 覆盖", value=st.session_state.manual_fx["HKD"], format="%.4f")
    
    if st.button("💾 永久保存修改", use_container_width=True, type="primary"):
        try:
            new_holdings = {
                "c124": int(float(input_c124)), "c216": int(float(input_c216)), 
                "c320": int(float(input_c320)), "c274": int(float(input_c274)), 
                "c_tqqq": int(float(input_c_tqqq)), "c_cash": int(float(input_c_cash))
            }
            new_fx = {"USD": input_fx_usd, "HKD": input_fx_hkd}
            save_data(new_holdings, new_fx)
            st.session_state.saved_data = new_holdings
            st.session_state.manual_fx = new_fx
            st.success("数据已同步！")
            st.rerun()
        except ValueError:
            st.error("请输入有效的整数格式")

holdings_map = {
    "513100.SS": {"name": "纳指100ETF(A)", "qty": st.session_state.saved_data["c124"], "lev": 1.0, "cur": "CNY"},
    "513300.SS": {"name": "纳指ETF(A)",    "qty": st.session_state.saved_data["c216"], "lev": 1.0, "cur": "CNY"},
    "2834.HK":   {"name": "纳指ETF(港)",    "qty": st.session_state.saved_data["c320"], "lev": 1.0, "cur": "HKD"},
    "7266.HK":   {"name": "两倍纳指(港)",    "qty": st.session_state.saved_data["c274"], "lev": 2.0, "cur": "HKD"},
    "TQQQ":      {"name": "三倍纳指(美)",    "qty": st.session_state.saved_data["c_tqqq"], "lev": 3.0, "cur": "USD"}
}

final_fx, fx_status, live_prices = get_live_market_data(holdings_map, st.session_state.manual_fx)

# ==========================================
# 8. 计算逻辑
# ==========================================
lev_sums = {1.0: 0.0, 2.0: 0.0, 3.0: 0.0}
for t, h in holdings_map.items():
    val_cny = live_prices[t] * h['qty'] * final_fx[h['cur']]
    lev_sums[h['lev']] += val_cny

mkt_val_total = sum(lev_sums.values())
cash_val = int(st.session_state.saved_data["c_cash"])
total_assets = mkt_val_total + cash_val
curr_beta = sum(live_prices[t] * h['qty'] * final_fx[h['cur']] * h['lev'] for t, h in holdings_map.items()) / total_assets if total_assets > 0 else 0

# ==========================================
# 9. UI 展现
# ==========================================
bj_now = get_beijing_time()
st.title("🛡️ 纳指平衡监控终端")
st.subheader(f"📅 北京日期：{bj_now.strftime('%Y年%m月%d日')}")

u_color = "green" if fx_status["USD"] == "实时" else "orange"
h_color = "green" if fx_status["HKD"] == "实时" else "orange"

st.markdown(f"""
> 汇率状态：
> USD/CNY: **{final_fx['USD']:.4f}** <span style='color:{u_color}'>({fx_status['USD']})</span> | 
> HKD/CNY: **{final_fx['HKD']:.4f}** <span style='color:{h_color}'>({fx_status['HKD']})</span>
""", unsafe_allow_html=True)

# 指标看板：增加了实时市值和曝险比例整数化
m1, m2, m3, m4 = st.columns(4)
m1.metric("总资产 (CNY)", f"¥{total_assets:,.0f}")
m2.metric("当前实时 Beta", f"{curr_beta:.2f}")
m3.metric("曝险实时市值", f"¥{mkt_val_total:,.0f}")
m4.metric("曝险比例", f"{int(mkt_val_total/total_assets*100)}%")

st.markdown("---")
st.subheader("📊 杠杆与现金分布")
p1, p2, p3, p4 = st.columns(4)
p1.write(f"🟢 **一倍资产**\n\n**{(lev_sums[1.0]/total_assets*100):.2f}%**")
p2.write(f"🟡 **二倍资产**\n\n**{(lev_sums[2.0]/total_assets*100):.2f}%**")
p3.write(f"🔴 **三倍资产**\n\n**{(lev_sums[3.0]/total_assets*100):.2f}%**")
p4.write(f"💰 **现金部位**\n\n**{(cash_val/total_assets*100):.2f}%**")

st.markdown("---")
st.subheader("📋 持仓详情明细")
df_list = []
for t, h in holdings_map.items():
    v_cny = live_prices[t] * h['qty'] * final_fx[h['cur']]
    df_list.append({
        "名称": h['name'], "代码": t, "持仓": f"{int(h['qty']):,}",
        "实时单价": f"{live_prices[t]:.3f}", "市值(CNY)": f"{v_cny:,.0f}",
        "资产占比": f"{(v_cny/total_assets*100):.2f}%", "杠杆倍数": f"{h['lev']}x"
    })
st.table(pd.DataFrame(df_list))

# 调仓助手
st.markdown("---")
st.subheader("🎯 调仓助手")
t_col1, t_col2 = st.columns(2)
with t_col1:
    target_b = st.slider("设定理想 Beta 目标", 0.0, 1.5, 0.9, 0.01)
with t_col2:
    ticker_options = {f"{v['name']} ({k})": k for k, v in holdings_map.items()}
    selected_label = st.selectbox("选择调仓标的", list(ticker_options.keys()), index=3)
    selected_ticker = ticker_options[selected_label]

h_info = holdings_map[selected_ticker]
price_cny_adj = live_prices[selected_ticker] * final_fx[h_info['cur']]

if price_cny_adj > 0:
    gap_beta = target_b - curr_beta
    needed_cny = gap_beta * total_assets / h_info['lev']
    shares = round(needed_cny / price_cny_adj)
    if shares != 0:
        action = "买入" if shares > 0 else "卖出"
        st.markdown(f"### 📢 建议指令：{action} **{abs(shares):,}** 股 {selected_label}")
        st.markdown(f"#### 预估金额: <span style='color:#ff4b4b'>¥{abs(shares * price_cny_adj):,.0f} CNY</span>", unsafe_allow_html=True)

# 底部更新时间适配北京时间
st.caption(f"🛡️ 终端状态：持久化激活 | 北京时间更新：{bj_now.strftime('%H:%M:%S')}")
