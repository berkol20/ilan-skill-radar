"""
Kural tabanlı çıkarım — API anahtarı gerektirmez, ücretsizdir.

extract.py ile aynı şemayı üretir, aynı dosyaya yazar. Yani analyze.py ve
app.py hiçbir değişiklik olmadan çalışır.

Yöntem: beceri sözlüğü + kelime sınırı duyarlı regex eşleştirme. Kısa ve
tehlikeli isimler (go, r, c) için özel kalıplar var, yoksa "go to the office"
cümlesi Go diliymiş gibi sayılıyor.

Kullanım:
    python src/extract_rules.py
    python src/extract_rules.py --limit 20 --verbose
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# canonical isim -> metinde aranacak yazımlar
SKILLS: dict[str, list[str]] = {
    "python": ["python"],
    "javascript": ["javascript", "js"],
    "typescript": ["typescript", "ts"],
    "react": ["react", "react.js", "reactjs"],
    "next.js": ["next.js", "nextjs"],
    "vue": ["vue", "vue.js", "vuejs"],
    "angular": ["angular"],
    "svelte": ["svelte"],
    "node.js": ["node.js", "nodejs", "node"],
    "django": ["django"],
    "flask": ["flask"],
    "fastapi": ["fastapi"],
    "rails": ["rails", "ruby on rails"],
    "laravel": ["laravel"],
    "spring": ["spring", "spring boot"],
    ".net": [".net", "dotnet", "asp.net"],
    "java": ["java"],
    "ruby": ["ruby"],
    "php": ["php"],
    "rust": ["rust"],
    "scala": ["scala"],
    "kotlin": ["kotlin"],
    "elixir": ["elixir"],
    "postgresql": ["postgresql", "postgres"],
    "mysql": ["mysql"],
    "mongodb": ["mongodb", "mongo"],
    "redis": ["redis"],
    "elasticsearch": ["elasticsearch", "elastic search"],
    "dynamodb": ["dynamodb"],
    "sql": ["sql"],
    "nosql": ["nosql"],
    "aws": ["aws", "amazon web services"],
    "azure": ["azure"],
    "google cloud": ["gcp", "google cloud"],
    "docker": ["docker"],
    "kubernetes": ["kubernetes", "k8s"],
    "terraform": ["terraform"],
    "ansible": ["ansible"],
    "ci/cd": ["ci/cd", "cicd", "continuous integration", "continuous delivery"],
    "jenkins": ["jenkins"],
    "github actions": ["github actions"],
    "linux": ["linux", "unix"],
    "bash": ["bash", "shell scripting"],
    "graphql": ["graphql"],
    "rest api": ["rest api", "rest apis", "restful api", "restful apis"],
    "grpc": ["grpc"],
    "microservices": ["microservices", "microservice"],
    "kafka": ["kafka"],
    "rabbitmq": ["rabbitmq"],
    "airflow": ["airflow"],
    "dbt": ["dbt"],
    "spark": ["spark", "pyspark"],
    "hadoop": ["hadoop"],
    "snowflake": ["snowflake"],
    "databricks": ["databricks"],
    "tableau": ["tableau"],
    "power bi": ["power bi", "powerbi"],
    "looker": ["looker"],
    "pandas": ["pandas"],
    "numpy": ["numpy"],
    "scikit-learn": ["scikit-learn", "sklearn", "scikit learn"],
    "pytorch": ["pytorch"],
    "tensorflow": ["tensorflow"],
    "machine learning": ["machine learning", "ml models"],
    "nlp": ["nlp", "natural language processing"],
    "llm": ["llm", "llms", "large language model", "large language models"],
    "computer vision": ["computer vision"],
    "data engineering": ["data engineering", "etl", "elt"],
    "html": ["html", "html5"],
    "css": ["css", "css3"],
    "tailwind": ["tailwind", "tailwindcss"],
    "sass": ["sass", "scss"],
    "figma": ["figma"],
    "react native": ["react native"],
    "flutter": ["flutter"],
    "ios": ["ios"],
    "android": ["android"],
    "git": ["git"],
    "jira": ["jira"],
    "agile": ["agile", "scrum"],
    "testing": ["unit testing", "unit tests", "test automation", "tdd"],
    "cypress": ["cypress"],
    "playwright": ["playwright"],
    "selenium": ["selenium"],
    "webpack": ["webpack"],
    "vite": ["vite"],
    "redux": ["redux"],
    "prisma": ["prisma"],
    "supabase": ["supabase"],
    "firebase": ["firebase"],
    "stripe": ["stripe"],
    "salesforce": ["salesforce"],
    "sap": ["sap"],
    "seo": ["seo"],
}

# Çok kısa oldukları için normal kelime sınırı yetmeyen isimler.
# Bunlar ancak belirli bağlamlarda sayılıyor.
STRICT_SKILLS: dict[str, list[str]] = {
    # "in go" kalıbı "go-to-market" ifadesini yakalıyordu: 60 ilanın çoğu
    # yanlış pozitifti (İK, operatör, teknisyen ilanları). Artık tire ve
    # "go to/live/forward" devamları dışlanıyor.
    "go": [
        r"\bgolang\b",
        r"\bgo\s+(?:lang|programming|developer|engineer)\b",
        r"(?<![\w-])(?:in|with|using|of)\s+go(?![\w-])(?!\s+(?:to|live|forward|public|through))",
        r"(?<![\w-])go(?![\w-])\s*(?:,|/|and)\s*(?:rust|python|java|node|kubernetes|c\+\+)",
    ],
    # "swift action", "swift response" gibi sıfat kullanımlarını dışla
    "swift": [
        r"(?<![a-z0-9])swiftui(?![a-z0-9])",
        r"(?<![a-z0-9])swift(?![a-z0-9])(?!\s+(?:action|response|decision|turnaround|resolution|execution))",
    ],
    "r": [r"\br\s+(?:programming|language)\b", r"\b(?:python|sql)\s*(?:,|/|and)\s*r\b"],
    "c": [r"\bc\s+programming\b", r"\bc/c\+\+"],
    "c++": [r"c\+\+"],
    "c#": [r"c#"],
}

SENIORITY_TITLE = [
    ("lead", [r"\b(lead|principal|staff|head of|director|vp of)\b"]),
    ("senior", [r"\b(senior|sr\.?|experienced)\b"]),
    ("intern", [r"\b(intern|internship|trainee|apprentice)\b"]),
    ("junior", [r"\b(junior|jr\.?|entry[\s-]level|graduate)\b"]),
    ("mid", [r"\b(mid[\s-]level|intermediate)\b"]),
]

YEARS_PATTERNS = [
    r"(\d{1,2})\s*\+?\s*(?:-|–|to)\s*\d{1,2}\s*(?:\+)?\s*years?",  # 3-5 years
    r"(?:at least|minimum(?: of)?|min\.?)\s*(\d{1,2})\s*(?:\+)?\s*years?",
    r"(\d{1,2})\s*\+\s*years?",
    r"(\d{1,2})\s*years?\s+(?:of\s+)?(?:professional\s+|relevant\s+|hands[\s-]on\s+)?experience",
]

ROLE_RULES = [
    ("data", [r"\bdata (scientist|engineer|analyst)\b", r"\bmachine learning\b", r"\banalytics\b", r"\bml engineer\b"]),
    ("devops", [r"\bdevops\b", r"\bsre\b", r"\bsite reliability\b", r"\binfrastructure\b", r"\bplatform engineer\b", r"\bcloud engineer\b"]),
    ("security", [r"\bsecurity\b", r"\bappsec\b", r"\bpenetration\b"]),
    ("mobile", [r"\bmobile\b", r"\bios\b", r"\bandroid\b", r"\breact native\b", r"\bflutter\b"]),
    ("qa", [r"\bqa\b", r"\bquality assurance\b", r"\btest engineer\b", r"\bsdet\b"]),
    ("frontend", [r"\bfront[\s-]?end\b", r"\bui engineer\b", r"\bweb developer\b"]),
    ("backend", [r"\bback[\s-]?end\b", r"\bserver[\s-]side\b"]),
    ("fullstack", [r"\bfull[\s-]?stack\b"]),
    ("design", [r"\bdesigner\b", r"\bux\b", r"\bui/ux\b", r"\bproduct design\b"]),
    ("product", [r"\bproduct manager\b", r"\bproduct owner\b", r"\bprogram manager\b"]),
    ("marketing", [r"\bmarketing\b", r"\bgrowth\b", r"\bcontent writer\b", r"\bseo\b"]),
    ("sales", [r"\bsales\b", r"\baccount executive\b", r"\bbusiness development\b"]),
    ("support", [r"\bsupport\b", r"\bcustomer success\b"]),
    ("engineering", [r"\bengineer\b", r"\bdeveloper\b", r"\bprogrammer\b", r"\barchitect\b"]),
]

NON_TECHNICAL_ROLES = {"marketing", "sales", "support", "product", "design"}

LOCATION_PATTERNS = [
    (r"\bus[\s-]?(?:only|based)\b|\bunited states only\b", "US only"),
    (r"\bcanada only\b|\bcanad(?:a|ian)[\s-]?based\b", "Canada only"),
    (r"\beu[\s-]?(?:only|based)\b|\beurope[\s-]?(?:only|based)\b", "EU only"),
    (r"\b(?:emea|cet|cest)\s*(?:timezone|time zone)?\b", "European timezone"),
    (r"\b(?:est|pst|pdt|edt)\s*(?:timezone|time zone)?\b", "US timezone"),
    (r"\blatam\b|\blatin america\b", "LATAM"),
    (r"\bapac\b|\basia[\s-]pacific\b", "APAC"),
    (r"\bworldwide\b|\banywhere\b|\bglobal(?:ly)?\b", "Worldwide"),
    (r"\buk[\s-]?(?:only|based)\b", "UK only"),
]


def build_skill_patterns() -> dict[str, re.Pattern]:
    patterns = {}
    for canonical, aliases in SKILLS.items():
        parts = []
        for alias in sorted(aliases, key=len, reverse=True):
            escaped = re.escape(alias)
            # kelime sınırı: önce/sonra harf-rakam gelmemeli
            parts.append(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])")
        patterns[canonical] = re.compile("|".join(parts), re.I)
    for canonical, raw in STRICT_SKILLS.items():
        patterns[canonical] = re.compile("|".join(raw), re.I)
    return patterns


SKILL_PATTERNS = build_skill_patterns()


def find_skills(text: str) -> list[str]:
    return sorted(name for name, pattern in SKILL_PATTERNS.items() if pattern.search(text))


def find_seniority(title: str, body: str) -> str:
    for level, patterns in SENIORITY_TITLE:
        if any(re.search(p, title, re.I) for p in patterns):
            return level
    for level, patterns in SENIORITY_TITLE:
        if any(re.search(p, body[:600], re.I) for p in patterns):
            return level
    return "unspecified"


def find_years(text: str) -> int | None:
    found = []
    for pattern in YEARS_PATTERNS:
        for match in re.finditer(pattern, text, re.I):
            try:
                value = int(match.group(1))
            except (IndexError, ValueError):
                continue
            if 0 < value <= 20:
                found.append(value)
    return min(found) if found else None


def find_role(title: str, body: str) -> str:
    for role, patterns in ROLE_RULES:
        if any(re.search(p, title, re.I) for p in patterns):
            return role
    for role, patterns in ROLE_RULES:
        if any(re.search(p, body[:800], re.I) for p in patterns):
            return role
    return "other"


def find_work_mode(text: str, location: str) -> str:
    haystack = f"{location} {text}"
    if re.search(r"\bhybrid\b", haystack, re.I):
        return "hybrid"
    if re.search(r"\bon[\s-]?site\b|\bin[\s-]office\b", haystack, re.I):
        return "onsite"
    if re.search(r"\bremote\b|\bwork from home\b|\bdistributed team\b|\bworldwide\b|\banywhere\b", haystack, re.I):
        return "remote"
    return "unspecified"


def find_location_note(text: str, location: str) -> str | None:
    haystack = f"{location} {text[:1500]}"
    for pattern, label in LOCATION_PATTERNS:
        if re.search(pattern, haystack, re.I):
            return label
    return location.strip() or None


def extract(job: dict) -> dict:
    title = job["position"]
    body = job["description"]
    text = f"{title}\n{' '.join(job.get('tags', []))}\n{body}"

    skills = find_skills(text)
    role = find_role(title, body)
    technical = role not in NON_TECHNICAL_ROLES and len(skills) >= 2

    return {
        "id": job["id"],
        "position": title,
        "company": job["company"],
        "url": job["url"],
        "salary_min": job.get("salary_min"),
        "salary_max": job.get("salary_max"),
        "remoteok_tags": job.get("tags", []),
        "is_technical": technical,
        "skills": skills if technical else [],
        "seniority": find_seniority(title, body),
        "years_required": find_years(body),
        "work_mode": find_work_mode(body, job.get("location", "")),
        "location_note": find_location_note(body, job.get("location", "")),
        "role_family": role,
        "method": "rules",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Kural tabanlı ilan çıkarımı")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--verbose", action="store_true", help="her ilan için satır bas")
    parser.add_argument(
        "--out", default="extracted.json", help="çıktı dosya adı (data/ içinde)"
    )
    args = parser.parse_args()

    raw_path = DATA_DIR / "raw_jobs.json"
    if not raw_path.exists():
        raise SystemExit("data/raw_jobs.json yok. Önce: python src/fetch_jobs.py")

    jobs = json.loads(raw_path.read_text(encoding="utf-8"))["jobs"]
    if args.limit:
        jobs = jobs[: args.limit]

    rows = []
    for job in jobs:
        row = extract(job)
        rows.append(row)
        if args.verbose:
            print(f"  {row['position'][:46]:48s} {row['role_family']:12s} {len(row['skills'])} beceri")

    out_path = DATA_DIR / args.out
    out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    technical = [r for r in rows if r["is_technical"]]
    no_skill = [r for r in technical if not r["skills"]]
    print("\n--- özet ---")
    print(f"ilan            : {len(rows)}")
    print(f"teknik sayılan  : {len(technical)}")
    print(f"ilan başına bec.: {sum(len(r['skills']) for r in technical) / max(len(technical), 1):.1f}")
    print(f"hiç beceri yok  : {len(no_skill)}")
    print(f"maliyet         : $0.00")
    print(f"yazıldı -> {out_path}")


if __name__ == "__main__":
    main()
