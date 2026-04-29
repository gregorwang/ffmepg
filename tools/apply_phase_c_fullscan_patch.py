from __future__ import annotations

import json
from pathlib import Path


SOURCE = Path("scratch/phase_c_model_applied_v24/all_segments.json")
TARGET = Path("scratch/phase_c_model_applied_v28/all_segments.json")


PART_PATCHES: dict[tuple[str, str], str] = {
    ("ghost-yotei-part01", "cue_00072"): "\u5341\u5175\u536b",
    ("ghost-yotei-part01", "cue_00248"): "\u6765\uff0c\u7b83\u3002",
    ("ghost-yotei-part01", "cue_00681"): "\u6211\u8bd5\u7740\u8fdb\u53bb\uff0c",
    ("ghost-yotei-part01", "cue_00697"): "\u4e09\u5927\u6050\u6016\u5206\u5b50\u91d1\u5409\u5409\u3001\u9a6c\u53e4\u4ecb\u548c\u5b97\u4e94\u90ce\u3002\u4e09\u4e2a\u6298\u78e8\u6b66\u58eb\u7684\u81f4\u547d\u4e09\u4eba\u7ec4\u3002\u6700\u540e\u4e00\u6b21\u5728\u8718\u86db\u9647\u53e3\u4e0a\u65b9\u7684\u5c71\u6d1e\u91cc\u88ab\u53d1\u73b0\u3002",
    ("ghost-yotei-part01", "cue_00704"): "\u8fd9\u7b14\u94b1\u5f88\u597d\u8d5a\u3002",
    ("ghost-yotei-part01", "cue_00754"): "\u6709\u4eba\u8d76\u65f6\u95f4\u3002",
    ("ghost-yotei-part01", "cue_00765"): "\u5bfb\u627e\u76ee\u6807",
    ("ghost-yotei-part01", "cue_00777"): "\u4f60\u8fd8\u771f\u81ea\u4ee5\u4e3a\u662f\u3002",
    ("ghost-yotei-part01", "cue_00778"): "\u5b88\u536b\uff01",
    ("ghost-yotei-part01", "cue_00854"): "\uff08\u55e2\u7b11\uff09",
    ("ghost-yotei-part01", "cue_01066"): "\u8fd8\u6709\u4f60\uff0c\u96c7\u4f6c\uff0c\u628a\u4f60\u7684\u5200\u501f\u7ed9\u6211\u4eec\u3002\u4f60\u4f1a\u5f97\u5230\u62a5\u916c\u3002",
    ("ghost-yotei-part01", "cue_01075"): "W\uff08\u6ee1\uff09",
    ("ghost-yotei-part01", "cue_01182"): "\u6211\u4eec\u53bb\u54ea\uff1f",
    ("ghost-yotei-part02", "cue_00102"): "\u4f60\u662f\u8c01\uff1f",
    ("ghost-yotei-part02", "cue_00498"): "\u4e0d\u884c\u3002",
    ("ghost-yotei-part02", "cue_00745"): "\u4e0d\u884c\u3002",
    ("ghost-yotei-part02", "cue_00777"): "\u771f\u60f3\u4e0d\u5230\u4e3a\u4ec0\u4e48\u3002",
    ("ghost-yotei-part02", "cue_00778"): "\u6211\u5f97\u6b66\u88c5\u81ea\u5df1\uff0c",
    ("ghost-yotei-part02", "cue_00854"): "\u6251\u6211\u4e00\u628a\uff0c\u6211\u62c9\u4f60\u4e0a\u6765\u3002",
    ("ghost-yotei-part02", "cue_00884"): "\u7b83\uff0c\u5728\u8fd9\u513f\u3002",
    ("ghost-yotei-part02", "cue_01066"): "\u56e0\u4e3a\u4f60\u5ba2\u6c14\u5730\u5f00\u53e3\u4e86\u2026\u2026",
    ("ghost-yotei-part03", "cue_00541"): "\u54e6\uff0c\u662f\u5417\uff1f",
    ("ghost-yotei-part03", "cue_00670"): "\u542c\u8d77\u6765\u5f88\u8fd1\u3002",
    ("ghost-yotei-part03", "cue_00777"): "\u6211\u7684\u4e09\u5473\u7ebf\u4e5f\u60f3\u5ff5\u65c5\u9014\u3002",
    ("ghost-yotei-part03", "cue_00778"): "\u4f46\u662f\uff1f",
    ("ghost-yotei-part03", "cue_00854"): "\u7a7f\u7740\u7e84\u7ea2\u548c\u670d\u7684\u90a3\u4e2a\u5973\u513f\u4e00\u5b9a\u5728\u8fd9\u513f\u5f85\u4e86\u5f88\u4e45\u3002",
    ("ghost-yotei-part03", "cue_00898"): "\u718a\u7684\u524d\u80a2\u53c8\u957f\u53c8\u6709\u529b\uff0c\u50cf\u9501\u9570\u7684\u5768\u9524\u4e00\u6837\u3002",
    ("ghost-yotei-part03", "cue_01066"): "\u5c31\u662f\u8fd9\u4e2a\uff1f",
    ("ghost-yotei-part04", "cue_00392"): "\u4f60\u77e5\u9053\u6211\u722c\u4e0a\u6765\u6709\u591a\u96be\u5417\uff1f",
    ("ghost-yotei-part04", "cue_00381"): "\u6309\u4e0b\u6309\u952e\u9009\u62e9\u4e39\u6d25\u4f4f\u63e1\u6301",
    ("ghost-yotei-part04", "cue_00622"): "\u83ca\uff0c\u7b83\u3002",
    ("ghost-yotei-part04", "cue_00805"): "\u53ea\u6709\u77e5\u9053\u53bb\u627e\u7684\u4eba\u624d\u770b\u5f97\u89c1\u3002",
    ("ghost-yotei-part04", "cue_00854"): "\uff08\u55e2\u7b11\uff09",
    ("ghost-yotei-part04", "cue_01066"): "\u7834\u5440\uff01",
    ("ghost-yotei-part04", "cue_01067"): "\u8fd9\u611f\u89c9\u5f88\u719f\u6089\uff01",
    ("ghost-yotei-part04", "cue_01111"): "\u6211\u5f88\u5feb\u5c31\u6765\u3002",
}


