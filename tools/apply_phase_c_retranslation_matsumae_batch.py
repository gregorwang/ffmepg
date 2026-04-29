from __future__ import annotations

import json
import requests
from pathlib import Path


SOURCE = Path("scratch/phase_c_model_applied_v30/all_segments.json")
TARGET = Path("scratch/phase_c_model_applied_v31/all_segments.json")


def clean_translation(text: str) -> str:
    zh = (text or "").strip()
    if zh.startswith("松前："):
        zh = "松前家：" + zh[len("松前：") :]
    return zh


def translate_text(text: str) -> str:
    url = "https://api.mymemory.translated.net/get"
    params = {"q": text, "langpair": "en|zh-CN"}
    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    payload = resp.json()
    return str(payload.get("responseData", {}).get("translatedText") or "")


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
    for src in unique_texts:
        try:
            translated[src] = clean_translation(translate_text(src))
        except Exception:
            translated[src] = ""

    # Apply translations to all Matsumae speaker rows.
    for seg in segments:
        en = str(seg.get("english_text") or "").strip()
        if en.startswith("Matsumae:") and en in translated:
            if translated[en]:
                seg["chinese_text"] = translated[en]

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {TARGET}")
    print(f"translated_rows={len(translated)}")


if __name__ == "__main__":
    main()
