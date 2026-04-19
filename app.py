import streamlit as st
import yfinance as yf
import pandas as pd
import time

# 页面配置
st.set_page_config(page_title="Beta 投资雷达", layout="wide")

st.title("🛡️ 纳指 100 资产配置与实时 Beta 监控")
st.markdown("---")

# ==========================================
# 1. 侧边栏：手动数据录入
# ==========================================
st.sidebar.header("📊 初始持仓设置")
c124 = st.sidebar.number_input("513100.SS 数量", value=1242800)
c216 = st.sidebar.number_input("513300.SS 数量", value=21600)
c320 = st.sidebar.number_input("2834.HK 数量", value=320)
c274 = st.sidebar.number_input("7266.HK 数量", value=27400)
c_tqqq = st.sidebar.number_input("TQQQ 数量", value=0)
c_cash = st.sidebar.number_input("现金部位 (CNY)", value=4900000.0)

# 初始化持仓字典
holdings = {
    "513100.SS": {"name": "纳指100ETF(A)", "qty": c124, "lev": 1.0, "cur": "CNY"},
    "513300.SS": {"name": "纳指ETF(A)",    "qty": c216, "lev": 1.0, "cur": "CNY"},
    "2834.HK":   {"name": "纳指ETF(港)",    "qty": c320, "lev": 1.0, "cur": "HKD"},
    "7266.HK":   {"name": "两倍纳指(港)",    "qty": c274, "lev": 2.0, "cur": "HKD"},
    "TQQQ":      {"name": "三倍纳指(美)",    "qty": c_tqqq, "lev": 3.0, "cur": "USD"}
}

# ==========================================
# 2. 核心计算逻辑 (带防封锁处理)
# ==========================================
@st.cache_data(ttl=300)  # 5分钟缓存，减少请求压力
def fetch_data(holdings_keys):
    fx = {"USD": 7.24, "HKD": 0.93, "CNY": 1.0}
    prices = {}
    
    try:
        # 1. 抓取汇率
        usd_data = yf.Ticker("USDCNY=X").fast_info
        hkd_data = yf.Ticker("HKDCNY=X").fast_info
        fx["USD"] = usd_data.get('last_price', 7.24)
        fx["HKD"] = hkd_data.get('last_price', 0.93)
        time.sleep(1) # 停顿一下
        
        # 2. 逐个抓取价格
        for t in holdings_keys:
            stock = yf.Ticker(t)
            p = stock.fast_info.get('last_price', 0.0)
            # 如果抓不到价格（比如收盘或限流），尝试用常规方法
            if p == 0.0:
                p = stock.history(period="1d")['Close'].iloc[-1]
            prices[t] = p
            time.sleep(1) # 强制停顿1秒，防止被雅虎识别为爬虫攻击
            
    except Exception as e:
        st.error(f"⚠️ 数据源请求受限 (YF Rate Limit)。请稍后再刷新网页，或尝试更换网络/VPN。")
        # 兜底：如果全部抓取失败，给一个 1.0 防止计算报错
        for t in holdings_keys:
            if t not in prices: prices[t] = 1.0
            
    return fx, prices

# 执行抓取
fx, prices = fetch_data(list(holdings.keys()))

# ==========================================
# 3. 资产计算
# ==========================================
total_market_value = sum(prices[t] * h['qty'] * fx[h['cur']] for t, h in holdings.items())
total_assets = total_market_value + c_cash
if total_assets > 0:
    weighted_beta = sum(prices[t] * h['qty'] * fx[h['cur']] * h['lev'] for t, h in holdings.items()) / total_assets
else:
    weighted_beta = 0

# ==========================================
# 4. 界面展示
# ==========================================
col_a, col_b, col_c = st.columns(3)
col_a.metric("总资产值 (CNY)", f"¥{total_assets:,.2f}")
col_b.metric("实时总 Beta", f"{weighted_beta:.2f}")
col_c.metric("现金占比", f"{(c_cash/total_assets*100):.2f}%" if total_assets > 0 else "0%")

st.subheader("📋 实时持仓明细")
data_list = []
lev_groups = {1.0: 0.0, 2.0: 0.0, 3.0: 0.0}

for t, h in holdings.items():
    val_cny = prices[t] * h['qty'] * fx[h['cur']]
    lev_groups[h['lev']] += val_cny
    data_list.append({
        "标的": h['name'],
        "代码": t,
        "数量": h['qty'], 
        "单价": f"{prices[t]:.3f}",
        "市值(CNY)": f"{val_cny:,.2f}",
        "占比": f"{(val_cny/total_assets*100):.2f}%" if total_assets > 0 else "0%",
        "杠杆": h['lev']
    })

st.table(pd.DataFrame(data_list))

# 汇总比例展示
st.info(f"""
**资产分布汇总**:
- 1倍标的占比: {(lev_groups[1.0]/total_assets*100):.2f}% | 
- 2倍标的占比: {(lev_groups[2.0]/total_assets*100):.2f}% | 
- 3倍标的占比: {(lev_groups[3.0]/total_assets*100):.2f}% | 
- 现金部位占比: {(c_cash/total_assets*100):.2f}%
""")

# ==========================================
# 5. 交互区：调仓模拟
# ==========================================
st.markdown("---")
st.subheader("🎯 调仓助手")
col1, col2 = st.columns(2)
with col1:
    target_beta = st.slider("设定理想目标 Beta", 0.0, 2.0, 0.9, 0.01)
with col2:
    # 自动识别代码前缀，方便选择
    choice_map = {h['name']: t for t, h in holdings.items()}
    selected_name = st.selectbox("选择调整标的", list(choice_map.keys()))
    adj_code = choice_map[selected_name]

# 模拟调仓计算
t_info = holdings[adj_code]
p_orig = prices[adj_code]
currency = t_info['cur']

if p_orig > 0:
    gap = (target_beta - weighted_beta) * total_assets
    qty_change = round(gap / (t_info['lev'] * p_orig * fx[currency]))
    total_cost_orig = abs(qty_change * p_orig)
    total_cost_cny = abs(qty_change * p_orig * fx[currency])

    if qty_change != 0:
        st.success(f"### 📢 建议指令: {'买入' if qty_change > 0 else '卖出'} {abs(qty_change):,} 股 {t_info['name']}")
        st.write(f"**成交预计**: {total_cost_orig:,.2f} {currency} (约 {total_cost_cny:,.2f} CNY)")
    else:
        st.write("✅ 当前 Beta 已符合目标，无需调仓。")
else:
    st.warning("价格获取失败，无法计算调仓建议。")
