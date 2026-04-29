from __future__ import annotations

import json
import re
from pathlib import Path


SOURCE = Path("scratch/phase_c_model_applied_v28/all_segments.json")
TARGET = Path("scratch/phase_c_model_applied_v30/all_segments.json")


PATCHES: dict[tuple[str, str], str] = {
    ("ghost-yotei-part01", "cue_00307"): "为什么不干脆让那个老残废在羊蹄山上烂掉？",
    ("ghost-yotei-part01", "cue_00492"): "别喝太多。要是斋藤的人回来了怎么办？",
    ("ghost-yotei-part01", "cue_00634"): "连斋藤都不敢碰它。",
    ("ghost-yotei-part01", "cue_00649"): "他们占了离这儿不远的一个狩猎营地。",
    ("ghost-yotei-part01", "cue_00740"): "因为你一直抱怨个不停。",
    ("ghost-yotei-part01", "cue_00752"): "别管我，小家伙。",
    ("ghost-yotei-part01", "cue_00789"): "我是不可能活着离开这里的，对吧？",
    ("ghost-yotei-part01", "cue_00851"): "不可能是真的。",
    ("ghost-yotei-part01", "cue_00906"): "松前家。她撑不过今天。",
    ("ghost-yotei-part01", "cue_01041"): "我们为什么不一起上？",
    ("ghost-yotei-part01", "cue_01145"): "让我们过去！……我们还以为最糟的情况发生了。",
    ("ghost-yotei-part01", "cue_01152"): "……如果不是鬼面队一直偷我们的木材。",
    ("ghost-yotei-part01", "cue_01163"): "另外五个人没能回来。",

    ("ghost-yotei-part02", "cue_00009"): "为什么帮我？……松前家在这儿可不怎么受欢迎。",
    ("ghost-yotei-part02", "cue_00123"): "我们什么时候对松前家动手？",
    ("ghost-yotei-part02", "cue_00129"): "一旦见血，就不会停下……",
    ("ghost-yotei-part02", "cue_00138"): "斋藤大人从未在决斗中输过……",
    ("ghost-yotei-part02", "cue_00139"): "我不在乎手下从哪来，父亲是谁，或者他们胯下那点事。",
    ("ghost-yotei-part02", "cue_00148"): "那对你不公平，也会让我这个武士显得太小气。",
    ("ghost-yotei-part02", "cue_00241"): "你没从他的坟里把它偷出来吧？",
    ("ghost-yotei-part02", "cue_00263"): "我会后悔这么做，对吧？",
    ("ghost-yotei-part02", "cue_00300"): "你身上的谜团还真不少，不是吗？",
    ("ghost-yotei-part02", "cue_00406"): "闻起来像机会，不是吗？",
    ("ghost-yotei-part02", "cue_00409"): "他不会让任何人打断石狩城的木材运输。",
    ("ghost-yotei-part02", "cue_00482"): "我就知道松前家不会抛下我们。",
    ("ghost-yotei-part02", "cue_00638"): "我永远想不明白，松前家为什么要租下这个地方。",
    ("ghost-yotei-part02", "cue_00836"): "这根本过不去。现在怎么办？",
    ("ghost-yotei-part02", "cue_00895"): "松前家不会把人活活烧死，也不会把人累死。",
    ("ghost-yotei-part02", "cue_01009"): "我们问错问题了。",
    ("ghost-yotei-part02", "cue_01134"): "难道不能让往事就这么过去吗？",

    ("ghost-yotei-part03", "cue_00152"): "你听说了吗？……有人把三吉从贼窝里救出来了。",
    ("ghost-yotei-part03", "cue_00214"): "想要弓吗？找我就对了。",
    ("ghost-yotei-part03", "cue_00304"): "这不行。",
    ("ghost-yotei-part03", "cue_00321"): "你来替我，但小心点……",
    ("ghost-yotei-part03", "cue_00338"): "她不是人。",
    ("ghost-yotei-part03", "cue_00395"): "你不是九尾的人，对吧？",
    ("ghost-yotei-part03", "cue_00482"): "你想找狐狸的老巢，对吧？",
    ("ghost-yotei-part03", "cue_00489"): "你接活前都不先查清楚雇主吗？",
    ("ghost-yotei-part03", "cue_00534"): "怎么了？",
    ("ghost-yotei-part03", "cue_00549"): "他不会死吧？",
    ("ghost-yotei-part03", "cue_00630"): "你没见过穿山箭吧？",
    ("ghost-yotei-part03", "cue_00719"): "那个女人不受欢迎。",
    ("ghost-yotei-part03", "cue_00915"): "要是我的敌人没有盾呢？",
    ("ghost-yotei-part03", "cue_00944"): "我们难道不该待在里面吗？",
    ("ghost-yotei-part03", "cue_00956"): "这股寒意不会让你变慢吗？",
    ("ghost-yotei-part03", "cue_01160"): "了结这件事帮不了我杀斋藤。",
    ("ghost-yotei-part03", "cue_01220"): "那为什么不直接杀了你？",
    ("ghost-yotei-part03", "cue_01231"): "为什么道俊从没在红鹤客栈试着袭击你？",
    ("ghost-yotei-part03", "cue_01235"): "松前家的存在给了道俊一个完美借口，让他不敢明着动手，",

    ("ghost-yotei-part04", "cue_00045"): "他们不会被斋藤所谓的乌合之众军队打败。",
    ("ghost-yotei-part04", "cue_00117"): "撤去城堡。这里不安全。",
    ("ghost-yotei-part04", "cue_00128"): "而且毫无武士道可言。他们的武器从远处杀人，不分目标。",
    ("ghost-yotei-part04", "cue_00208"): "你又在捣什么鬼，菊？",
    ("ghost-yotei-part04", "cue_00523"): "没想到他居然还会在乎别人。",
    ("ghost-yotei-part04", "cue_00566"): "……这样就更难把他们击落了。我们不会让这种事发生。",
    ("ghost-yotei-part04", "cue_00571"): "事情不是这么办的。",
    ("ghost-yotei-part04", "cue_00603"): "你杀人时不会觉得难受吗？",
    ("ghost-yotei-part04", "cue_00604"): "要是他们杀了我也不会觉得难受。我只是更快一步。",
    ("ghost-yotei-part04", "cue_00725"): "小心脚下，路很滑。",
    ("ghost-yotei-part04", "cue_00726"): "跟下雨时城墙一样滑。",
    ("ghost-yotei-part04", "cue_00853"): "我本想反驳，但跟死人没什么好说的。",
    ("ghost-yotei-part04", "cue_00875"): "不能让他们发现我们！",
}


MATSUMAE_CASTLE_RE = re.compile(r"松前(?!城)")


def normalize_matsumae(english_text: str, chinese_text: str) -> str:
    text = (english_text or "")
    zh = (chinese_text or "").strip()
    if "Matsumae Castle" in text:
        return zh
    if "Matsumae" not in text:
        return zh
    if "松前" in zh and "松前家" not in zh:
        zh = MATSUMAE_CASTLE_RE.sub("松前家", zh)
    return zh


def main() -> None:
    obj = json.loads(SOURCE.read_text(encoding="utf-8"))
    for seg in obj["segments"]:
        part = str(seg.get("part_name") or "")
        cue = str(seg.get("english_cue_id") or "")
        english_text = str(seg.get("english_text") or "")
        key = (part, cue)
        if key in PATCHES:
            seg["chinese_text"] = PATCHES[key]
        seg["chinese_text"] = normalize_matsumae(english_text, str(seg.get("chinese_text") or ""))

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {TARGET}")


if __name__ == "__main__":
    main()
