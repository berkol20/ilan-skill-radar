"""
Remote OK'in açık JSON API'sinden ilanları çeker.

API anahtarı gerekmiyor. Tek istek atıyoruz, sonuç data/raw_jobs.json'a yazılıyor.
Feed'in ilk elemanı ilan değil, Remote OK'in yasal/attribution notu — onu ayrı
saklıyoruz ve README'de kaynağı belirtiyoruz.

Kullanım:
    python src/fetch_jobs.py --limit 300
    python src/fetch_jobs.py --limit 200 --tags python,data
"""

from __future__ import annotations

import argparse
import html
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

API_URL = "https://remoteok.com/api"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Remote OK bot trafiğini engellemesin diye normal bir User-Agent gönderiyoruz.
HEADERS = {"User-Agent": "ilan-skill-radar/0.1 (portfolio project; contact: you@example.com)"}


def strip_html(raw: str) -> str:
    """İlan açıklamaları HTML içeriyor. Etiketleri at, boşlukları sadeleştir."""
    if not raw:
        return ""
    text = re.sub(r"<br\s*/?>|</p>|</div>|</li>", "\n", raw, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def fetch(tag: str | None = None) -> tuple[dict, list[dict]]:
    """Tek istek. Tag verilirse Remote OK sunucu tarafında filtreliyor."""
    params = {"tags": tag} if tag else None
    response = requests.get(API_URL, headers=HEADERS, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()

    if not isinstance(payload, list) or not payload:
        raise RuntimeError("Beklenmeyen API cevabı: liste bekleniyordu")

    legal = payload[0]
    jobs = [item for item in payload[1:] if item.get("id")]
    return legal, jobs


def normalise(job: dict) -> dict:
    """API cevabından sadece ihtiyacımız olan alanları alıp sabit bir şemaya sokar."""
    return {
        "id": str(job.get("id")),
        "position": job.get("position") or job.get("title") or "",
        "company": job.get("company") or "",
        "tags": job.get("tags") or [],
        "location": job.get("location") or "",
        "salary_min": job.get("salary_min"),
        "salary_max": job.get("salary_max"),
        "date": job.get("date"),
        "url": job.get("url"),
        "apply_url": job.get("apply_url"),
        "description": strip_html(job.get("description", "")),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Remote OK ilanlarını indir")
    parser.add_argument("--limit", type=int, default=300, help="kaç ilan saklanacak")
    parser.add_argument("--tags", default=None, help="virgülle ayrılmış Remote OK tag'leri")
    parser.add_argument(
        "--min-desc",
        type=int,
        default=400,
        help="bu karakterden kısa açıklamaları at (çıkarım için çok az bilgi var)",
    )
    args = parser.parse_args()

    # Etiketsiz feed en yeni ~100 ilanı veriyor. Daha geniş bir küme için her
    # etiket için ayrı istek atıp id üzerinden birleştiriyoruz.
    tags = [t.strip() for t in args.tags.split(",")] if args.tags else [None]

    legal: dict = {}
    merged: dict[str, dict] = {}
    for tag in tags:
        legal, jobs = fetch(tag)
        new = 0
        for job in jobs:
            job_id = str(job.get("id"))
            if job_id not in merged:
                merged[job_id] = job
                new += 1
        label = tag or "(etiketsiz feed)"
        print(f"{label}: {len(jobs)} ilan geldi, {new} tanesi yeni")
        if tag:
            time.sleep(1)  # API'yi yormayalım

    print(f"birleştirilmiş toplam: {len(merged)}")

    rows = [normalise(job) for job in merged.values()]
    rows = [row for row in rows if len(row["description"]) >= args.min_desc]
    print(f"Açıklaması {args.min_desc} karakterden uzun olan: {len(rows)}")

    rows = rows[: args.limit]

    DATA_DIR.mkdir(exist_ok=True)
    output = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "Remote OK (https://remoteok.com)",
        "source_terms": legal,
        "count": len(rows),
        "jobs": rows,
    }
    path = DATA_DIR / "raw_jobs.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(rows)} ilan yazıldı -> {path}")


if __name__ == "__main__":
    main()
