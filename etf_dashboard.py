import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# ----------------------------------------------------------------------
# 페이지 기본 설정
# ----------------------------------------------------------------------
st.set_page_config(page_title="ETF Market Monitoring (v7.0)", layout="wide")
st.title("📊 ETF Market Monitoring Dashboard (통합판)")

# ----------------------------------------------------------------------
# 데이터 로드 및 전처리 (캐싱 처리 및 속도 최적화)
# ----------------------------------------------------------------------
@st.cache_data
def load_data():
    csv_file_id = "14q4_DyFiyNqm9HrIwvCTnRNIfzM2Y1BY"
    excel_file_id = "1gHKN8CcXch1s3L-O8XOac98uh2c8Lq4N"

    csv_url = f"https://drive.google.com/uc?export=download&id={csv_file_id}"
    excel_url = f"https://docs.google.com/spreadsheets/d/{excel_file_id}/export?format=xlsx"

    # 1. 엑셀 마스터 파일 로드
    try:
        df_excel = pd.read_excel(excel_url)
    except Exception as e:
        st.error(f"구글 드라이브에서 엑셀 마스터 파일을 불러오는 중 오류가 발생했습니다: {e}")
        return pd.DataFrame(), {}

    master_db = {}
    for _, row in df_excel.iterrows():
        std_code = str(row.iloc[0]).strip().upper().replace(" ", "")
        if pd.isna(std_code) or std_code == 'NAN': continue

        raw_short = str(row.iloc[1]).strip().upper().replace(" ", "")
        if (not raw_short or raw_short == 'NAN') and len(std_code) >= 9:
            raw_short = std_code[3:9]
        a_code = "A" + raw_short if not raw_short.startswith("A") else raw_short

        name = str(row.iloc[3])
        if pd.isna(name) or name == 'nan': name = str(row.iloc[2])
        if pd.isna(name) or name == 'nan': name = str(row.iloc[1])

        market = "국내" if str(row.iloc[10]).replace(" ", "") == "국내" else "해외"
        asset = "주식" if str(row.iloc[11]).replace(" ", "") == "주식" else "그외"

        base_index = str(row.iloc[6]).upper().replace(" ", "")
        rep_keys = ["코스피200", "코스닥150", "S&P500", "나스닥100", "NASDAQ100"]
        is_rep = "대표지수" if any(k in base_index for k in rep_keys) else "그외"

        deriv = "일반" if str(row.iloc[8]).replace(" ", "") == "일반" else "파생"
        tracking = "패시브" if str(row.iloc[9]).replace(" ", "") in ["실물(패시브)", "합성(패시브)"] else "액티브"

        amc_raw = str(row.iloc[13]).replace(" ", "")
        amc = amc_raw if amc_raw and amc_raw != 'nan' else "기타운용사"
        cat_key = f"{market} | {asset} | {is_rep} | {deriv} | {tracking}"

        master_db[std_code] = {
            'a_code': a_code, 'name': name, 'market': market, 'asset': asset,
            'is_rep': is_rep, 'deriv': deriv, 'tracking': tracking, 'category_key': cat_key, 'amc': amc
        }

    # 2. CSV 실적 파일 로드 
    try:
        df = pd.read_csv(csv_url, encoding='cp949', thousands=',')
    except Exception as e:
        st.error(f"구글 드라이브에서 CSV 실적 파일을 불러오는 중 오류가 발생했습니다: {e}")
        return pd.DataFrame(), {}

    df = df[df['상품그룹ID'].str.upper() == 'ETF'].copy()

    # 일자 파싱 및 거래대금/수량 산출
    df['거래일자'] = pd.to_datetime(df['거래일자'].astype(str), format='%Y%m%d')
    df['LP매도거래대금'] = df['LP매도거래대금'].fillna(0)
    df['LP매수거래대금'] = df['LP매수거래대금'].fillna(0)
    
    if 'LP매도거래량' in df.columns: df['LP매도거래량'] = df['LP매도거래량'].fillna(0)
    if 'LP매수거래량' in df.columns: df['LP매수거래량'] = df['LP매수거래량'].fillna(0)

    df['총LP거래대금'] = df['LP매도거래대금'] + df['LP매수거래대금']
    df['LP순매수대금'] = df['LP매수거래대금'] - df['LP매도거래대금']

    # 3. 마스터 DB 고속 맵핑
    master_df = pd.DataFrame.from_dict(master_db, orient='index')

    df['종목코드'] = df['종목코드'].str.strip().str.upper().str.replace(' ', '')
    df['a_code'] = df['종목코드'].map(master_df['a_code']).fillna(df['종목코드'])

    master_names = df['종목코드'].map(master_df['name'])
    df['종목명'] = np.where(master_names.isna() | (master_names == ''), df['종목명'], master_names)

    categories = ['market', 'asset', 'is_rep', 'deriv', 'tracking', 'amc', 'category_key']
    for cat in categories:
        df[cat] = df['종목코드'].map(master_df[cat]).fillna('미분류')

    return df, master_db

