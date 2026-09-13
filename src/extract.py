"""
İlan metinlerinden Claude ile yapılandırılmış veri çıkarır.

Serbest formatlı ilan açıklaması -> sabit şemalı JSON. Şemaya uyulmasını
prompt'la rica etmek yerine tool use ile zorluyoruz: modele `extract_job` adında
bir araç veriyoruz, cevabı o aracın input_schema'sına uymak zorunda.

Özellikler:
- resume: data/extracted.json varsa, orada olan ilanları tekrar işlemez
- paralel istek (varsayılan 4 thread)
- retry + backoff (429 / 5xx için)
- sonunda token ve tahmini maliyet raporu

Kullanım:
    export ANTHROPIC_API_KEY=sk-ant-...
    python src/extract.py                 # hepsini işle
    python src/extract.py --limit 20      # önce 20 tanesiyle dene
    python src/extract.py --model claude-haiku-4-5-20251001
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import anthropic
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
PROMPT_PATH = ROOT / "prompts" / "extraction.md"

DEFAULT_MODEL = "claude-sonnet-4-6"

# 1M token başına USD. Güncel fiyatlar için: https://claude.com/pricing
# Buradaki değerler sadece kabaca maliyet raporu üretmek için.
PRICES = {
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
}

EXTRACT_TOOL = {
    "name": "extract_job",
    "description": "Record the structured fields extracted from a job posting.",
    "input_schema": {
        "type": "object",
        "properties": {
            "is_technical": {
                "type": "boolean",
                "description": "True if this is a technical/engineering role.",
            },
            "skills": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Lowercase, normalised skill names explicitly required.",
            },
            "seniority": {
                "type": "string",
                "enum": ["intern", "junior", "mid", "senior", "lead", "unspecified"],
            },
            "years_required": {
                "type": ["integer", "null"],
                "description": "Minimum years of experience explicitly stated, else null.",
            },
            "work_mode": {
                "type": "string",
                "enum": ["remote", "hybrid", "onsite", "unspecified"],
            },
            "location_note": {
                "type": ["string", "null"],
                "description": "Stated geographic restriction, else null.",
            },
            "role_family": {
                "type": "string",
                "description": "Short role category, e.g. 'backend', 'data', 'devops', 'design'.",
            },
        },
        "required": [
            "is_technical",
            "skills",
            "seniority",
            "years_required",
            "work_mode",
            "location_note",
            "role_family",
        ],
    },
}


def load_prompt() -> tuple[str, str]:
    """prompts/extraction.md içinden SYSTEM ve USER bölümlerini ayırır."""
    text = PROMPT_PATH.read_text(encoding="utf-8")
    system = re.search(r"## SYSTEM\n(.*?)\n## USER", text, re.S)
    user = re.search(r"## USER\n(.*)$", text, re.S)
    if not system or not user:
        raise RuntimeError("prompts/extraction.md içinde ## SYSTEM ve ## USER bölümleri yok")
    return system.group(1).strip(), user.group(1).strip()


def render(template: str, job: dict, max_chars: int) -> str:
    return (
        template.replace("{{position}}", job["position"])
        .replace("{{company}}", job["company"])
        .replace("{{tags}}", ", ".join(job.get("tags", [])))
        .replace("{{location}}", job.get("location") or "unspecified")
        .replace("{{description}}", job["description"][:max_chars])
    )


class Usage:
    """Thread-safe token sayacı."""

    def __init__(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0
        self._lock = threading.Lock()

    def add(self, usage) -> None:
        with self._lock:
            self.input_tokens += usage.input_tokens
            self.output_tokens += usage.output_tokens

    def cost(self, model: str) -> float | None:
        price = PRICES.get(model)
        if not price:
            return None
        return (
            self.input_tokens / 1_000_000 * price["input"]
            + self.output_tokens / 1_000_000 * price["output"]
        )


def extract_one(
    client: anthropic.Anthropic,
    job: dict,
    system: str,
    user_template: str,
    model: str,
    usage: Usage,
    max_chars: int,
    retries: int = 4,
) -> dict | None:
    prompt = render(user_template, job, max_chars)

    for attempt in range(retries):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=1000,
                system=system,
                tools=[EXTRACT_TOOL],
                tool_choice={"type": "tool", "name": "extract_job"},
                messages=[{"role": "user", "content": prompt}],
            )
            usage.add(response.usage)

            for block in response.content:
                if block.type == "tool_use":
                    return {
                        "id": job["id"],
                        "position": job["position"],
                        "company": job["company"],
                        "url": job["url"],
                        "salary_min": job.get("salary_min"),
                        "salary_max": job.get("salary_max"),
                        "remoteok_tags": job.get("tags", []),
                        **block.input,
                    }
            print(f"  ! {job['id']}: tool_use bloğu dönmedi")
            return None

        except (anthropic.RateLimitError, anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
            if attempt == retries - 1:
                print(f"  ! {job['id']}: {type(exc).__name__} — pas geçildi")
                return None
            wait = 2**attempt + random.random()
            time.sleep(wait)
    return None


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Claude ile ilan çıkarımı")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--limit", type=int, default=None, help="sadece ilk N ilanı işle")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-chars", type=int, default=6000, help="ilan metni kırpma sınırı")
    parser.add_argument("--force", action="store_true", help="mevcut çıktıyı yok say, baştan işle")
    args = parser.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY yok. .env dosyasına ekle (.env.example'a bak).")

    raw_path = DATA_DIR / "raw_jobs.json"
    if not raw_path.exists():
        raise SystemExit("data/raw_jobs.json yok. Önce: python src/fetch_jobs.py")

    jobs = json.loads(raw_path.read_text(encoding="utf-8"))["jobs"]

    out_path = DATA_DIR / "extracted.json"
    done: dict[str, dict] = {}
    if out_path.exists() and not args.force:
        done = {row["id"]: row for row in json.loads(out_path.read_text(encoding="utf-8"))}
        print(f"{len(done)} ilan zaten işlenmiş, atlanıyor")

    todo = [job for job in jobs if job["id"] not in done]
    if args.limit:
        todo = todo[: args.limit]

    if not todo:
        print("İşlenecek yeni ilan yok.")
        return

    print(f"{len(todo)} ilan işlenecek — model: {args.model}")

    system, user_template = load_prompt()
    client = anthropic.Anthropic()
    usage = Usage()
    started = time.time()

    def work(item: tuple[int, dict]) -> dict | None:
        index, job = item
        result = extract_one(
            client, job, system, user_template, args.model, usage, args.max_chars
        )
        if result:
            print(f"  [{index + 1}/{len(todo)}] {job['position'][:48]} -> {len(result['skills'])} beceri")
        return result

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(work, enumerate(todo)))

    for row in results:
        if row:
            done[row["id"]] = row

    out_path.write_text(
        json.dumps(list(done.values()), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    elapsed = time.time() - started
    cost = usage.cost(args.model)
    print("\n--- özet ---")
    print(f"toplam kayıt      : {len(done)}")
    print(f"bu çalıştırmada   : {sum(1 for r in results if r)} / {len(todo)}")
    print(f"süre              : {elapsed:.0f} sn")
    print(f"input token       : {usage.input_tokens:,}")
    print(f"output token      : {usage.output_tokens:,}")
    if cost is not None:
        print(f"tahmini maliyet   : ${cost:.3f}  (ilan başına ${cost / max(len(todo), 1):.4f})")
    print(f"yazıldı -> {out_path}")


if __name__ == "__main__":
    main()
