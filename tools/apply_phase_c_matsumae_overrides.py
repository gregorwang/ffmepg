from __future__ import annotations

import json
import re
from pathlib import Path


SOURCE = Path("scratch/phase_c_model_applied_v32/all_segments.json")
TARGET = Path("scratch/phase_c_model_applied_v34/all_segments.json")


OVERRIDES: dict[str, str] = {
    "Matsumae: I need a drink.": "松前家：我得喝一杯。",
    "Matsumae: A mercenary.": "松前家：佣兵。",
    "Matsumae: Are you for hire?": "松前家：你接活吗？",
    "Matsumae: It's for the good of Ezo.": "松前家：这是为了虾夷的利益。",
    "Matsumae: A spyglass.": "松前家：望远镜。",
    "Matsumae: I haven't seen one of these since the Portuguese.": "松前家：自从葡萄牙人之后，我就没见过这东西了。",
    "Matsumae: Quite the sword you have there.": "松前家：你那把剑真不错。",
    "Matsumae: Been on the road for a while?": "松前家：赶路很久了吧？",
    "Matsumae: Maybe you should visit the hot spring nearby.": "松前家：你也许该去附近的温泉泡泡。",
    "Matsumae: Stay back, stranger.": "松前家：退后，陌生人。",
    "Matsumae: Good hunting": "松前家：狩猎顺利。",
    "Matsumae: Halt!": "松前家：站住！",
    "Matsumae: Open the gates!": "松前家：打开城门！",
    "Matsumae: Follow me.": "松前家：跟我来。",
    "Matsumae: Dismissed.": "松前家：解散。",
    "Matsumae: Thank you.": "松前家：谢谢。",
    "Matsumae: Take care.": "松前家：保重。",
    "Matsumae: Wait here.": "松前家：在这里等着。",
    "Matsumae: I should get back to my garrison now.": "松前家：我该回营地了。",
    "Matsumae: I was wondering who the stray was.": "松前家：我还在想是谁在这儿晃荡。",
    "Matsumae: I'm not sure this 'Kitsune' even exists.": "松前家：我甚至不确定这个“狐狸”是否真的存在。",
    "Matsumae: Are you Atsu?": "松前家：你是笃吗？",
    "Matsumae: You have the look of someone who trains often.": "松前家：你看起来经常训练。",
    "Matsumae: The woman bounty hunter—": "松前家：那个女赏金猎人——",
    "Matsumae: The woman herself.": "松前家：就是那个女人。",
    "Matsumae: That woman is not welcome here.": "松前家：那个女人不受欢迎。",
    "Matsumae: We can't let them spot us!": "松前家：不能让他们发现我们！",
    "Matsumae: We fight the way Matsumae have always fought. Our blades will win the day.": "松前家向来就是这么战斗的。我们的刀会赢下今天。",
    "Matsumae: They are undisciplined,": "松前家：他们毫无纪律，",
    "Matsumae: but ruthless.": "松前家：但很残忍。",
    "Matsumae: He said nothing": "松前家：他什么也没说。",
    "Matsumae: Nothing!": "松前家：什么都没有！",
    "Matsumae: A moment, please!": "松前家：请稍等！",
    "Matsumae: This area is restrict—": "松前家：这个区域禁止通行——",
    "Matsumae: The Matsumae are not sloppy!": "松前家：松前家可不马虎！",
    "Matsumae: I need to verify its authenticity.": "松前家：我得确认它的真伪。",
    "Matsumae: We held us for ransom.": "松前家：他们把我们扣作赎金。",
    "Matsumae: The odachi weighs more than she does.": "松前家：这把大太刀比她还重。",
    "Matsumae: Our new'student thinks she can best Master Yoshida": "松前家：我们的新学生以为她能打败吉田师父。",
    "Matsumae: There's a group on their way now. 7": "松前家：现在有一群人正赶过来。",
}


def normalize_label(text: str) -> str:
    zh = (text or "").strip()
    zh = re.sub(r"^(?:Matsumae|松前)[：:\s]+", "松前家：", zh)
    zh = re.sub(r"\s+：", "：", zh)
    zh = re.sub(r"：\s+", "：", zh)
    zh = re.sub(r"\s{2,}", " ", zh)
    return zh


def main() -> None:
    obj = json.loads(SOURCE.read_text(encoding="utf-8"))
    for seg in obj["segments"]:
        en = str(seg.get("english_text") or "").strip()
        if en in OVERRIDES:
            seg["chinese_text"] = OVERRIDES[en]
        elif en.startswith("Matsumae:"):
            seg["chinese_text"] = normalize_label(str(seg.get("chinese_text") or ""))
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {TARGET}")


if __name__ == "__main__":
    main()