df, master_db = load_data()
if df.empty:
    st.stop()

# ----------------------------------------------------------------------
# 사이드바 (Global Date Filter)
# ----------------------------------------------------------------------
st.sidebar.header("🗓️ 데이터 기간 설정")
min_date = df['거래일자'].min().date()
max_date = df['거래일자'].max().date()

date_selection = st.sidebar.date_input(
    "조회 기간을 선택하세요", 
    [min_date, max_date],
    min_value=min_date,
    max_value=max_date
)

if len(date_selection) == 2:
    start_date, end_date = date_selection
else:
    start_date = end_date = date_selection[0]

df_filtered = df[(df['거래일자'].dt.date >= start_date) & (df['거래일자'].dt.date <= end_date)].copy()

# ----------------------------------------------------------------------
# UI Tabs 구성 (통합 및 재정렬)
# ----------------------------------------------------------------------
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "1. 종합 대시보드", "2. ETF 구분별 분석", "3. LP사 다각도 분석", 
    "4. ETF별 주력 LP 분석", "5. 운용사별 주력 ETF 분석",
    "6. 종목 집중도 분석"
])

# ==========================================
# Tab 1: 종합 대시보드 (KPI + Bar 차트 + Time Series 통합)
# ==========================================
with tab1:
    st.subheader("📊 시장 핵심 지표 및 추이 (KPI)")

    # 1. 공통 필터 (드롭다운 5개)
    c1, c2, c3, c4, c5 = st.columns(5)
    mkt_filter_t1 = c1.selectbox("국내/해외", ["전체"] + list(df_filtered['market'].unique()), key='t1_mkt')
    ast_filter_t1 = c2.selectbox("주식/그외", ["전체"] + list(df_filtered['asset'].unique()), key='t1_ast')
    rep_filter_t1 = c3.selectbox("대표지수", ["전체"] + list(df_filtered['is_rep'].unique()), key='t1_rep')
    drv_filter_t1 = c4.selectbox("일반/파생", ["전체"] + list(df_filtered['deriv'].unique()), key='t1_drv')
    trk_filter_t1 = c5.selectbox("패시브/액티브", ["전체"] + list(df_filtered['tracking'].unique()), key='t1_trk')

    # 필터 적용
    df_t1 = df_filtered.copy()
    if mkt_filter_t1 != "전체": df_t1 = df_t1[df_t1['market'] == mkt_filter_t1]
    if ast_filter_t1 != "전체": df_t1 = df_t1[df_t1['asset'] == ast_filter_t1]
    if rep_filter_t1 != "전체": df_t1 = df_t1[df_t1['is_rep'] == rep_filter_t1]
    if drv_filter_t1 != "전체": df_t1 = df_t1[df_t1['deriv'] == drv_filter_t1]
    if trk_filter_t1 != "전체": df_t1 = df_t1[df_t1['tracking'] == trk_filter_t1]

    # KPI 지표 계산
    total_amt = df_t1['총LP거래대금'].sum() / 100_000_000
    unique_days = df_t1['거래일자'].nunique()
    daily_avg = total_amt / unique_days if unique_days > 0 else 0
    active_etf_cnt = df_t1[df_t1['총LP거래대금'] > 0]['종목코드'].nunique()
    active_lp_cnt = df_t1[df_t1['총LP거래대금'] > 0]['회원사명'].nunique()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("기간 총 거래대금", f"{total_amt:,.0f} 억원")
    col2.metric("일평균 거래대금", f"{daily_avg:,.0f} 억원")
    col3.metric("유효 거래 종목 수", f"{active_etf_cnt:,} 개")
    col4.metric("활동 LP 회원사 수", f"{active_lp_cnt:,} 사")
    st.divider()

    # LP사별 총 거래대금 바 차트
    lp_total = df_t1.groupby('회원사명')['총LP거래대금'].sum().sort_values(ascending=False) / 100_000_000
    lp_total = lp_total[lp_total > 0]

    if not lp_total.empty:
        fig = px.bar(
            lp_total, x=lp_total.index, y=lp_total.values, 
            title="필터 적용 LP사별 총 거래대금 (억원)",
            labels={'y': '거래대금(억)', '회원사명': '증권사'},
            color_discrete_sequence=['#4A90E2']
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("선택하신 필터 조건에 해당하는 데이터가 없습니다.")

    st.divider()

    # 시계열 거래대금 추이 차트
    st.subheader("📉 시계열(Time-Series) 일별 거래대금 추이")

    trend_type = st.radio("추이 분석 관점 선택", ["시장 전체 (Total Market)", "특정 LP사 (Specific LP)", "특정 운용사 (Specific AMC)"], horizontal=True, key='t1_trend')

    if trend_type == "시장 전체 (Total Market)":
        daily_vol = df_t1.groupby('거래일자')['총LP거래대금'].sum().reset_index()
        daily_vol['거래대금(억)'] = daily_vol['총LP거래대금'] / 100_000_000
        fig_t = px.line(daily_vol, x='거래일자', y='거래대금(억)', title="전체 시장 일별 LP 거래대금 추이", markers=True)
        st.plotly_chart(fig_t, use_container_width=True)

    elif trend_type == "특정 LP사 (Specific LP)":
        target_lps = st.multiselect("비교할 LP사 선택 (다중 선택 가능)", sorted(df_t1['회원사명'].unique()), key='t1_lp_sel')
        if target_lps:
            daily_vol = df_t1[df_t1['회원사명'].isin(target_lps)].groupby(['거래일자', '회원사명'])['총LP거래대금'].sum().reset_index()
            daily_vol['거래대금(억)'] = daily_vol['총LP거래대금'] / 100_000_000
            fig_t = px.line(daily_vol, x='거래일자', y='거래대금(억)', color='회원사명', title="선택 LP사별 일별 거래대금 추이", markers=True)
            st.plotly_chart(fig_t, use_container_width=True)

    elif trend_type == "특정 운용사 (Specific AMC)":
        target_amcs = st.multiselect("비교할 운용사 선택 (다중 선택 가능)", sorted([a for a in df_t1['amc'].unique() if a != '미분류']), key='t1_amc_sel')
        if target_amcs:
            daily_vol = df_t1[df_t1['amc'].isin(target_amcs)].groupby(['거래일자', 'amc'])['총LP거래대금'].sum().reset_index()
            daily_vol['거래대금(억)'] = daily_vol['총LP거래대금'] / 100_000_000
            fig_t = px.line(daily_vol, x='거래일자', y='거래대금(억)', color='amc', title="선택 운용사별 일별 거래대금 추이", markers=True)
            st.plotly_chart(fig_t, use_container_width=True)

# ==========================================
# Tab 2: ETF 구분별 분석 (점유율 + 매수/매도 현황 병합)
# ==========================================
with tab2:
    st.subheader("📈 ETF 섹터 필터링을 통한 점유율 및 성향 분석")

    # 1. 공통 필터 (드롭다운 5개)
    c1, c2, c3, c4, c5 = st.columns(5)
    mkt_filter_t2 = c1.selectbox("국내/해외", ["전체"] + list(df_filtered['market'].unique()), key='t2_mkt')
    ast_filter_t2 = c2.selectbox("주식/그외", ["전체"] + list(df_filtered['asset'].unique()), key='t2_ast')
    rep_filter_t2 = c3.selectbox("대표지수", ["전체"] + list(df_filtered['is_rep'].unique()), key='t2_rep')
    drv_filter_t2 = c4.selectbox("일반/파생", ["전체"] + list(df_filtered['deriv'].unique()), key='t2_drv')
    trk_filter_t2 = c5.selectbox("패시브/액티브", ["전체"] + list(df_filtered['tracking'].unique()), key='t2_trk')

    # 필터 적용
    df_t2 = df_filtered.copy()
    if mkt_filter_t2 != "전체": df_t2 = df_t2[df_t2['market'] == mkt_filter_t2]
    if ast_filter_t2 != "전체": df_t2 = df_t2[df_t2['asset'] == ast_filter_t2]
    if rep_filter_t2 != "전체": df_t2 = df_t2[df_t2['is_rep'] == rep_filter_t2]
    if drv_filter_t2 != "전체": df_t2 = df_t2[df_t2['deriv'] == drv_filter_t2]
    if trk_filter_t2 != "전체": df_t2 = df_t2[df_t2['tracking'] == trk_filter_t2]

    # 2. 종목별 집계 (추정매매손익 사전 계산용)
    t2_etf = df_t2.groupby(['회원사명', '종목명'])[['총LP거래대금', 'LP매도거래대금', 'LP매수거래대금', 'LP순매수대금', 'LP매도거래량', 'LP매수거래량']].sum().reset_index()
    t2_etf['평균매도단가'] = np.where(t2_etf['LP매도거래량'] > 0, t2_etf['LP매도거래대금'] / t2_etf['LP매도거래량'], 0)
    t2_etf['평균매수단가'] = np.where(t2_etf['LP매수거래량'] > 0, t2_etf['LP매수거래대금'] / t2_etf['LP매수거래량'], 0)
    t2_etf['체결수량(min)'] = t2_etf[['LP매도거래량', 'LP매수거래량']].min(axis=1)
    t2_etf['추정매매이익'] = (t2_etf['평균매도단가'] - t2_etf['평균매수단가']) * t2_etf['체결수량(min)']

    # 3. 회원사 단위 재집계 (점유율 및 성향 분석용 통합 데이터)
    agg_df = t2_etf.groupby('회원사명')[['총LP거래대금', 'LP매도거래대금', 'LP매수거래대금', 'LP순매수대금', '추정매매이익']].sum().reset_index()
    agg_df = agg_df[agg_df['총LP거래대금'] > 0].sort_values('총LP거래대금', ascending=False)
    
    total_vol = agg_df['총LP거래대금'].sum()
    agg_df['점유율(%)'] = (agg_df['총LP거래대금'] / total_vol) * 100 if total_vol > 0 else 0
    agg_df['거래대금(억)'] = agg_df['총LP거래대금'] / 100_000_000
    agg_df['추정매매손익(백만)'] = agg_df['추정매매이익'] / 1_000_000

    # --- (1) 시장 점유율 테이블 & 차트 ---
    st.write("### 1️⃣ 타겟 섹터 회원사 점유율")
    col1, col2 = st.columns([1, 1])
    with col1:
        show_df = agg_df[['회원사명', '거래대금(억)', '추정매매손익(백만)', '점유율(%)']].copy()
        show_df['순위'] = range(1, len(show_df) + 1)
        st.dataframe(show_df.set_index('순위').style.format({
            '거래대금(억)': '{:,.0f}', '추정매매손익(백만)': '{:,.0f}', '점유율(%)': '{:.1f}%'
        }), use_container_width=True)

    with col2:
        if not agg_df.empty:
            fig2 = px.pie(agg_df.head(10), values='거래대금(억)', names='회원사명', hole=0.4)
            st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # --- (2) 매수/매도 성향 차트 & 테이블 ---
    st.write("### 2️⃣ LP사 매수/매도 스탠스 (순매수 현황)")
    imb_df = agg_df.copy()
    imb_df['순매수비율(%)'] = np.where(imb_df['총LP거래대금'] > 0, (imb_df['LP순매수대금'] / imb_df['총LP거래대금']) * 100, 0)
    imb_df = imb_df.sort_values('LP순매수대금', ascending=False)

    fig_imb = px.bar(
        imb_df, x='회원사명', y='LP순매수대금',
        title="필터링된 섹터 내 순매수/순매도 누적대금",
        labels={'LP순매수대금': '순매수대금(원)', '회원사명': '증권사'},
        color='LP순매수대금', color_continuous_scale=px.colors.diverging.RdBu_r,
        text=imb_df['LP순매수대금'] / 100_000_000
    )
    fig_imb.update_traces(texttemplate='%{text:,.0f}억', textposition='outside')
    st.plotly_chart(fig_imb, use_container_width=True)

    st.write("▼ 세부 금액 데이터")
    imb_df['매도대금(억)'] = imb_df['LP매도거래대금'] / 100_000_000
    imb_df['매수대금(억)'] = imb_df['LP매수거래대금'] / 100_000_000
    imb_df['순매수대금(억)'] = imb_df['LP순매수대금'] / 100_000_000
    
    st.dataframe(
        imb_df[['회원사명', '매도대금(억)', '매수대금(억)', '순매수대금(억)', '거래대금(억)', '순매수비율(%)']].style.format({
            '매도대금(억)': '{:,.0f}', '매수대금(억)': '{:,.0f}', 
            '순매수대금(억)': '{:,.0f}', '거래대금(억)': '{:,.0f}', '순매수비율(%)': '{:.2f}%'
        }), use_container_width=True, hide_index=True
    )

# ==========================================
# Tab 3: LP사 다각도 분석
# ==========================================
with tab3:
    lp_list = df_filtered.groupby('회원사명')['총LP거래대금'].sum().sort_values(ascending=False).index.tolist()
    target_lp = st.selectbox("📌 분석 대상 LP사 선택", lp_list)

    if target_lp:
        df_lp = df_filtered[df_filtered['회원사명'] == target_lp]
        lp_total_amt = df_lp['총LP거래대금'].sum()
        sys_total_amt = df_filtered['총LP거래대금'].sum()
        ms = (lp_total_amt / sys_total_amt) * 100 if sys_total_amt > 0 else 0

        st.info(f"**{target_lp}** | 해당 기간 LP 총 거래대금: {lp_total_amt/100_000_000:,.0f} 억원 | 전체 시장 점유율(M/S): {ms:.2f}%")

        c1, c2 = st.columns(2)
        with c1:
            st.write("1️⃣ 섹터별 상세 거래 내역 (5단계 분류)")
            market_sector = df_filtered.groupby('category_key')['총LP거래대금'].sum()
            lp_sector = df_lp.groupby('category_key')['총LP거래대금'].sum().reset_index()
            lp_sector['내부비중(%)'] = (lp_sector['총LP거래대금'] / lp_total_amt) * 100
            lp_sector['섹터내_MS(%)'] = lp_sector.apply(lambda r: (r['총LP거래대금'] / market_sector.get(r['category_key'], 1)) * 100, axis=1)
            lp_sector['대금(억)'] = lp_sector['총LP거래대금'] / 100_000_000
            st.dataframe(
                lp_sector[lp_sector['총LP거래대금'] > 0].sort_values('총LP거래대금', ascending=False)
                [['category_key', '대금(억)', '내부비중(%)', '섹터내_MS(%)']].style.format({'대금(억)': '{:,.0f}', '내부비중(%)': '{:.1f}%', '섹터내_MS(%)': '{:.1f}%'}), 
                use_container_width=True, hide_index=True
            )

        with c2:
            st.write("2️⃣ 운용사(AMC)별 커버리지 및 충성도 (섹터 필터링)")
            
            f1, f2, f3 = st.columns(3)
            mkt_filter_t3 = f1.selectbox("국내/해외", ["전체"] + list(df_filtered['market'].unique()), key='t3_mkt')
            ast_filter_t3 = f2.selectbox("주식/그외", ["전체"] + list(df_filtered['asset'].unique()), key='t3_ast')
            rep_filter_t3 = f3.selectbox("대표지수", ["전체"] + list(df_filtered['is_rep'].unique()), key='t3_rep')
            
            f4, f5 = st.columns(2)
            drv_filter_t3 = f4.selectbox("일반/파생", ["전체"] + list(df_filtered['deriv'].unique()), key='t3_drv')
            trk_filter_t3 = f5.selectbox("패시브/액티브", ["전체"] + list(df_filtered['tracking'].unique()), key='t3_trk')

            df_c2_lp = df_lp.copy()
            df_c2_mkt = df_filtered.copy()

            if mkt_filter_t3 != "전체": 
                df_c2_lp = df_c2_lp[df_c2_lp['market'] == mkt_filter_t3]
                df_c2_mkt = df_c2_mkt[df_c2_mkt['market'] == mkt_filter_t3]
            if ast_filter_t3 != "전체": 
                df_c2_lp = df_c2_lp[df_c2_lp['asset'] == ast_filter_t3]
                df_c2_mkt = df_c2_mkt[df_c2_mkt['asset'] == ast_filter_t3]
            if rep_filter_t3 != "전체": 
                df_c2_lp = df_c2_lp[df_c2_lp['is_rep'] == rep_filter_t3]
                df_c2_mkt = df_c2_mkt[df_c2_mkt['is_rep'] == rep_filter_t3]
            if drv_filter_t3 != "전체": 
                df_c2_lp = df_c2_lp[df_c2_lp['deriv'] == drv_filter_t3]
                df_c2_mkt = df_c2_mkt[df_c2_mkt['deriv'] == drv_filter_t3]
            if trk_filter_t3 != "전체": 
                df_c2_lp = df_c2_lp[df_c2_lp['tracking'] == trk_filter_t3]
                df_c2_mkt = df_c2_mkt[df_c2_mkt['tracking'] == trk_filter_t3]

            filtered_lp_total = df_c2_lp['총LP거래대금'].sum()

            if filtered_lp_total > 0:
                amc_lp = df_c2_lp.groupby('amc')['총LP거래대금'].sum().reset_index()
                amc_mkt = df_c2_mkt.groupby('amc')['총LP거래대금'].sum()
                
                amc_lp['대금(억)'] = amc_lp['총LP거래대금'] / 100_000_000
                amc_lp['내부비중(%)'] = (amc_lp['총LP거래대금'] / filtered_lp_total) * 100
                amc_lp['AMC내_MS(%)'] = amc_lp.apply(
                    lambda r: (r['총LP거래대금'] / amc_mkt.get(r['amc'], 1)) * 100 if amc_mkt.get(r['amc'], 0) > 0 else 0, axis=1
                )
                
                st.dataframe(
                    amc_lp[amc_lp['총LP거래대금'] > 0].sort_values('총LP거래대금', ascending=False)
                    [['amc', '대금(억)', '내부비중(%)', 'AMC내_MS(%)']].style.format({'대금(억)': '{:,.0f}', '내부비중(%)': '{:.1f}%', 'AMC내_MS(%)': '{:.1f}%'}),
                    use_container_width=True, hide_index=True
                )
            else:
                st.warning("선택하신 필터 조건에 해당하는 LP 거래 내역이 없습니다.")

        st.divider()

        # --- 3️⃣ 전체 거래 종목 상세 분석 (합계 행 추가 및 누적비중 삭제) ---
        st.subheader(f"3️⃣ [{target_lp}] 전체 거래 종목 상세 분석 (섹터 필터링 & 추정매매손익)")
        
        fd1, fd2, fd3, fd4, fd5 = st.columns(5)
        mkt_filter_detail = fd1.selectbox("국내/해외", ["전체"] + list(df_filtered['market'].unique()), key='detail_mkt')
        ast_filter_detail = fd2.selectbox("주식/그외", ["전체"] + list(df_filtered['asset'].unique()), key='detail_ast')
        rep_filter_detail = fd3.selectbox("대표지수", ["전체"] + list(df_filtered['is_rep'].unique()), key='detail_rep')
        drv_filter_detail = fd4.selectbox("일반/파생", ["전체"] + list(df_filtered['deriv'].unique()), key='detail_drv')
        trk_filter_detail = fd5.selectbox("패시브/액티브", ["전체"] + list(df_filtered['tracking'].unique()), key='detail_trk')

        df_detail = df_lp.copy()
        if mkt_filter_detail != "전체": df_detail = df_detail[df_detail['market'] == mkt_filter_detail]
        if ast_filter_detail != "전체": df_detail = df_detail[df_detail['asset'] == ast_filter_detail]
        if rep_filter_detail != "전체": df_detail = df_detail[df_detail['is_rep'] == rep_filter_detail]
        if drv_filter_detail != "전체": df_detail = df_detail[df_detail['deriv'] == drv_filter_detail]
        if trk_filter_detail != "전체": df_detail = df_detail[df_detail['tracking'] == trk_filter_detail]

        total_detail_vol = df_detail['총LP거래대금'].sum()

        if total_detail_vol > 0:
            detail_etfs = df_detail.groupby('종목명')[
                ['총LP거래대금', 'LP매도거래대금', 'LP매수거래대금', 'LP순매수대금', 'LP매도거래량', 'LP매수거래량']
            ].sum().reset_index()

            detail_etfs = detail_etfs[detail_etfs['총LP거래대금'] > 0].sort_values('총LP거래대금', ascending=False).reset_index(drop=True)
            detail_etfs['순위'] = detail_etfs.index + 1
            
            detail_etfs['평균매도단가'] = np.where(detail_etfs['LP매도거래량'] > 0, detail_etfs['LP매도거래대금'] / detail_etfs['LP매도거래량'], 0)
            detail_etfs['평균매수단가'] = np.where(detail_etfs['LP매수거래량'] > 0, detail_etfs['LP매수거래대금'] / detail_etfs['LP매수거래량'], 0)
            detail_etfs['체결수량(min)'] = detail_etfs[['LP매도거래량', 'LP매수거래량']].min(axis=1)
            detail_etfs['추정매매이익'] = (detail_etfs['평균매도단가'] - detail_etfs['평균매수단가']) * detail_etfs['체결수량(min)']

            detail_etfs['거래대금(억)'] = detail_etfs['총LP거래대금'] / 100_000_000
            detail_etfs['매도대금(억)'] = detail_etfs['LP매도거래대금'] / 100_000_000
            detail_etfs['매수대금(억)'] = detail_etfs['LP매수거래대금'] / 100_000_000
            detail_etfs['순매수대금(억)'] = detail_etfs['LP순매수대금'] / 100_000_000
            detail_etfs['추정매매손익(백만)'] = detail_etfs['추정매매이익'] / 1_000_000
            detail_etfs['비중(%)'] = (detail_etfs['총LP거래대금'] / total_detail_vol) * 100

            # 합계 데이터 프레임 생성 (순위를 0으로 지정하여 상단 배치)
            total_row = pd.DataFrame([{
                '순위': 0,
                '종목명': '📊 [총 합계]',
                '거래대금(억)': detail_etfs['거래대금(억)'].sum(),
                '매도대금(억)': detail_etfs['매도대금(억)'].sum(),
                '매수대금(억)': detail_etfs['매수대금(억)'].sum(),
                '순매수대금(억)': detail_etfs['순매수대금(억)'].sum(),
                '추정매매손익(백만)': detail_etfs['추정매매손익(백만)'].sum(),
                '비중(%)': 100.0
            }])

            # 기존 데이터프레임과 합계 행 합치기
            detail_etfs = pd.concat([total_row, detail_etfs], ignore_index=True)

            st.write(f"해당 필터 조건 거래 종목 수: **{len(detail_etfs)-1:,}개** | 기간 총 거래대금: **{total_detail_vol/100_000_000:,.0f}억원**")

            # 누적비중 열 삭제됨
            show_cols = ['순위', '종목명', '거래대금(억)', '매도대금(억)', '매수대금(억)', '순매수대금(억)', '추정매매손익(백만)', '비중(%)']
            
            st.dataframe(
                detail_etfs[show_cols].set_index('순위').style.format({
                    '거래대금(억)': '{:,.0f}',
                    '매도대금(억)': '{:,.0f}',
                    '매수대금(억)': '{:,.0f}',
                    '순매수대금(억)': '{:,.0f}',
                    '추정매매손익(백만)': '{:,.0f}',
                    '비중(%)': '{:.2f}%'
                }), 
                use_container_width=True
            )
        else:
            st.warning("선택하신 필터 조건에 해당하는 종목 거래 내역이 없습니다.")

# ==========================================
# Tab 4: ETF별 주력 LP 분석
# ==========================================
with tab4:
    st.subheader("🔍 특정 ETF 종목의 LP 점유율 파악")
    etf_list = df_filtered.groupby(['a_code', '종목명'])['총LP거래대금'].sum().sort_values(ascending=False).reset_index()
    etf_options = [f"[{row['a_code']}] {row['종목명']}" for _, row in etf_list.iterrows()]

    selected_etf_str = st.selectbox("종목 검색 (거래대금 순 배열):", etf_options)

    if selected_etf_str:
        a_code_target = selected_etf_str.split("]")[0][1:]
        df_target = df_filtered[df_filtered['a_code'] == a_code_target]
        tot_target = df_target['총LP거래대금'].sum()

        st.write(f"**해당 ETF 기간 총 거래대금:** {tot_target/100_000_000:,.0f} 억원")

        target_lp_df = df_target.groupby('회원사명')[
            ['총LP거래대금', 'LP매도거래대금', 'LP매수거래대금', 'LP순매수대금', 'LP매도거래량', 'LP매수거래량']
        ].sum().reset_index()
        
        target_lp_df = target_lp_df[target_lp_df['총LP거래대금'] > 0].sort_values('총LP거래대금', ascending=False)
        
        target_lp_df['평균매도단가'] = np.where(target_lp_df['LP매도거래량'] > 0, target_lp_df['LP매도거래대금'] / target_lp_df['LP매도거래량'], 0)
        target_lp_df['평균매수단가'] = np.where(target_lp_df['LP매수거래량'] > 0, target_lp_df['LP매수거래대금'] / target_lp_df['LP매수거래량'], 0)
        
        target_lp_df['체결수량(min)'] = target_lp_df[['LP매도거래량', 'LP매수거래량']].min(axis=1)
        target_lp_df['추정매매이익'] = (target_lp_df['평균매도단가'] - target_lp_df['평균매수단가']) * target_lp_df['체결수량(min)']

        target_lp_df['대금(억)'] = target_lp_df['총LP거래대금'] / 100_000_000
        target_lp_df['매도대금(억)'] = target_lp_df['LP매도거래대금'] / 100_000_000
        target_lp_df['매수대금(억)'] = target_lp_df['LP매수거래대금'] / 100_000_000
        target_lp_df['순매수대금(억)'] = target_lp_df['LP순매수대금'] / 100_000_000
        target_lp_df['추정매매이익(백만)'] = target_lp_df['추정매매이익'] / 1_000_000
        target_lp_df['점유율(%)'] = (target_lp_df['총LP거래대금'] / tot_target) * 100
        target_lp_df['누적점유율(%)'] = target_lp_df['점유율(%)'].cumsum()

        show_cols = [
            '회원사명', '대금(억)', '매도대금(억)', '매수대금(억)', '순매수대금(억)', 
            '추정매매이익(백만)', '점유율(%)', '누적점유율(%)'
        ]

        st.dataframe(
            target_lp_df[show_cols].style.format({
                '대금(억)': '{:,.0f}',
                '매도대금(억)': '{:,.0f}',
                '매수대금(억)': '{:,.0f}',
                '순매수대금(억)': '{:,.0f}',
                '추정매매이익(백만)': '{:,.0f}',
                '점유율(%)': '{:.1f}%', 
                '누적점유율(%)': '{:.1f}%'
            }), use_container_width=True, hide_index=True
        )

# ==========================================
# Tab 5: 운용사별 주력 ETF 분석
# ==========================================
with tab5:
    st.subheader("🏢 운용사(AMC)별 ETF 및 1~3위 핵심 파트너 LP")
    amc_list = df_filtered.groupby('amc')['총LP거래대금'].sum().sort_values(ascending=False).index.tolist()
    target_amc = st.selectbox("운용사 선택", amc_list)

    if target_amc:
        df_amc = df_filtered[df_filtered['amc'] == target_amc]
        st.success(f"**{target_amc}** 총 거래대금: {df_amc['총LP거래대금'].sum()/100_000_000:,.0f} 억원")

        result_data = []
        for (a_code, name), group in df_amc.groupby(['a_code', '종목명']):
            tot_vol = group['총LP거래대금'].sum()
            if tot_vol == 0: continue

            lp_rank = group.groupby('회원사명')['총LP거래대금'].sum().sort_values(ascending=False)
            row = {'단축코드': a_code, '종목명': name, '총대금(억)': tot_vol / 100_000_000}

            for i in range(3):
                if i < len(lp_rank):
                    row[f'{i+1}위_LP'] = lp_rank.index[i]
                    row[f'{i+1}위_비중(%)'] = (lp_rank.values[i] / tot_vol) * 100
                else:
                    row[f'{i+1}위_LP'] = '-'
                    row[f'{i+1}위_비중(%)'] = 0
            result_data.append(row)

        st.dataframe(
            pd.DataFrame(result_data).sort_values('총대금(억)', ascending=False).style.format({
                '총대금(억)': '{:,.0f}', '1위_비중(%)': '{:.1f}%', '2위_비중(%)': '{:.1f}%', '3위_비중(%)': '{:.1f}%'
            }), use_container_width=True, hide_index=True
        )

# ==========================================
# Tab 6: 종목 집중도 분석
# ==========================================
with tab6:
    st.subheader("🎯 종목 집중도 (HHI 및 Top-N 의존도)")

    lp_vol = df_filtered.groupby('회원사명')['총LP거래대금'].sum()
    lp_etf_vol = df_filtered.groupby(['회원사명', '종목명'])[['총LP거래대금', 'LP매도거래대금', 'LP매수거래대금', 'LP순매수대금']].sum().reset_index()

    records = []
    for lp, lp_tot in lp_vol.items():
        if lp_tot == 0: continue
        etfs = lp_etf_vol[lp_etf_vol['회원사명'] == lp].sort_values('총LP거래대금', ascending=False)
        
        t1_name = etfs.iloc[0]['종목명'] if len(etfs) > 0 else "-"
        t1_vol = etfs.iloc[0]['총LP거래대금'] if len(etfs) > 0 else 0
        
        t2_name = etfs.iloc[1]['종목명'] if len(etfs) > 1 else "-"
        t2_vol = etfs.iloc[1]['총LP거래대금'] if len(etfs) > 1 else 0
        
        t3_name = etfs.iloc[2]['종목명'] if len(etfs) > 2 else "-"
        t3_vol = etfs.iloc[2]['총LP거래대금'] if len(etfs) > 2 else 0

        top3_vol_sum = t1_vol + t2_vol + t3_vol

        shares = (etfs['총LP거래대금'] / lp_tot) * 100
        hhi = (shares ** 2).sum()

        records.append({
            '회원사명': lp, 
            '총대금(억)': lp_tot / 100_000_000,
            '1위 종목명': t1_name,
            '1위 비중(%)': (t1_vol / lp_tot) * 100,
            '2위 종목명': t2_name,
            '2위 비중(%)': (t2_vol / lp_tot) * 100,
            '3위 종목명': t3_name,
            '3위 비중(%)': (t3_vol / lp_tot) * 100,
            'Top 3 누적비중(%)': (top3_vol_sum / lp_tot) * 100,
            'HHI 지수': hhi
        })

    conc_df = pd.DataFrame(records).sort_values('HHI 지수', ascending=False)

    st.info("💡 **HHI (허핀달-허쉬만 지수)**: 포트폴리오 내 개별 종목 점유율의 제곱합 (0~10,000). 숫자가 클수록 소수 특정 종목에 거래가 기형적으로 집중되어 있음을 의미합니다.")
    st.dataframe(
        conc_df.style.format({
            '총대금(억)': '{:,.0f}', 
            '1위 비중(%)': '{:.1f}%', 
            '2위 비중(%)': '{:.1f}%', 
            '3위 비중(%)': '{:.1f}%', 
            'Top 3 누적비중(%)': '{:.1f}%',
            'HHI 지수': '{:,.0f}'
        }), use_container_width=True, hide_index=True
    )