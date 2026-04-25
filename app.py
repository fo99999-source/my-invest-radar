import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import json
import os
import time
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone

# 1. 配置文件路径
DB_FILE = "portfolio_data.json"

# 2. 页面配置
st.set_page_config(page_title="Beta Radar Pro", page_icon="🛡️", layout="wide")

# ==========================================
# 3. 工具函数
# ==========================================
def get_beijing_time():
    tz_utc_8 = timezone(timedelta(hours=8))
    return datetime.now(tz_utc_8)

def load_data():
    default = {
        "holdings": {"c124": 1174300, "c216": 21600, "c320": 600, "c274": 77600, "c_tqqq": 0, "c_cash": 3250000},
        "fx": {"USD": 7.24, "HKD": 0.92}
    }
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: return json.load(f)
        except: return default
    return default

def save_data(holdings, fx):
    with open(DB_FILE, "w") as f: json.dump({"holdings": holdings, "fx": fx}, f)

# ==========================================
# 4. 数据获取引擎 (修正优先级)
# ==========================================
@st.cache_data(ttl=60)
def get_live_market_data(config, manual_fx):
    # 基础 fallback 值
    fx = {"USD": manual_fx["USD"], "HKD": manual_fx["HKD"], "CNY": 1.0}
    status = {"USD": "手动保底", "HKD": "手动保底"}
    prices = {}
    header = {'Referer': 'http://finance.sina.com.cn'}
    
    # 强制尝试实时抓取 (不受本地存储值干扰)
    try:
        r_u = requests.get("http://hq.sinajs.cn/list=fx_susdcny", timeout=2, headers=header).text
        d_u = r_u.split('"')[1].split(',')
        if len(d_u) > 1 and float(d_u[1]) > 0: 
            fx["USD"] = float(d_u[1])
            status["USD"] = "实时"
        
        r_h = requests.get("http://hq.sinajs.cn/list=fx_shkdcny", timeout=2, headers=header).text
        d_h = r_h.split('"')[1].split(',')
        if len(d_h) > 1 and float(d_h[1]) > 0: 
            fx["HKD"] = float(d_h[1])
            status["HKD"] = "实时"
    except: pass 

    for ticker, info in config.items():
        p = 0.0
        if ticker.endswith(".SS"):
            try:
                code = ticker.replace(".SS", "").lower()
                resp = requests.get(f"http://hq.sinajs.cn/list=sh{code}", timeout=2, headers=header).text
                dt = resp.split('"')[1].split(',')
                if len(dt) > 3: p = float(dt[3])
            except: pass
        if p == 0:
            try:
                p = yf.Ticker(ticker).fast_info.get('last_price', 0.0)
                if p == 0: p = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
            except: p = 1.0
        prices[ticker] = p
    return fx, status, prices

# ==========================================
# 5. 初始化
# ==========================================
persisted = load_data()
if 'saved_data' not in st.session_state:
    st.session_state.saved_data = persisted["holdings"]
    st.session_state.manual_fx = persisted["fx"]

# ==========================================
# 6. 侧边栏 (分开确认逻辑)
# ==========================================
with st.sidebar:
    st.header("⚙️ 终端配置")
    
    # --- 模块 A: 持仓管理 ---
    with st.expander("📦 持仓数量管理", expanded=True):
        input_c124 = st.text_input("513100.SS", value=str(int(st.session_state.saved_data["c124"])))
        input_c216 = st.text_input("513300.SS", value=str(int(st.session_state.saved_data["c216"])))
        input_c320 = st.text_input("2834.HK", value=str(int(st.session_state.saved_data["c320"])))
        input_c274 = st.text_input("7266.HK", value=str(int(st.session_state.saved_data["c274"])))
        input_c_tqqq = st.text_input("TQQQ", value=str(int(st.session_state.saved_data["c_tqqq"])))
        input_c_cash = st.text_input("现金储备 (CNY)", value=str(int(st.session_state.saved_data["c_cash"])))
        
        if st.button("确认修改持仓", use_container_width=True):
            new_h = {
                "c124": int(float(input_c124)), "c216": int(float(input_c216)), 
                "c320": int(float(input_c320)), "c274": int(float(input_c274)), 
                "c_tqqq": int(float(input_c_tqqq)), "c_cash": int(float(input_c_cash))
            }
            save_data(new_h, st.session_state.manual_fx)
            st.session_state.saved_data = new_h
            st.success("持仓已保存")
            st.rerun()

    # --- 模块 B: 汇率管理 ---
    with st.expander("💱 汇率保底设置", expanded=False):
        st.caption("仅在实时抓取失败时作为保底使用")
        input_fx_usd = st.number_input("手动 USD/CNY", value=st.session_state.manual_fx["USD"], format="%.4f")
        input_fx_hkd = st.number_input("手动 HKD/CNY", value=st.session_state.manual_fx["HKD"], format="%.4f")
        
        if st.button("确认手动汇率", use_container_width=True):
            new_fx = {"USD": input_fx_usd, "HKD": input_fx_hkd}
            save_data(st.session_state.saved_data, new_fx)
            st.session_state.manual_fx = new_fx
            st.success("保底汇率已更新")
            st.rerun()