TEXT_PATCHES: dict[tuple[str, str], str] = {
    ("ghost-yotei-part01", "Atsu Where we going?"): "\u6211\u4eec\u53bb\u54ea\uff1f",
    ("ghost-yotei-part01", "Kengo: Jubei"): "\u5341\u5175\u536b",
    ("ghost-yotei-part01", "Atsu: Someone's in a hurry."): "\u6709\u4eba\u8d76\u65f6\u95f4\u3002",
    ("ghost-yotei-part01", "Ronin: It'll be easy money."): "\u8fd9\u7b14\u94b1\u5f88\u597d\u8d5a\u3002",
    ("ghost-yotei-part01", "Muneji: Guards!"): "\u5b88\u536b\uff01",
    ("ghost-yotei-part02", "Jubei: Give me a boost\u2014I'll pull you up."): "\u6251\u6211\u4e00\u628a\uff0c\u6211\u62c9\u4f60\u4e0a\u6765\u3002",
    ("ghost-yotei-part02", "Atsu: Can't imagine why."): "\u771f\u60f3\u4e0d\u5230\u4e3a\u4ec0\u4e48\u3002",
    ("ghost-yotei-part02", "Atsu: Need to arm myself,"): "\u6211\u5f97\u6b66\u88c5\u81ea\u5df1\uff0c",
    ("ghost-yotei-part02", "Jubei: Atsu"): "\u7b83",
    ("ghost-yotei-part02", "Jubei: Because you asked nicely..."): "\u56e0\u4e3a\u4f60\u5ba2\u6c14\u5730\u5f00\u53e3\u4e86\u2026\u2026",
    ("ghost-yotei-part02", "Atsu: No."): "\u4e0d\u884c\u3002",
    ("ghost-yotei-part02", "Ronin: Come at mel"): "\u653e\u9a6c\u8fc7\u6765\u5427\u3002",
    ("ghost-yotei-part03", "Chosuke: Oh?"): "\u54e6\uff1f",
    ("ghost-yotei-part03", "Oyuki: My shamisen does miss the road."): "\u6211\u7684\u4e09\u5473\u7ebf\u4e5f\u60f3\u5ff5\u65c5\u9014\u3002",
    ("ghost-yotei-part03", "Atsu: But?"): "\u4f46\u662f\uff1f",
    ("ghost-yotei-part03", "Atsu: This it?"): "\u5c31\u662f\u8fd9\u4e2a\uff1f",
    ("ghost-yotei-part04", "Atsu: Then lead on."): "\u90a3\u5c31\u5e26\u8def\u5427\u3002",
    ("ghost-yotei-part04", "Atsu: Show me what you've got."): "\u8ba9\u6211\u770b\u770b\u4f60\u7684\u672c\u4e8b\u3002",
    ("ghost-yotei-part04", "Atsu: (Laughs) Uh, no."): "\uff08\u7b11\uff09\u5475\uff0c\u4e0d\u3002",
    ("ghost-yotei-part04", "Kiku: Please?"): "\u6c42\u4f60\u4e86\uff1f",
    ("ghost-yotei-part04", "Atsu: Fine."): "\u597d\u5427\u3002",
    ("ghost-yotei-part04", "Jubei: Bo-hiya!"): "\u6ce2\u706b\u5440\uff01",
}


def main() -> None:
    obj = json.loads(SOURCE.read_text(encoding="utf-8"))
    for seg in obj["segments"]:
        part = str(seg.get("part_name") or "")
        cue = str(seg.get("english_cue_id") or "")
        text = str(seg.get("english_text") or "")
        key = (part, cue)
        if key in PART_PATCHES:
            seg["chinese_text"] = PART_PATCHES[key]
            continue
        key2 = (part, text)
        if key2 in TEXT_PATCHES:
            seg["chinese_text"] = TEXT_PATCHES[key2]
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {TARGET}")


if __name__ == "__main__":
    main()
