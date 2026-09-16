"""서울의 100년 기온 변화를 보여주는 스트림릿 앱."""

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

DATA_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/seoul.csv"
LOCAL_PATH = "seoul.csv"

st.set_page_config(page_title="서울 100년 기온 변화", page_icon="🌡️", layout="wide")


@st.cache_data
def load_data():
    """seoul.csv를 읽어 온다. 같은 폴더에 파일이 있으면 그것을, 없으면 원본 주소에서 받는다."""
    try:
        df = pd.read_csv(LOCAL_PATH, encoding="utf-8-sig")
    except FileNotFoundError:
        df = pd.read_csv(DATA_URL, encoding="utf-8-sig")

    df.columns = [c.strip() for c in df.columns]
    df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
    df = df.dropna(subset=["날짜"])

    for col in ["평균기온", "최저기온", "최고기온"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["연도"] = df["날짜"].dt.year
    return df


@st.cache_data
def yearly_summary(df):
    """연도별 평균을 계산한다. 관측일이 300일 미만인 해는 통계가 왜곡되므로 제외한다."""
    grouped = df.groupby("연도").agg(
        평균기온=("평균기온", "mean"),
        최저기온=("최저기온", "mean"),
        최고기온=("최고기온", "mean"),
        관측일수=("평균기온", "count"),
    )
    yearly = grouped[grouped["관측일수"] >= 300].reset_index()
    yearly["10년 이동평균"] = yearly["평균기온"].rolling(10, min_periods=10).mean()
    return yearly


df = load_data()
yearly = yearly_summary(df)

st.title("🌡️ 서울의 100년 기온 변화")
st.caption("기상청 서울 관측소(지점 108) 일별 기온 자료를 연 단위로 정리했습니다.")

if yearly.empty:
    st.error("연평균을 계산할 수 있는 자료가 없습니다. 데이터 파일을 확인해 주세요.")
    st.stop()

min_year = int(yearly["연도"].min())
max_year = int(yearly["연도"].max())

with st.sidebar:
    st.header("보기 설정")
    start_year, end_year = st.slider(
        "기간 선택",
        min_value=min_year,
        max_value=max_year,
        value=(min_year, max_year),
    )
    show_avg = st.checkbox("10년 이동평균 보기", value=True)
    show_trend = st.checkbox("전체 추세선 보기", value=True)
    show_range = st.checkbox("연평균 최저·최고기온 함께 보기", value=False)

view = yearly[(yearly["연도"] >= start_year) & (yearly["연도"] <= end_year)].copy()

# ── 한눈에 보는 숫자 ──────────────────────────────────────────────
first30 = view.head(30)["평균기온"].mean()
last30 = view.tail(30)["평균기온"].mean()
diff = last30 - first30

slope = np.polyfit(view["연도"], view["평균기온"], 1)[0]
hottest = view.loc[view["평균기온"].idxmax()]
coldest = view.loc[view["평균기온"].idxmin()]

c1, c2, c3, c4 = st.columns(4)
c1.metric("처음 30년 평균", f"{first30:.2f} ℃")
c2.metric("최근 30년 평균", f"{last30:.2f} ℃", f"{diff:+.2f} ℃")
c3.metric("100년당 상승폭", f"{slope * 100:+.2f} ℃")
c4.metric("가장 더웠던 해", f"{int(hottest['연도'])}년", f"{hottest['평균기온']:.2f} ℃")

st.markdown(
    f"**{start_year}년부터 {end_year}년까지**, 서울의 연평균 기온은 "
    f"10년마다 약 **{slope * 10:+.2f}℃**씩 변해 왔습니다. "
    f"가장 추웠던 해는 {int(coldest['연도'])}년({coldest['평균기온']:.2f}℃)입니다."
)

# ── 그래프 ────────────────────────────────────────────────────────
base = alt.Chart(view).encode(
    x=alt.X("연도:Q", title="연도", scale=alt.Scale(nice=False), axis=alt.Axis(format="d"))
)

layers = [
    base.mark_circle(size=28, opacity=0.45, color="#9AB5D9").encode(
        y=alt.Y("평균기온:Q", title="연평균 기온 (℃)", scale=alt.Scale(zero=False)),
        tooltip=[
            alt.Tooltip("연도:Q", title="연도", format="d"),
            alt.Tooltip("평균기온:Q", title="연평균 기온", format=".2f"),
            alt.Tooltip("최저기온:Q", title="평균 최저기온", format=".2f"),
            alt.Tooltip("최고기온:Q", title="평균 최고기온", format=".2f"),
        ],
    ),
    base.mark_line(strokeWidth=1.2, opacity=0.5, color="#9AB5D9").encode(
        y=alt.Y("평균기온:Q", scale=alt.Scale(zero=False))
    ),
]

if show_avg:
    layers.append(
        base.mark_line(strokeWidth=3.5, color="#E4572E").encode(
            y=alt.Y("10년 이동평균:Q", scale=alt.Scale(zero=False))
        )
    )

if show_trend:
    layers.append(
        base.transform_regression("연도", "평균기온")
        .mark_line(strokeDash=[7, 5], strokeWidth=2, color="#2E4057")
        .encode(y=alt.Y("평균기온:Q", scale=alt.Scale(zero=False)))
    )

chart = alt.layer(*layers).properties(height=430).interactive()
st.altair_chart(chart, use_container_width=True)

legend = ["🔵 연평균 기온", "🟠 10년 이동평균" if show_avg else "", "⬛ 추세선" if show_trend else ""]
st.caption("  |  ".join([x for x in legend if x]))

if show_range:
    st.subheader("연평균 최저기온과 최고기온")
    long_df = view.melt(
        id_vars="연도",
        value_vars=["최저기온", "평균기온", "최고기온"],
        var_name="구분",
        value_name="기온",
    )
    range_chart = (
        alt.Chart(long_df)
        .mark_line(strokeWidth=2)
        .encode(
            x=alt.X("연도:Q", title="연도", scale=alt.Scale(nice=False), axis=alt.Axis(format="d")),
            y=alt.Y("기온:Q", title="기온 (℃)", scale=alt.Scale(zero=False)),
            color=alt.Color("구분:N", title="구분"),
            tooltip=[
                alt.Tooltip("연도:Q", title="연도", format="d"),
                alt.Tooltip("구분:N", title="구분"),
                alt.Tooltip("기온:Q", title="기온", format=".2f"),
            ],
        )
        .properties(height=360)
        .interactive()
    )
    st.altair_chart(range_chart, use_container_width=True)

# ── 원자료 ────────────────────────────────────────────────────────
with st.expander("연도별 수치 보기"):
    table = view[["연도", "평균기온", "최저기온", "최고기온", "관측일수"]].copy()
    table[["평균기온", "최저기온", "최고기온"]] = table[
        ["평균기온", "최저기온", "최고기온"]
    ].round(2)
    st.dataframe(table, use_container_width=True, hide_index=True)
    st.download_button(
        "연도별 자료 내려받기 (CSV)",
        table.to_csv(index=False).encode("utf-8-sig"),
        file_name="seoul_yearly_temperature.csv",
        mime="text/csv",
    )

st.caption(
    "자료 출처: 기상청 기상자료개방포털 · 관측일이 300일이 안 되는 해는 "
    "연평균이 실제와 달라질 수 있어 그래프에서 제외했습니다."
)
