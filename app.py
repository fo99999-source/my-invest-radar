import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import time

# 1. 页面基础配置
st.set_page_config(page_title="Beta Radar", page_icon="📈", layout="wide")

st.title("🛡️ 纳指 100 资产监控终端")

# ==========================================
# 2. 侧边栏：初始数据录入
# ==========================================
with st.sidebar:
    st.header("⚙️ 持仓配置")
    c124 = st.number_input("513100.SS 数量", value=1242800)
    c216 = st.number_input("513300.SS 数量", value=21600)
    c320 = st.number_input("2834.HK 数量", value=320)
    c274 = st.number_input("7266.HK 数量", value=27400)
    c_tqqq = st.number_input("TQQQ 数量", value=0)
    st.markdown("---")
    c_cash = st.number_input("现金储备 (CNY)", value=4900000.0, step=10000.0)
    st.info("💡 修改此处数字，中间仪表盘将实时刷新。")

# 资产配置定义
holdings_config = {
    "513100.SS": {"name": "纳指100ETF(A)", "qty": c124, "lev": 1.0, "cur": "CNY", "tx_code": "sh513100"},
    "513300.SS": {"name": "纳指ETF(A)",    "qty": c216, "lev": 1.0, "cur": "CNY", "tx_code": "sh513300"},
    "2834.HK":   {"name": "纳指ETF(港)",    "qty": c320, "lev": 1.0, "cur": "HKD", "tx_code": "hk02834"},
    "7266.HK":   {"name": "两倍纳指(港)",    "qty": c274, "lev": 2.0, "cur": "HKD", "tx_code": "hk07266"},
    "TQQQ":      {"name": "三倍纳指(美)",    "qty": c_tqqq, "lev": 3.0, "cur": "USD", "tx_code": "usTQQQ"}
}

# ==========================================
# 3. 核心数据抓取 (双源备份 + 汇率显式化)
# ==========================================
@st.cache_data(ttl=300)
def get_all_data(config):
    # 默认汇率兜底
    fx = {"USD": 7.24, "HKD": 0.93, "CNY": 1.0}
    prices = {}
    
    # A. 抓取汇率
    try:
        usd_data = yf.Ticker("USDCNY=X").fast_info
        hkd_data = yf.Ticker("HKDCNY=X").fast_info
        if usd_data.get('last_price'): fx["USD"] = usd_data['last_price']
        if hkd_data.get('last_price'): fx["HKD"] = hkd_data['last_price']
    except:
        pass # 失败则沿用默认值

    # B. 抓取股价
    for ticker, info in config.items():
        success = False
        # 优先尝试 yfinance
        try:
            p = yf.Ticker(ticker).fast_info.get('last_price', 0)
            if p > 0:
                prices[ticker] = p
                success = True
        except: pass
        
        # 失败则尝试国内接口
        if not success:
            try:
                resp = requests.get(f"http://qt.gtimg.cn/q={info['tx_code']}", timeout=3)
                data = resp.text.split('~')
                if len(data) > 3:
                    prices[ticker] = float(data[3])
                    success = True
            except: pass
        
        if not success: prices[ticker] = 1.0 # 极值兜底

    return fx, prices

fx, prices = get_all_data(holdings_config)

# ==========================================
# 4. 计算逻辑
# ==========================================
total_mkt_val = sum(prices[t] * h['qty'] * fx[h['cur']] for t, h in holdings_config.items())
total_assets = total_mkt_val + c_cash
current_beta = sum(prices[t] * h['qty'] * fx[h['cur']] * h['lev'] for t, h in holdings_config.items()) / total_assets if total_assets > 0 else 0

# ==========================================
# 5. UI 渲染
# ==========================================
# 顶部实时汇率条
st.write(f"💱 **当前参考汇率**: 1 USD = {fx['USD']:.4f} CNY | 1 HKD = {fx['HKD']:.4f} CNY")

# 核心指标卡片
m1, m2, m3 = st.columns(3)
m1.metric("总资产值 (CNY)", f"¥{total_assets:,.2f}")
m2.metric("实时总 Beta", f"{current_beta:.2f}")
m3.metric("现金占比", f"{(c_cash/total_assets*100):.2f}%")

st.subheader("📋 持仓明细")
display_df = []
for t, h in holdings_config.items():
    val_cny = prices[t] * h['qty'] * fx[h['cur']]
    display_df.append({
        "名称": h['name'], "代码": t, "数量": f"{h['qty']:,}",
        "价格": f"{prices[t]:.3f}", "市值(CNY)": f"{val_cny:,.0f}",
        "占比": f"{(val_cny/total_assets*100):.2f}%", "杠杆": f"{h['lev']}x"
    })
st.table(pd.DataFrame(display_df))

# 调仓助手部分
st.markdown("---")
st.subheader("🎯 调仓助手")
col1, col2 = st.columns(2)

with col1:
    target_b = st.slider("设定理想目标 Beta", 0.0, 1.5, 0.9, 0.01)

with col2:
    # 修复：提供可选标的下拉菜单
    option_names = [h['name'] for h in holdings_config.values()]
    selected_name = st.selectbox("选择用于调整的标的", option_names, index=3) # 默认选 7266

# 寻找所选名称对应的代码
adj_ticker = next(k for k, v in holdings_config.items() if v['name'] == selected_name)
t_info = holdings_config[adj_ticker]
t_p_cny = prices[adj_ticker] * fx[t_info['cur']]

# 计算差额
if t_p_cny > 0:
    gap_val = (target_b - current_beta) * total_assets
    shares_needed = round(gap_val / (t_info['lev'] * t_p_cny))
    cost_orig = abs(shares_needed * prices[adj_ticker])
    
    if shares_needed != 0:
        action = "买入" if shares_needed > 0 else "卖出"
        st.warning(f"### 建议操作: {action} {abs(shares_needed):,} 股 {t_info['name']}")
        st.write(f"**成交金额**: {cost_orig:,.2f} {t_info['cur']} (约 {abs(shares_needed)*t_p_cny:,.0f} CNY)")
    else:
        st.success("✅ 当前组合已符合目标 Beta，无需操作。")

st.caption(f"数据更新时间: {time.strftime('%Y-%m-%d %H:%M:%S')} (每5分钟自动刷新)")
