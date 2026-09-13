"""
Streamlit panosu. data/analysis.json ve data/extracted.json'u okur,
API anahtarı gerektirmez.

Kullanım:
    streamlit run src/app.py
"""

from __future__ import annotations

import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

st.set_page_config(page_title="İlan Beceri Radarı", layout="wide")


@st.cache_data
def load():
    analysis = json.loads((DATA_DIR / "analysis.json").read_text(encoding="utf-8"))
    rows = json.loads((DATA_DIR / "extracted.json").read_text(encoding="utf-8"))
    return analysis, pd.DataFrame(rows)


try:
    analysis, jobs = load()
except FileNotFoundError:
    st.error("data/analysis.json bulunamadı. Önce `python src/analyze.py` çalıştır.")
    st.stop()

st.title("İlan Beceri Radarı")
st.caption(
    "Remote OK açık API'sinden alınan ilanlardan Claude ile çıkarılmış beceri verisi. "
    "Kaynak: [Remote OK](https://remoteok.com)"
)

counts = analysis["counts"]
c1, c2, c3, c4 = st.columns(4)
c1.metric("İlan", counts["total_jobs"])
c2.metric("Teknik ilan", counts["technical_jobs"])
c3.metric("Farklı beceri", counts["unique_skills"])
c4.metric("İlan başına beceri", counts["avg_skills_per_job"])

st.divider()

left, right = st.columns([3, 2])

with left:
    st.subheader("En çok istenen beceriler")
    top = pd.DataFrame(analysis["top_skills"])
    chart = (
        alt.Chart(top)
        .mark_bar()
        .encode(
            x=alt.X("count:Q", title="ilan sayısı"),
            y=alt.Y("skill:N", sort="-x", title=None),
            tooltip=["skill", "count"],
        )
        .properties(height=520)
    )
    st.altair_chart(chart, width="stretch")

with right:
    st.subheader("Seviye dağılımı")
    seniority = pd.DataFrame(
        analysis["seniority"].items(), columns=["seviye", "ilan"]
    )
    st.altair_chart(
        alt.Chart(seniority)
        .mark_arc(innerRadius=60)
        .encode(theta="ilan:Q", color=alt.Color("seviye:N", title=None), tooltip=["seviye", "ilan"])
        .properties(height=240),
        width="stretch",
    )

    st.subheader("Rol ailesi")
    roles = pd.DataFrame(analysis["role_family"].items(), columns=["rol", "ilan"])
    st.dataframe(roles, hide_index=True, width="stretch", height=240)

st.divider()

st.subheader("Hangi beceriler birlikte isteniyor")
st.caption(
    "lift = bağımsız olsalardı beklenenin kaç katı birlikte geçiyorlar. "
    "1'in üzerindeki her değer gerçek bir birliktelik demek."
)
edges = pd.DataFrame(analysis["co_occurrence"])
if not edges.empty:
    heat = (
        alt.Chart(edges)
        .mark_rect()
        .encode(
            x=alt.X("source:N", title=None),
            y=alt.Y("target:N", title=None),
            color=alt.Color("lift:Q", scale=alt.Scale(scheme="blues"), title="lift"),
            tooltip=["source", "target", "count", "lift"],
        )
        .properties(height=480)
    )
    st.altair_chart(heat, width="stretch")

    st.markdown("**En güçlü 15 birliktelik**")
    st.dataframe(
        edges.sort_values("lift", ascending=False)
        .head(15)[["source", "target", "count", "lift"]]
        .reset_index(drop=True),
        hide_index=True,
        width="stretch",
    )

st.divider()

col_a, col_b = st.columns(2)

with col_a:
    st.subheader("Beceri başına maaş medyanı")
    st.caption(f"Sadece maaşı açıklanmış {counts['with_salary']} ilan üzerinden, en az 5 gözlem.")
    salary = pd.DataFrame(analysis["skill_salary"])
    if not salary.empty:
        st.altair_chart(
            alt.Chart(salary)
            .mark_bar()
            .encode(
                x=alt.X("median_usd:Q", title="medyan USD/yıl"),
                y=alt.Y("skill:N", sort="-x", title=None),
                tooltip=["skill", "median_usd", "n"],
            )
            .properties(height=420),
            width="stretch",
        )
    else:
        st.info("Yeterli maaş verisi yok.")

with col_b:
    st.subheader("Çalışma şekli ve konum kısıtı")
    st.dataframe(
        pd.DataFrame(analysis["work_mode"].items(), columns=["çalışma şekli", "ilan"]),
        hide_index=True,
        width="stretch",
    )
    st.dataframe(
        pd.DataFrame(analysis["location_notes"].items(), columns=["konum kısıtı", "ilan"]),
        hide_index=True,
        width="stretch",
    )

st.divider()

st.subheader("Ham çıkarım çıktısı")
st.caption("Modelin ilan başına ne ürettiğini görmek için — hata aramanın en hızlı yolu bu tablo.")
skill_filter = st.text_input("Beceriye göre filtrele (örn. react)").strip().lower()
view = jobs.copy()
view["skills"] = view["skills"].apply(lambda s: ", ".join(s))
if skill_filter:
    view = view[view["skills"].str.contains(skill_filter, na=False)]
st.dataframe(
    view[["position", "company", "seniority", "role_family", "years_required", "skills", "url"]],
    hide_index=True,
    width="stretch",
    column_config={"url": st.column_config.LinkColumn("ilan", display_text="aç")},
)