# ==========================================
# 7. 计算与展现 (保持原有回测与指标逻辑)
# ==========================================
holdings_map = {
    "513100.SS": {"name": "纳指100ETF(A)", "qty": st.session_state.saved_data["c124"], "lev": 1.0, "cur": "CNY"},
    "513300.SS": {"name": "纳指ETF(A)",    "qty": st.session_state.saved_data["c216"], "lev": 1.0, "cur": "CNY"},
    "2834.HK":   {"name": "纳指ETF(港)",    "qty": st.session_state.saved_data["c320"], "lev": 1.0, "cur": "HKD"},
    "7266.HK":   {"name": "两倍纳指(港)",    "qty": st.session_state.saved_data["c274"], "lev": 2.0, "cur": "HKD"},
    "TQQQ":      {"name": "三倍纳指(美)",    "qty": st.session_state.saved_data["c_tqqq"], "lev": 3.0, "cur": "USD"}
}

final_fx, fx_status, live_prices = get_live_market_data(holdings_map, st.session_state.manual_fx)

# 实时计算
lev_sums = {1.0: 0.0, 2.0: 0.0, 3.0: 0.0}
for t, h in holdings_map.items():
    val_cny = live_prices[t] * h['qty'] * final_fx[h['cur']]
    lev_sums[h['lev']] += val_cny

mkt_val_total = sum(lev_sums.values())
cash_val = int(st.session_state.saved_data["c_cash"])
total_assets = mkt_val_total + cash_val
curr_beta = sum(live_prices[t] * h['qty'] * final_fx[h['cur']] * h['lev'] for t, h in holdings_map.items()) / total_assets if total_assets > 0 else 0

# UI 部分
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

# 指标看板
m1, m2, m3, m4 = st.columns(4)
m1.metric("总资产 (CNY)", f"¥{total_assets:,.0f}")
m2.metric("当前实时 Beta", f"{curr_beta:.2f}")
m3.metric("曝险实时市值", f"¥{mkt_val_total:,.0f}")
m4.metric("曝险比例", f"{int(mkt_val_total/total_assets*100)}%")

# 比例监控
st.markdown("### 📊 资产分布比例")
d1, d2, d3, d4 = st.columns(4)
p1 = (lev_sums[1.0] / total_assets * 100) if total_assets > 0 else 0
p2 = (lev_sums[2.0] / total_assets * 100) if total_assets > 0 else 0
p3 = (lev_sums[3.0] / total_assets * 100) if total_assets > 0 else 0
p_cash = (cash_val / total_assets * 100) if total_assets > 0 else 0
d1.metric("一倍资产占比", f"{p1:.1f}%")
d2.metric("二倍资产占比", f"{p2:.1f}%")
d3.metric("三倍资产占比", f"{p3:.1f}%")
d4.metric("现金储备占比", f"{p_cash:.1f}%")

# 回测波动图
st.markdown("---")
st.subheader("📈 资产历史波动回测 (2025-01-01 至今)")
@st.cache_data(ttl=3600)
def get_backtest_data(holdings):
    start_date = "2025-01-01"
    tk_list = ["513100.SS", "513300.SS", "2834.HK", "7266.HK", "TQQQ", "USDCNY=X", "HKDCNY=X"]
    hist = yf.download(tk_list, start=start_date)['Close'].ffill()
    def calc_assets(row):
        total = holdings["c_cash"]
        total += row["513100.SS"] * holdings["c124"]
        total += row["513300.SS"] * holdings["c216"]
        total += row["2834.HK"] * holdings["c320"] * row["HKDCNY=X"]
        total += row["7266.HK"] * holdings["c274"] * row["HKDCNY=X"]
        total += row["TQQQ"] * holdings["c_tqqq"] * row["USDCNY=X"]
        return total
    return hist.apply(calc_assets, axis=1)

try:
    history_series = get_backtest_data(st.session_state.saved_data)
    h_max, h_min = history_series.max(), history_series.min()
    d_max, d_min = history_series.idxmax(), history_series.idxmin()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=history_series.index, y=history_series, name="总资产", line=dict(color='#FF69B4', width=2)))
    fig.add_annotation(x=d_max, y=h_max, text=f"最高: ¥{h_max:,.0f}<br>{d_max.strftime('%Y-%m-%d')}", showarrow=True, arrowhead=1, yshift=10)
    fig.add_annotation(x=d_min, y=h_min, text=f"最低: ¥{h_min:,.0f}<br>{d_min.strftime('%Y-%m-%d')}", showarrow=True, arrowhead=1, yshift=-10)
    fig.update_layout(template="plotly_dark", height=400, margin=dict(l=10, r=10, t=10, b=10), hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
except:
    st.warning("回测数据加载中...")

# 持仓明细表
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

# 调仓助手 (Beta 目标调优)
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
p_cny_adj = live_prices[selected_ticker] * final_fx[h_info['cur']]
if p_cny_adj > 0:
    gap = target_b - curr_beta
    needed = gap * total_assets / h_info['lev']
    shares = round(needed / p_cny_adj)
    if shares != 0:
        st.markdown(f"### 📢 建议指令：{'买入' if shares > 0 else '卖出'} **{abs(shares):,}** 股 {selected_label}")
        st.markdown(f"#### 预估金额: <span style='color:#ff4b4b'>¥{abs(shares * p_cny_adj):,.0f} CNY</span>", unsafe_allow_html=True)

st.caption(f"🛡️ 终端状态：持久化激活 | 北京时间更新：{bj_now.strftime('%H:%M:%S')}")
