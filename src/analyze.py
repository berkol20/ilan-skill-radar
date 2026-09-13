"""
Çıkarılmış ilanlardan toplulaştırılmış istatistikler üretir.

Çıktı: data/analysis.json — app.py bunu okur, böylece pano API anahtarı
olmadan da çalışır.

Kullanım:
    python src/analyze.py
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from statistics import median

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Aynı şeyin farklı yazımlarını tek isimde topla. Çıkarım prompt'u normalize
# etmeye çalışıyor ama yine de kaçaklar oluyor — bu tablo onları yakalıyor.
ALIASES = {
    "nodejs": "node.js",
    "node": "node.js",
    "reactjs": "react",
    "react.js": "react",
    "postgres": "postgresql",
    "golang": "go",
    "js": "javascript",
    "ts": "typescript",
    "k8s": "kubernetes",
    "amazon web services": "aws",
    "gcp": "google cloud",
    "ci": "ci/cd",
    "cd": "ci/cd",
    "restful apis": "rest api",
    "rest apis": "rest api",
    "restful api": "rest api",
}


def canon(skill: str) -> str:
    key = skill.strip().lower()
    return ALIASES.get(key, key)


def load() -> list[dict]:
    path = DATA_DIR / "extracted.json"
    if not path.exists():
        raise SystemExit("data/extracted.json yok. Önce: python src/extract.py")
    rows = json.loads(path.read_text(encoding="utf-8"))
    for row in rows:
        row["skills"] = sorted({canon(s) for s in row.get("skills", []) if s.strip()})
    return rows


def salary_mid(row: dict) -> float | None:
    lo, hi = row.get("salary_min"), row.get("salary_max")
    if lo and hi and hi > 0:
        return (lo + hi) / 2
    return float(lo) if lo else None


def build(rows: list[dict], top_n: int = 25, min_pair: int = 3) -> dict:
    technical = [r for r in rows if r.get("is_technical")]

    freq = Counter(skill for row in technical for skill in row["skills"])
    top_skills = freq.most_common(top_n)
    top_names = [name for name, _ in top_skills]

    # Birlikte geçiş: sadece en sık becerilerin arasındaki çiftlere bakıyoruz,
    # yoksa matris uzun kuyrukla dolup okunmaz hale geliyor.
    pairs: Counter[tuple[str, str]] = Counter()
    for row in technical:
        relevant = sorted(set(row["skills"]) & set(top_names))
        pairs.update(combinations(relevant, 2))

    # Lift: iki beceri bağımsız olsaydı beklenenin kaç katı birlikte geçiyor.
    total = len(technical) or 1
    edges = []
    for (a, b), count in pairs.items():
        if count < min_pair:
            continue
        expected = (freq[a] / total) * (freq[b] / total) * total
        edges.append(
            {
                "source": a,
                "target": b,
                "count": count,
                "lift": round(count / expected, 2) if expected else None,
            }
        )
    edges.sort(key=lambda e: e["count"], reverse=True)

    # Beceri başına maaş medyanı — sadece maaşı açıklanmış ilanlar üzerinden.
    salaries: dict[str, list[float]] = defaultdict(list)
    for row in technical:
        mid = salary_mid(row)
        if mid:
            for skill in row["skills"]:
                salaries[skill].append(mid)
    skill_salary = [
        {"skill": skill, "median_usd": round(median(values)), "n": len(values)}
        for skill, values in salaries.items()
        if len(values) >= 5
    ]
    skill_salary.sort(key=lambda item: item["median_usd"], reverse=True)

    years = [r["years_required"] for r in technical if r.get("years_required")]

    return {
        "counts": {
            "total_jobs": len(rows),
            "technical_jobs": len(technical),
            "unique_skills": len(freq),
            "avg_skills_per_job": round(
                sum(len(r["skills"]) for r in technical) / (len(technical) or 1), 2
            ),
            "with_salary": sum(1 for r in technical if salary_mid(r)),
        },
        "top_skills": [{"skill": s, "count": c} for s, c in top_skills],
        "co_occurrence": edges[:120],
        "seniority": dict(Counter(r["seniority"] for r in technical).most_common()),
        "work_mode": dict(Counter(r["work_mode"] for r in technical).most_common()),
        "role_family": dict(
            Counter(canon(r.get("role_family", "unknown")) for r in technical).most_common(15)
        ),
        "location_notes": dict(
            Counter(r["location_note"] for r in technical if r.get("location_note")).most_common(15)
        ),
        "skill_salary": skill_salary[:25],
        "years_required": {
            "median": median(years) if years else None,
            "distribution": dict(Counter(years).most_common()),
        },
    }


def main() -> None:
    rows = load()
    analysis = build(rows)
    path = DATA_DIR / "analysis.json"
    path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")

    counts = analysis["counts"]
    print(f"{counts['technical_jobs']} teknik ilan, {counts['unique_skills']} farklı beceri")
    print("en sık 10 beceri:")
    for item in analysis["top_skills"][:10]:
        print(f"  {item['count']:4d}  {item['skill']}")
    print(f"\nyazıldı -> {path}")


if __name__ == "__main__":
    main()
