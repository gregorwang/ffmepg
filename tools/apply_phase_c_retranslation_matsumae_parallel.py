from __future__ import annotations

import concurrent.futures as cf
import json
from pathlib import Path

import requests


SOURCE = Path("scratch/phase_c_model_applied_v30/all_segments.json")
TARGET = Path("scratch/phase_c_model_applied_v32/all_segments.json")


def clean_translation(text: str) -> str:
    zh = (text or "").strip()
    if zh.startswith("松前："):
        zh = "松前家：" + zh[len("松前：") :]
    return zh


def translate_text(text: str) -> str:
    url = "https://api.mymemory.translated.net/get"
    params = {"q": text, "langpair": "en|zh-CN"}
    resp = requests.get(url, params=params, timeout=8)
    resp.raise_for_status()
    payload = resp.json()
    return clean_translation(str(payload.get("responseData", {}).get("translatedText") or ""))


def main() -> None:
    obj = json.loads(SOURCE.read_text(encoding="utf-8"))
    segments = obj["segments"]

    unique_texts: list[str] = []
    seen: set[str] = set()
    for seg in segments:
        en = str(seg.get("english_text") or "").strip()
        if en.startswith("Matsumae:") and en not in seen:
            seen.add(en)
            unique_texts.append(en)

    translated: dict[str, str] = {}
    workers = 8
    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {pool.submit(translate_text, text): text for text in unique_texts}
        done_count = 0
        for future in cf.as_completed(future_map):
            src = future_map[future]
            try:
                translated[src] = future.result()
            except Exception:
                translated[src] = ""
            done_count += 1
            if done_count % 20 == 0 or done_count == len(unique_texts):
                print(f"translated {done_count}/{len(unique_texts)}")

    for seg in segments:
        en = str(seg.get("english_text") or "").strip()
        if en.startswith("Matsumae:") and translated.get(en):
            seg["chinese_text"] = translated[en]

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {TARGET}")
    print(f"translated_rows={len(translated)}")


if __name__ == "__main__":
    main()
