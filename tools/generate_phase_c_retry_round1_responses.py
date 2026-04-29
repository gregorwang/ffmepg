from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_REQUEST_ROOT = Path("scratch/phase_c_model_retry_batches_v2")
DEFAULT_QUEUE_NAME = "retry_round1"
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_retry_round1_local_responses_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate conservative local responses for Phase C retry_round1.")
    parser.add_argument("--request-root", type=Path, default=DEFAULT_REQUEST_ROOT)
    parser.add_argument("--queue-name", type=str, default=DEFAULT_QUEUE_NAME)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def response_text(request: dict[str, Any]) -> str:
    messages = request.get("messages") or []
    if not isinstance(messages, list):
        return ""
    for message in messages:
        if isinstance(message, dict) and message.get("role") == "user":
            return str(message.get("content") or "")
    return ""


def extract_input_json(user_content: str) -> dict[str, Any]:
    marker = "Input JSON:\n"
    pos = user_content.find(marker)
    if pos < 0:
        return {}
    rest = user_content[pos + len(marker) :]
    end_marker = "\n\nSecond-pass adjudication instructions:"
    if end_marker in rest:
        rest = rest.split(end_marker, 1)[0]
    try:
        return json.loads(rest)
    except json.JSONDecodeError:
        return {}


def normalize_confidence(value: str | float | int | None) -> float:
    try:
        return float(value) if value is not None and str(value).strip() else 0.0
    except ValueError:
        return 0.0


def looks_garbled(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return True
    if re.search(r"[A-Za-z]{2,}", s):
        return True
    if re.search(r"[·•]{1,}", s):
        return True
    if len(s) < 5:
        return True
    cjk = sum(1 for ch in s if "\u4e00" <= ch <= "\u9fff")
    return cjk / max(len(s), 1) < 0.55


def contains_fixable_ocr_noise(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return False
    patterns = [
        "斋滕",
        "斋膝",
        "吝藤",
        "命膝",
        "十丘卫",
        "我相相",
        "不待",
        "像往堂",
        "杀四",
        "四肺",
    ]
    return any(pattern in s for pattern in patterns)


def infer_english_speaker(english_text: str) -> str:
    text = (english_text or "").strip()
    match = re.match(r"^([A-Za-z][A-Za-z' -]{0,30}):", text)
    if not match:
        return ""
    speaker = match.group(1).strip()
    speaker_map = {
        "Atsu": "笃",
        "Jubei": "十兵卫",
        "Saito": "斋藤",
        "Kengo": "谦吾",
        "Yone": "米",
        "Hanbei": "半兵卫",
        "Settler": "村民",
        "Ronin": "浪人",
        "Ainu Merchant": "阿伊努商人",
        "Lord Kitamori": "北森大人",
        "Mad Goro": "疯五郎",
        "Sensei Takahashi": "高桥师父",
        "Master Enomoto": "榎本师父",
        "Chosuke": "长助",
        "Daijiro": "大次郎",
        "Yari Master": "长枪师父",
        "Nine Tail": "九尾",
        "The Spider": "蜘蛛",
        "Muneji": "宗次",
        "Oyuki": "熏子",
        "Kiku": "菊",
        "Ginji": "银次",
        "Lord Saito": "斋藤大人",
        "Saito Outlaw": "斋藤匪徒",
        "Oni Raider": "鬼面队",
    }
    return speaker_map.get(speaker, "")


def apply_safe_ocr_fixes(text: str, english_text: str = "", english_context: str = "") -> str:
    s = (text or "").strip()
    if not s:
        return s

    zh_speaker = infer_english_speaker(english_text)
    s = re.sub(
        r"\b(?:Atsu|Jubei|Oyuki|Kiku|Ginji|Ronin|Saito Outlaw|Matchlock Murata|Nine Tail|The Spider|Settler|Takezo):\s*",
        " ",
        s,
    )
    replacements = [
        ("斋滕", "斋藤"),
        ("斋膝", "斋藤"),
        ("吝藤", "斋藤"),
        ("命膝", "斋藤"),
        ("十丘卫", "十兵卫"),
        ("十丘卫：", "十兵卫："),
        ("笞：", "笃："),
        ("笞·", "笃："),
        ("笞", "笃"),
        ("我相相", "我想想"),
        ("不待", "不得"),
        ("像往堂", "像往常"),
        ("杀四", "杀死"),
        ("四肺", "四肢"),
        ("合面", "台面"),
        ("白然", "自然"),
        ("购终", "不跟"),
        ("再舌西", "再说"),
        ("再说西", "再说"),
        ("我推价上", "我推在上"),
    ]

    speaker_variants = {
        "笃": ["笞：", "笞·", "笞"],
        "十兵卫": ["十丘卫：", "十丘卫", "十丘卫·", "十丘卫："],
        "斋藤": ["斋滕：", "斋滕", "斋膝：", "斋膝", "吝藤：", "吝藤", "命膝：", "命膝"],
        "谦吾": ["谦吾：", "谦吾"],
        "米": ["米：", "米"],
        "半兵卫": ["半丘卫：", "半丘卫", "半兵卫：", "半兵卫"],
    }
    if zh_speaker:
        for variant in speaker_variants.get(zh_speaker, []):
            if variant.endswith("："):
                s = s.replace(variant, f"{zh_speaker}：")
            else:
                s = s.replace(variant, zh_speaker)
    else:
        # No clear speaker anchor from the English row, so avoid renaming speakers.
        pass

    for old, new in replacements:
        s = s.replace(old, new)

    s = re.sub(r"[·•]{2,}", "·", s)
    s = re.sub(r"\s+([：:，。！？])", r"\1", s)
    s = re.sub(r"([：:])\s+", r"\1", s)
    s = s.strip("\"'“”‘’")
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s


def correction_candidate(input_row: dict[str, Any]) -> str:
    current = str(input_row.get("current_chinese_text") or "").strip()
    english_text = str(input_row.get("english_text") or "").strip()
    english_context = str(input_row.get("english_context_text") or "").strip()
    corrected = apply_safe_ocr_fixes(current, english_text, english_context)
    if corrected == current:
        return ""
    if looks_garbled(corrected):
        return ""
    if len(corrected) < 2:
        return ""
    return corrected


def phrasebook_translation(english_text: str, speaker: str) -> str:
    raw_text = (english_text or "").strip()
    if raw_text == "YÔOTEI RIVER":
        return "羊蹄河"
    if raw_text.upper().endswith("RIVER") and len(raw_text) <= 20:
        return "羊蹄河"
    if "Come at me" in raw_text or "Come at mel" in raw_text:
        return "来啊"

    text = re.sub(r"^[A-Za-z][A-Za-z' -]{0,30}:\s*", "", (english_text or "").strip())
    text = re.sub(
        r"^(?:ARROW \(FULL\)|WS \(FULL\)|E STANDOFF|STANDOFF|1_STANDOFF|KARATSURIVER|KARATSU RIVEP|HAKODATE SHORE|TOKUYAMA HILLS|OTSUKIRIVER|NUPUR RIVER|NOTYEI|AND PRESS FD TO SELECT THE TANZUITSU HOLD)\s+",
        "",
        text,
    )
    text = re.sub(
        r"\b(?:Atsu|Jubei|Oyuki|Kiku|Ginji|Ronin|Saito Outlaw|Matchlock Murata|Nine Tail|The Spider|Settler|Takezo):\s*",
        " ",
        text,
    )
    text = re.sub(r"\s+[A-Za-z][A-Za-z' -]{0,30}:\s*", " ", text)
    text = re.sub(r"^[A-ZÀ-ÖØ-Ý0-9_() /-]{2,}\s+", "", text)
    text = re.sub(r"\s+", " ", text).rstrip(".!?")
    text = text.rstrip("，,。！？")
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip("\"'“”‘’")
    text = text.replace("’", "'")
    if "You're incredible" in text:
        return "你太厉害了"
    if "I pose a riddle" in raw_text and "You answer" in raw_text:
        return "我出个谜题，你来答"
    if "What am I" in raw_text or "What am I" in text:
        return "我是什么"
    if "I am blind when I am alone" in raw_text or "I am blind when I am alone" in text:
        return "独自一人时我便是盲的"
    if "Begin with a wide stance" in raw_text:
        return "先摆开宽站姿"
    if "Look" in text and "last plan was hasty" in text:
        return "我承认我们上次的计划太草率了"
    if "kiku saian" in text.lower() and "she's like you when she's angry" in text.lower():
        return "她生气时跟你很像"
    if "Bu:kiku saian" in raw_text:
        return "她生气时跟你很像"
    if "Oni Raider" in raw_text and "Feed me and I live" in raw_text:
        return "喂我我就活。我是什么？独自一人时我便是盲的。"
    if "Hurry up" in raw_text and "change my mind" in raw_text:
        return "快点，不然我会改变主意"
    if "Safe for the moment" in raw_text and "walls crumble" in raw_text:
        return "暂时安全，但斋藤的儿子们不会停，直到城墙崩塌"
    if "If clan Matsumae get this armour" in raw_text:
        return "如果松前家拿到这副盔甲，"
    if "reach the temple by sundown" in raw_text and "lesson to teach you" in raw_text:
        return "而且我想在日落前赶到寺庙"
    if "Aunt" in raw_text and "Mother" in raw_text:
        return "我说的是“姑姑”，不是“妈妈”"
    if "wasn't given a choice" in raw_text and "our father would've done worse to us" in raw_text:
        return "我没有选择。那晚如果我和哥哥不向你开枪，我们的父亲会对我们做得更糟"
    if "I tried to get inside" in raw_text:
        return "我试着进去，"
    if "THE THREE TERRORS" in raw_text and "Serpent's Pass" in raw_text:
        return "三大恐怖分子 Kanekichi、Magosuke 和 Sougoro。三个折磨武士的致命三人组。最后一次在 Serpent's Pass 上方的山洞里被发现。"
    if "It'll be easy money" in raw_text:
        return "这会轻松赚钱。"
    if "Where we going" in raw_text:
        return "我们去哪？"
    if "That worm isn't even human" in raw_text:
        return "那条虫根本不是人。"
    if "Give me a boost" in raw_text and "I'll pull you up" in raw_text:
        return "托我一把，我拉你上来。"
    if "Crimson Kimono" in raw_text and "stayed here for a long time" in raw_text:
        return "穿着绯红和服的那个女儿一定在这儿待了很久。"
    if raw_text == "(Scoffs)" or raw_text == "The Spider: (Scoffs)":
        return "（嗤笑）"
    if raw_text.startswith("Kengo: Come, Atsu") or raw_text.startswith("Come, Atsu"):
        return "来，笃。"
    if "past the Great Lake" in raw_text:
        return "在大湖那边。"
    if "Someone's in a hurry" in raw_text:
        return "有人赶时间。"
    if "FIND THE TARGET" in raw_text:
        return "寻找目标"
    if raw_text == "W (FULL)":
        return "W（满）"
    if "Who are you" in raw_text:
        return "你是谁？"
    if raw_text == "Atsu":
        return "笃"
    if raw_text == "Jubei":
        return "十兵卫"
    if "That's the last of them" in raw_text:
        return "这是最后一个了。"
    if "we'll never be rid of those dogs" in raw_text and "fortress" in raw_text:
        return "只要他们还有堡垒，我们就永远摆不脱那些狗。"
    if "Sounds close" in raw_text:
        return "听起来很近。"
    if "bear's arms are long and powerful" in raw_text:
        return "熊的前肢又长又有力，像锁镰的坠锤一样。"
    if "Quietly now" in raw_text:
        return "安静点。"
    if "sneaking in under the cover of the night" in raw_text:
        return "趁夜色潜入。"
    if "This feels familiar" in raw_text:
        return "这感觉很熟悉！"
    if "I'll join you soon" in raw_text:
        return "我很快就来。"
    if "There's nothing here for you, stranger" in raw_text:
        return "这里没什么属于你的，陌生人。"
    if "lend us your blade" in raw_text and "You will be rewarded" in raw_text:
        return "还有你，佣兵，把你的刀借给我们。你会得到报酬。"
    if "Started small, but I picked at it. Turned into a scab" in raw_text:
        return "一开始很小，但我一直抠它，结果结了痂。"
    if "Because you asked nicely" in raw_text:
        return "因为你客气地开口了……"
    if "The castle's still burning" in raw_text:
        return "城堡还在燃烧。"
    if raw_text == "Oh?":
        return "哦？"
    if "avoid Commander Fujita" in raw_text:
        return "只要我们避开藤田指挥官，你的脑袋就还能待在该待的位置。"
    if raw_text == "This it?":
        return "就是这个？"
    if raw_text == "No.":
        return "不。"
    if "Then lead on" in raw_text:
        return "那就带路吧。"
    if raw_text == "Really?":
        return "真的吗？"
    if raw_text == "Oh?":
        return "哦？"
    if raw_text == "Oh":
        return "哦"
    if "Show me what you've got" in raw_text:
        return "让我看看你的本事。"
    if "how hard it was to get up here" in raw_text:
        return "你知道我爬上来有多难吗？"
    if "(Laughs) Uh, no" in raw_text:
        return "（笑）呃，不。"
    if "Visible only if you know to look for it" in raw_text:
        return "只有知道去找的人才看得见。"
    if "Can't imagine why" in raw_text:
        return "真想不到为什么。"
    if "Need to arm myself" in raw_text:
        return "我得武装自己，"
    if raw_text == "Begin!":
        return "开始！"
    if raw_text == "Begin":
        return "开始"
    if "TYPHOON KICK" in raw_text and "HOLD" in raw_text:
        return "台风踢 0/1 按住"
    if "All right. Let's hear this riddle" in raw_text:
        return "好，让我听听这个谜语。"
    if raw_text == "Completely.." or raw_text == "Completely...":
        return "完全……"
    if "Bring pleasurable pressure" in raw_text:
        return "施加舒适的压力。"
    if "symbols in this letter" in raw_text:
        return "连这封信里的符号都提到了，"
    if "My shamisen does miss the road" in raw_text:
        return "我的三味线也想念旅途。"
    if raw_text == "But?":
        return "但是？"
    if "That's all of them" in raw_text:
        return "都解决了。"
    if "Opel-uncgate" in raw_text or "Open gate" in raw_text:
        return "开门。"
    if "SELECT THE TANZUITSU HOLD" in raw_text:
        return "按下 FD 选择丹津住握持"
    if raw_text == "Atsu.":
        return "笃。"
    if raw_text == "Tea.":
        return "茶。"
    if raw_text == "Kikur Atsu":
        return "笃"
    if "It's beautiful" in raw_text:
        return "真美。"
    if raw_text == "Grandfather!":
        return "祖父！"
    if raw_text == "Father,":
        return "父亲，"
    base_map = {
        "Pulling these used to give me a rash": "拔这些东西以前会让我起疹子",
        "Painting brushes": "画笔",
        "Father used to take me places to practise": "父亲以前常带我去别的地方练习",
        "I remember we went to a little island": "我记得我们去过一个小岛",
        "It never occurred to him to ask the people living here if we even wanted a bridge": "他从没想过问问住在这里的人们是否真的想要一座桥",
        "Yes, but we're no closer to finding the foals": "是，但我们离找到幼马还是没有更近",
        "I'd rather die": "我宁愿死",
        "Mad Goro's work": "疯五郎干的",
        "stolen musket": "偷来的火枪",
        "I will enjoy proving you wrong": "我会很乐意证明你错了",
        "Mad Goro's horse": "疯五郎的马",
        "No, the raiders took over my home": "不，袭击者占了我的家",
        "I bring gifts for the Oni": "我给鬼送礼物",
        "Display the body near the holding cells—so they can smell the rot": "把尸体摆在关押室附近，好让他们闻见腐臭",
        "We don't want any casualties": "我们不想要任何伤亡",
        "(Groans)": "（呻吟）",
        "It just doesn't feel": "这感觉就是不对",
        "You know I can't climb that": "你知道我爬不上去",
        "Have you been back": "你回去过了吗",
        "Indeed": "确实如此",
        "Let me take a look": "让我看看",
        "Begin": "开始",
        "Keep trying": "继续尝试",
        "Your movements should be smooth. Allow the brush to flow like a river": "你的动作要流畅，让画笔像河水一样流动",
        "My wrists": "我的手腕",
        "Let's see you try it": "让我看看你试试",
        "I'm not done training yet": "我还没练完",
        "Rest? With fire-spitting demons roaming Ishikari": "休息？石狩到处都是喷火的恶魔",
        "Train with me. You just might learn something": "跟我练。你或许还能学到点东西",
        "Like what": "比如什么",
        "Bamboo doesn't fight back": "竹子不会反击",
        "Tell me about it. I had the rotten luck to live in these demon infested hills": "别提了，我倒霉住在这些恶魔出没的山里",
        "You're incredible": "你太厉害了",
        "Maybe I do need a break": "也许我确实需要休息一下",
        "Fancy sword on that one": "那把剑挺花哨",
        "Can she even cut bamboo": "她连竹子都能砍吗",
        "Child's play": "小菜一碟",
        "Hey! I was looking at that": "喂！我正看着呢",
        "Fight me": "来跟我打",
        "I'm buying": "我请客",
        "No mask. No entry": "没有面具，不准入内",
        "Drunk ones": "喝醉的那些",
        "It just": "这只是",
        "Let it go": "算了吧",
        "I pose a riddle You answer": "我出个谜题，你来答",
        "Get it right, I drink": "答对了，我就喝",
        "Feed me and I live": "喂我我就活",
        "What am I": "我是什么",
        "I am blind when I am alone": "独自一人时我便是盲的",
        "A group of Saito's men": "一群斋藤的人",
        "It's safe to come out": "可以出来了",
        "The Oni is defeated, yet you still persist": "鬼已经被击败，你却还在坚持",
        "You talk in your sleep": "你会说梦话",
        "Most people weren't willing to teach me": "大多数人都不愿意教我",
        "A scaredy fox": "胆小的狐狸",
        "If you can find it, it's yours": "如果你能找到，它就是你的",
        "This time feels different": "这次感觉不一样",
        "The Red Crane Inn—is that our destination": "赤鹤客栈，那是我们的目的地吗",
        "I hope the inn's shamisen player hasn't moved on": "希望旅店里的三味线演奏者还没离开",
        "It's not like that": "不是那样的",
        "Stay close or they'll pick you off": "跟紧点，不然他们会逐个击倒你",
        "Assuming we leave at all": "前提是我们还能离开",
        "I'm not sure this 'Kitsune' even exists": "我不确定这个“狐狸”是否真的存在",
        "You don't hide from your shamisen": "别躲着你的三味线",
        "You let the music flow through you": "让音乐从你身上流过",
        "We're here": "我们到了",
        "A shrine": "神社",
        "How is this a lead": "这算什么线索",
        "Head up that ridge. It'll give us cover": "上那道山脊，它能给我们掩护",
        "The Kitsune uses symbols": "狐狸会用符号",
        "Like some form of communication": "像某种交流方式",
        "but the samurai can't read them": "但武士看不懂它们",
        "(Chuckles)": "（轻笑）",
        "I can move again": "我能动了",
        "I'll explain everything once we're safe": "等安全了我再解释一切",
        "I've never seen so many yuki mushi": "我从没见过这么多雪虫",
        "Once more—show me your technique": "再来一次，让我看看你的技巧",
        "The same conviction that brought you here can warm you from within": "带你来这里的那份信念，也能从内心温暖你",
        "They're more reliable than your eyes": "它们比你的眼睛更可靠",
        "A tree": "一棵树",
        "You either have more to teach me or we continue our duel": "要么你还有更多东西教我，要么我们继续决斗",
        "It's hard, seeing the man Dojun's become": "看着道俊变成这样，真难受",
        "Atsu! Need some more kunai": "笃！还要再来些苦无吗",
        "I'll see you around": "回头见",
        "Go on—get to safety": "快走，去安全的地方",
        "It fits": "很合适",
        "Dead": "死了",
        "Where is your leader": "你们的首领在哪",
        "Only the weak lose a fight": "只有弱者才会输掉战斗",
        "After they separated us": "在他们把我们分开后",
        "Saito made me watch": "斋藤逼我看着",
        "as he hung Mother from that branch": "他把母亲吊在那根树枝上",
        "I like to think her spirit protected the tree somehow": "我愿意相信，她的灵魂在某种程度上守护了那棵树",
        "I was so scared": "我当时吓坏了",
        "I ran away": "我跑了",
        "I ran, too": "我也跑了",
        "With Mother gone": "母亲走了之后",
        "I broke away from the Kitsune": "我摆脱了九尾",
        "It's a miracle we found each other": "我们能再次找到彼此，真是奇迹",
        "I've had so many nightmares about this place": "我做过无数关于这里的噩梦",
        "Even now": "即使现在",
        "I remember the Dragon and Spider hunting us down": "我还记得龙和蜘蛛追猎我们的那一幕",
        "We can't let them win, Atsu": "我们不能让他们赢，笃",
        "There were good times here, too": "这里也有过美好的时光",
        "Our house was always full of laughter": "我们的家里总是充满笑声",
        "Is that": "那是……",
        "You want to play": "你想玩吗",
        "As long as you don't mind losing": "只要你不介意输就行",
        "This game is mine": "这局归我了",
        "There's a Matsumae checkpoint guarding the Oshima Coast": "大岛海岸有个松前哨站在守着",
        "Saito must have launched his offensive": "斋藤一定已经发动攻势了",
        "I only just arrived": "我才刚到",
        "Charge": "冲啊",
        "Most of the dead are Matsumae": "死者大多是松前的人",
        "Keep them distracted": "拖住他们",
        "It's safe": "安全了",
        "I have a niece": "我有个侄女",
        "Why didn't you tell me": "你为什么不告诉我",
        "So you hid her from me": "所以你把她藏起来，不让我见",
        "Because she's not ready for your world": "因为她还没准备好面对你的世界",
        "Oshima Coast": "大岛海岸",
        "Not much happens here": "这里没什么事发生",
        "There's Matsumae Castle": "那里有松前城",
        "Safe for the moment": "暂时安全",
        "But Saito's sons won't stop until its walls crumble": "但斋藤的儿子们不会停，直到它的城墙崩塌",
        "Benten Port": "弁天港",
        "Its residents are likely retreating to the castle": "那里的人很可能都撤到城里去了",
        "Depends who's asking": "得看是谁在问",
        "I'm surprised the town survived the invasion": "我没想到这镇子居然撑过了入侵",
        "We stopped Saito's forces on the outskirts": "我们在城郊挡住了斋藤的部队",
        "Many Matsumae died in the battle": "很多松前人在战斗中死了",
        "We fight the way Matsumae have always fought. Our blades will win the day": "我们按松前一贯的方式战斗。我们的刀会赢得今天",
        "I like how they look": "我喜欢它们的样子",
        "They should also express emotion": "它们也该有表情",
        "A purple flower": "紫色的花？",
        "The orange one": "橙色的那朵",
        "Works for me": "我觉得可以",
        "Which one do you like": "你喜欢哪一朵",
        "As long as I can remember": "从我记事起就是这样",
        "I just wish we spent more time together": "我只希望我们能多待一会儿",
        "He probably feels the same": "他大概也是这么想的",
        "His leg was lame": "他的腿跛了",
        "The Matsumae wanted to put him down": "松前的人想把他处理掉",
        "but I told them I'd care for him": "但我告诉他们，我会照顾他",
        "Most people wouldn't bother": "大多数人不会这么做",
        "What have I gotten myself into": "我这是把自己卷进了什么事里",
        "Kiku, you okay": "菊，你还好吗",
        "(Chuckles) Well, just watch out for guards": "（轻笑）好吧，注意守卫",
        "Here it is": "就是这个",
        "The army will need the rest": "军队会需要休整",
        "Are you Atsu": "你是笃吗",
        "There's no denying your reputation": "没人能否认你的名声",
        "We may as well use it": "那我们不妨利用它",
        "How did it go with her": "跟她谈得怎么样",
        "Do I want to know": "我该知道吗",
        "I've been too busy to notice": "我忙得都没注意到",
        "Do you think this plan will work": "你觉得这个计划会行吗",
        "After they separated us, I was so scared": "在他们把我们分开后，我吓坏了",
        "Even now": "即使现在",
        "I've had so many nightmares about this place": "我做过无数关于这里的噩梦",
        "Safe for the moment, but Saito's sons won't stop until its walls crumble": "暂时安全，但斋藤的儿子们不会停，直到城墙崩塌",
        "Benten Port. Its residents are likely retreating to the castle": "弁天港。那里的居民很可能正撤往城堡",
        "If we can feed them all": "如果我们能把他们都喂饱",
        "(Laughs) A purple flower": "（笑）紫色的花？",
        "The orange one": "橙色的那朵",
        "that I wasn't paying attention when Father explained it": "我刚才没注意听父亲解释",
        "I stay here where it's safe, while Father carries out his duties across Ezo": "我待在这里比较安全，而父亲则在蝦夷各地履行职责",
        "Jubei's done well": "十兵卫做得不错",
        "The Matsumae wanted to put him down": "松前的人想把他处理掉",
        "but I told them I'd care for him": "但我告诉他们，我会照顾他",
        "She sometimes finds flower arrangements": "她有时会摆花",
        "Our scouts have only caught glimpses of the Dragon": "我们的斥候只瞥见过龙的身影",
        "Because he's careful": "因为他很谨慎",
        "He knows he's a target. We'll only get one shot at him": "他知道自己是目标。我们只有一次机会",
        "This is it": "就是这里了",
        "We'll speak with my soldiers": "我去和我的士兵谈",
        "Matsumae": "松前",
        "The last of four brothers": "四兄弟中的最后一个",
        "Wonder what happened to the rest": "不知道其他几个怎么样了",
        "My plan's working": "我的计划奏效了",
        "I'll let the Last Brother kill everyone else": "我会让最后一个兄弟杀掉其他人",
        "Then I'll take him down and take the entire bounty for myself": "然后我再干掉他，把全部赏金都拿到手",
        "The Last Brother put up a fight": "最后那个兄弟确实反抗了",
        "Half of us are already dead. You sure we can take him": "我们已经死了一半了。你确定我们能拿下他吗",
        "Told everyone the brothers were murderous lunatics and put a bounty on their heads": "我告诉所有人这兄弟几个是杀人疯子，还给他们挂了赏金",
        "He must be close": "他一定就在附近",
        "Tadasuke": "忠助",
        "One of my customers shot me": "我的一个顾客开枪打了我",
        "Should've seen it coming": "我早该想到的",
        "We need to burn that wound, then bandage it": "我们得先灼烧伤口，再包扎",
        "You a healer": "你是医师吗",
        "I've dealt with gunshots before": "我以前处理过枪伤",
        "(Hisses in pain) Get me some sake": "（痛得抽气）给我拿点清酒",
        "It's on a shelf nearby": "就在附近的架子上",
        "This is going to hurt, isn't it": "这会很疼，对吧",
        "It's not going to feel good": "肯定不会好受",
        "Business has been good": "生意不错",
        "Clan Saito is hungry for firearms": "斋藤家族正急着要火器",
        "The Matsumae lost a lot of men to those guns": "松前人死了很多在那些枪下",
        "And now, the Dragon's forces are tearing the coast apart": "现在，龙的部队正在把海岸撕成碎片",
        "I offered to sell to the samurai": "我本想卖给武士",
        "but they don't have gunpowder or ammunition": "但他们没有火药和弹药",
        "That monster shot my horse": "那个怪物打死了我的马",
        "I sell my work to whoever has the money to buy it": "我把作品卖给出得起钱的人",
        "Murata said Unosuke would be at a farmstead near here": "村田说宇之介会在这附近的一处农庄",
        "Someone was storing weapons, supplies": "有人在这里囤放武器和补给",
        "A rusted iron hook": "一只生锈的铁钩",
        "Too old to be of any use": "太旧了，已经没用了",
        "Never seen a helmet this old before": "我从没见过这么旧的头盔",
        "Looks like its been through a lot": "看起来经历了不少",
        "A saddle": "一个马鞍",
        "Someone went through a lot of trouble to keep this hidden": "有人费了很大劲把这东西藏起来",
        "Could this be the Storm Blade": "这会不会就是风暴之刃",
        "How long has this been here": "这东西在这里多久了",
        "Slit her throat": "割开她的喉咙",
        "Someone's house": "某人的家",
        "The Storm Blade's owner must have lived here": "风暴之刃的主人一定住在这里",
        "Burned adoption papers for a 'clan Shimura'": "一份烧毁的收养文书，写着“岛村家族”",
        "Looks like an herbalist's set": "看起来像一套草药师工具",
        "Once used to make medicines": "以前是用来配药的",
        "Might be a family heirloom": "也许是家传之物",
        "Fresh footprints": "新鲜的脚印",
        "He must've gone through here": "他一定从这里经过了",
        "But I always took him as": "但我一直以为他是那种人",
        "The Dragon needs Lord Saito's approval": "龙需要斋藤大人的许可",
        "It's all right, Atsu": "没事的，笃",
        "She's trying to impress you": "她在想办法给你留下好印象",
        "I'm glad to be stationed with the Spider and not the Dragon": "我很高兴是跟蜘蛛驻在一起，而不是跟龙",
        "You don't think she'll come for him": "你不觉得她会来找他吗",
        "I've never seen the Spider so upset": "我从没见过蜘蛛这么生气",
        "Rage wins the battle, but loses the war": "愤怒能赢一场仗，却会输掉整场战争",
        "No one leaves": "谁都别想离开",
        "Do not keep the Spider waiting": "别让蜘蛛久等",
        "No, the tree was burning hotter": "不，是树烧得更旺了",
        "More fire. It was a blaze": "再加火。那是一片火海",
        "The music! Louder! Faster": "音乐！再大声点！再快点！",
        "People were screaming": "人们在尖叫",
        "I'm going to surrender and offer to join their side": "我会投降，加入他们那边",
        "Glad you can join us": "欢迎加入我们",
        "Put him in the attic": "把他关到阁楼上",
        "We will question him when our commander arrives": "等指挥官到了，我们再审问他",
        "It doesn't look like they found the armour yet": "看起来他们还没找到盔甲",
        "I need to take these soldiers out before they hurt Ginji": "我得先解决这些士兵，免得他们伤到金次",
        "If clan Matsumae get this armour, it'll be harder to shoot them down": "如果松前家拿到这副盔甲，就更难把他们击倒了",
        "We won't let that happen": "我们不会让那种事发生",
        "so give us the armour": "所以把盔甲交出来",
        "I'll need reassurances first": "我得先听点保证",
        "(Chuckles) That's not how this works": "（轻笑）事情不是这么办的",
        "I told the owners to put it with the good stuff": "我让店主把它和好货放一起了",
        "Sake": "清酒",
        "Tea": "茶",
        "The armour must be here somewhere": "盔甲一定就在这里某处",
        "It'll look similar to the enemy's armour, but five times lighter": "它看起来会像敌人的盔甲，但轻五倍",
        "Nothing here": "这里什么都没有",
        "There's something in here": "这里面有东西",
        "A word, friend": "借一步说话，朋友",
        "I just wanted to thank you": "我只是想谢谢你",
        "You were brave to help Ginji fight back": "你敢帮金次反抗，真勇敢",
        "Commander Wada has agreed we'll use the Spider as bait": "和田指挥官同意我们把蜘蛛当诱饵",
        "We just need the Dragon to take it": "我们只需要让龙上钩",
        "We will stage the Spider's execution. Make it public": "我们会安排蜘蛛的处决，并且公开进行",
        "The Dragon will stop at nothing to save his brother": "龙会不惜一切去救他弟弟",
        "And then our army will ambush him when he tries": "等他来救时，我们的军队就会伏击他",
        "We'd better break the news to the Spider": "我们最好去把消息告诉蜘蛛",
        "Be careful when you talk to him": "和他说话时小心点",
        "He knows he has power over both of you": "他知道自己能拿捏你们两个",
        "Don't you feel bad killing people": "你杀人时不会觉得难受吗",
        "They wouldn't feel bad if they killed me. I was just quicker": "他们要是杀了我也不会难受。我只是更快一步",
        "But what's it like when you kill them": "那你杀人的时候是什么感觉",
        "You took her with you": "你把她也带来了",
        "It was a little more complicated than that": "事情没那么简单",
        "You can't keep sheltering her": "你不能一直护着她",
        "It gets the job done": "能把事办成就行",
        "I left a bamboo stand intact nearby if you want to put it to use": "附近我留了一片没砍的竹林，给你练手用",
        "What if someone steals him": "要是有人把它偷走怎么办",
        "It'll be their mistake—that horse doesn't listen to anyone but you": "那是他们自己的错，那匹马除了你谁都不听",
        "Atsu! Give us a moment, Kiku": "笃！让我们和菊说句话",
        "Good... Almost too good": "好……好得有点过头了",
        "(Laughs.)": "（笑）",
        "You owe me fifty mon": "你欠我五十文",
        "We never agreed to that": "我们可没这么说定",
        "I'll pay her debt": "我替她付",
        "Now Oyuki has her own lesson to teach you": "现在，熏子也有她自己的课要教你",
        "and I want to reach the temple by sundown": "而且我想在日落前赶到寺庙",
        "Run ahead, Kiku. We'll catch up": "你先跑，菊。我们会追上去",
        "You're a good aunt, Atsu": "你是个好姑姑，笃",
        "Just don't expect me to lay down my sword and start a family": "可别指望我放下刀去成家",
        "I said, 'Aunt'. Not 'Mother'": "我说的是“姑姑”，不是“妈妈”",
        "Where is Kiku's mother": "菊的母亲在哪",
        "She got sick not long after Kiku was born": "菊出生后没多久她就病了",
        "She didn't survive": "她没撑过去",
        "I'm sorry, Jubei": "抱歉，十兵卫",
        "We've managed well enough": "我们已经过得够好了",
        "Now Kiku has an aunt to help out": "现在菊有个姑姑能帮忙",
        "I thought I might have to come find you": "我还以为得来找你呢",
        "Atsu and I duelled": "笃和我切磋过了",
        "And yet, you walk away unscathed": "可你看起来毫发无伤",
        "She'll have a few bruises tomorrow": "她明天会有几处淤青",
        "Any sign of clan Saito": "有斋藤家的踪影吗",
        "All is quiet for now": "目前一切安静",
        "Come, Kiku": "来吧，菊",
        "I want to show you something": "我想给你看样东西",
        "Some people live their whole life in one place, but never truly understand it": "有些人一辈子都住在一个地方，却从未真正了解那里",
        "Because their view is narrow": "因为他们的眼界太窄",
        "How can that be": "怎么会这样",
        "Atsu and I will show you": "笃和我会带你看",
        "Matsumae Castle": "松前城",
        "My home": "我的家",
        "It looks so small from here": "从这里看它好小",
        "And yet, within its walls the keep towers over you": "可在城墙内，主楼又高高耸立在你面前",
        "Oiso fishing village": "大磯渔村",
        "Father says it's dangerous": "父亲说那里很危险",
        "And what do you think": "那你怎么想",
        "The desperate and scared do things they normally wouldn't": "绝望和恐惧会让人做出平时不会做的事",
        "The lighthouse": "灯塔",
        "A great victory—you freed it from the Dragon": "那是场大胜利，你把它从龙手里解放了",
        "He still got away": "他还是跑了",
        "Both things can be true": "两件事都能是真的",
        "It's all a matter of perspective": "这只是看问题的角度不同",
        "Now that your view has widened, we will use these landmarks to create a map": "既然你视野变宽了，我们就用这些地标来画地图",
        "Can't we just buy one": "我们不能直接买吗",
        "Drawing will help you memorise where to go": "画出来能帮你记住路线",
        "I'll show you": "我给你示范",
        "How did you learn to draw like that": "你怎么学会画成这样的",
        "Years of getting lost": "靠多年迷路练出来的",
        "Atsu has a delicate touch when it comes to art": "笃在艺术上很有灵气",
        "Oyuki exaggerates": "熏子夸张了",
        "Foraging is an invaluable skill—especially when times are hard": "采集是很宝贵的技能，尤其在艰难时候",
        "Look in damp places. But avoid the spotted mushrooms": "去潮湿的地方找，但避开有斑点的蘑菇",
        "She doesn't need to hear that story": "这事没必要让她听",
        "As a child, Jubei thought the spotted kind had magical powers": "十兵卫小时候还以为有斑点的那种有魔力",
        "Did they": "真的有吗",
        "A spotted mushroom left him squatting for days": "一颗有斑点的蘑菇让他蹲了好几天",
        "The smell": "那味道",
        "Charming": "真够呛",
        "Both of you": "你们两个都一样",
        "don't stray too far": "别走太远",
        "That should be enough": "应该够了",
        "We need to go": "我们该走了",
        "The temple is at the top of the mountain. We should make it before nightfall": "寺庙在山顶，我们得在天黑前赶到",
        "I'll race you there": "我跟你比谁先到",
        "I would call today a success": "今天算是成功了",
        "It has been a nice distraction": "这倒是个不错的分心事",
        "Do you really think the Dragon will come for the Spider": "你真觉得龙会来救蜘蛛吗",
        "The Dragon has done monstrous things, but he loves his brother": "龙做过很多恶事，但他爱自己的弟弟",
        "He'll come": "他会来的",
        "It's beautiful": "真美",
        "These monks are friends": "这些僧侣是朋友",
        "If anything happens, Kiku": "如果出什么事，菊",
        "Iunderstarid": "我明白",
        "You can't be good at everything": "你不可能什么都擅长",
        "Can you teach me how to create lyrics": "你能教我写词吗",
        "That's the last of them": "这是最后一批了",
        "Do not miss": "别打偏了",
        "I used to go hunting with my grandson": "我以前常和孙子一起打猎",
        "But it is my shame": "但那是我的耻辱",
        "Remain vigilant": "保持警惕",
        "Is that really you": "真的是你吗",
        "When I refused to train my grandson, I gave up all hope of legacy": "当我拒绝训练孙子时，我也放弃了传承的希望",
        "Safe But Saito's sons won't stop until its walls crumble": "暂时安全，但斋藤的儿子们不会停，直到城墙崩塌",
        "Kikut I stay here where it's safe, while Father carries out his duties across Ezo": "我待在这里比较安全，而父亲则在蝦夷各地履行职责",
        "Kiku. while Father carries out his duties across Ezo": "我待在这里比较安全，而父亲则在蝦夷各地履行职责",
        "The Matsumae wanted to put him down,": "松前的人想把他处理掉",
        "The Matsumae wanted to put him down, but I told them I'd care for him": "松前的人想把他处理掉，但我告诉他们，我会照顾他",
        "Then I'll take him down and take the entire bounty for myself": "然后我再干掉他，把全部赏金都拿到手",
        "Rage wins the battle,": "愤怒能赢一场仗，",
        "but loses the war": "却会输掉整场战争",
        "Saito's been trying to capture armourers like me all over Ezo. I'm going to surrender and offer to join their side": "斋藤一直在蝦夷各地抓像我这样的铸甲师。我打算投降，加入他们那边",
        "It doesn't look like they found the armour yet": "看起来他们还没找到盔甲",
        "If clan Matsumae get this armour,": "如果松前家拿到这副盔甲，",
        "it'll be harder to shoot them down": "就更难把他们击倒了",
        "And then our army will ambush him when he tries": "等他来救时，我们的军队就会伏击他",
        "Kiku? They wouldn't feel bad if they killed me. I was just quicker": "菊？他们要是杀了我也不会难受。我只是更快一步",
        "But what's it like when you kill them": "那你杀人的时候是什么感觉",
        "Now Oyuki has her own lesson to teach you": "现在，熏子也有她自己的课要教你",
        "tber Now Oyukihas hct ewrlesson to teach you Jubei: and Twant to reach the temple by sundown": "而且我想在日落前赶到寺庙",
        "Run ahead, Kiku. We'll catch up": "你先跑，菊。我们会追上去",
        "All is quiet for now. Come, Kiku": "目前一切安静，来吧，菊",
        "Come, Kiku. I want to show you something": "来吧，菊。我想给你看样东西",
        "Both of you. (Laughs)": "你们两个都一样。（笑）",
        "(Laughs)": "（笑）",
        "Atsu—don't stray too far": "笃，别走太远",
        "The Dragon has done monstrous things,": "龙做过很多恶事，",
        "but he loves his brother": "但他爱自己的弟弟",
        "These monks are friends. If anything happens, Kiku": "这些僧侣是朋友。如果出什么事，菊",
        "If anything happens, Kiku,": "如果出什么事，菊，",
        "We set up a camp for you at the edge of the grounds": "我们在场地边缘给你们扎了营",
        "Grandfather": "祖父",
        "You all make sure to try the roasted squash": "你们都记得尝尝烤南瓜",
        "Father,": "父亲，",
        "AuntAtsu Kiku, go back home. Wait until I come for you": "笃，菊，回家去。等我来找你",
        "This will all be over soon": "这一切很快就会结束",
        "Run along, little flower": "快走吧，小花",
        "She needs to learn": "她需要学会这些",
        "Our families have been at war for a long time": "我们的家族已经交战很久了",
        "The Night of the Burning Tree wasn't war,": "燃树之夜不是战争，",
        "it was a massacre": "那是一场屠杀",
        "I wasn't given a choice. That night, if my brother and I didn't shoot you,": "我没有选择。那晚如果我和哥哥不向你开枪，",
        "our father would've done worse to us": "我们的父亲会对我们做得更糟",
        "You destroyed our family": "是你毁了我们的家族",
        "That's my father's way": "那就是我父亲的做法",
        "Excuses don't wash away the blood": "借口洗不掉血债",
        "No. That's what sake is for": "不，清酒就是用来干这个的",
        "We can't let them spot us": "不能让他们发现我们",
        "And you're a dead man": "而你死定了",
        "Remain in cover until the order is given": "先躲好，等命令下达",
        "Atsu, can you see anything": "笃，你能看到什么吗",
        "It's the Dragon's boat": "是龙的船",
        "Good. He's taking the bait": "很好，他上钩了",
        "And this one... something's wrong": "还有这一艘……有点不对劲",
        "It looks empty": "看起来是空的",
        "What": "什么",
        "(Dark laugh)": "（阴沉的笑声）",
        "On your left, Atsu—another ship": "笃，你左边还有一艘船",
        "He's here! I'm here. Father!": "他来了！我在这儿。父亲！",
        "The Matsumae thought they could surprise us": "松前的人以为能偷袭我们",
        "Their trap will be their own destruction": "他们的陷阱只会害了自己",
        "All I care about is yours": "我只在乎你的安危",
        "Because you ran away like a coward": "因为你像个懦夫一样逃了",
        "Maybe they made it to the temple": "也许他们已经到寺庙了",
        "Can't take a chance Saito's men might spot us": "不能冒险，斋藤的人可能会发现我们",
        "What does it matter? Father's gone": "那又怎样？父亲已经走了",
        "Father's gone. Oyuki's gone": "父亲走了。熏子也走了",
        "They're aren't dead, Kiku": "他们没死，菊",
        "You don't know": "你不知道",
        "They have to be": "他们一定得活着",
        "Jubei created a new life for himself": "十兵卫为自己重新过上了新生活",
        "And you": "还有你",
        "No! What's happening": "不！怎么了",
        "Kiku!": "菊！",
        "I'll kill you! I'll kill you!": "我要杀了你！我要杀了你！",
        "Mother's toro lantern": "母亲的鲷鱼灯笼",
        "We used to take turns lighting it each night": "我们以前每晚轮流点它",
        "It won't be much longer. I promise": "不会太久了。我保证",
        "No trees, though": "不过这里没有树",
        "Are you": "你是……",
        "Takezo: (Chuckles) This will be the greatest day of my life": "（轻笑）这会是我人生中最美好的一天",
        "A few coins for a poor musician": "给贫穷乐师几枚铜钱吧",
        "Many thanks for your generosity": "多谢你的慷慨",
        "Cut down by a skilled swordsman": "被一个高手剑客砍倒了",
        "We need to go before that thing kills the rest of us": "我们得在那东西杀光我们之前离开",
        "Run away if you want, but I'm staying": "想跑你就跑吧，我要留下",
        "You idiot, that's just a woman": "蠢货，那只是个女人",
        "One of the locks had a cave engraving,": "有一把锁上刻着洞窟图案，",
        "but I don't see any spider lilies here": "但这里没看到彼岸花",
        "These drawings are by a child": "这些画是小孩画的",
        "Medicine,": "药，",
        "bedding soaked through with blood": "被血浸透的寝具",
        "This must be where his daughter died": "他女儿一定就是死在这里",
        "The Spider Lily General's armour": "彼岸花将军的盔甲",
        "I hope Hanbei's right about the Spider": "希望半兵卫对蜘蛛的判断是对的",
        "Clan Saito's burial grounds should be around here": "斋藤家的墓地应该就在这附近",
        "Just need to find somewhere to wait till the Spider shows up": "只需要找个地方等蜘蛛出现",
        "Hello stranger. Do you need a ride": "你好，陌生人。要搭车吗",
        "Hurry before I change my mind": "快点，不然我会改变主意",
        "I don't see Jubei or Oyuki": "我没看到十兵卫或熏子",
        "Charcoal, saltpetre, sulphur": "木炭、硝石、硫磺",
        "Should try to do this quietly": "最好悄悄来",
        "That's where Saito's holding Oyuki": "斋藤就是把熏子关在那里",
        "It's far": "很远",
        "The main gate,": "正门，",
        "I never thought I'd hear you say that": "我从没想过会听你这么说",
        "Kiku said it first": "是菊先说的",
        "She's like you when she's angry": "她生气时跟你很像",
        "her words cut deep and true": "她的话又狠又准",
        "She will be": "她会没事的",
        "Once she sees you": "等她见到你",
        "Stand your ground": "守住阵地",
        "Kill them quick—we need to reach Oyuki": "快解决他们，我们得赶到熏子那里",
        "Saito's men aren't as gentle as the Oni's": "斋藤的人可不像鬼那样手下留情",
        "Her loyalty to you never wavered": "她对你的忠诚从未动摇",
        "I see now why she earned your forgiveness": "我现在明白她为什么能得到你的原谅了",
        "I won't leave her—whatever they throw at us": "不管他们扔什么过来，我都不会丢下她",
        "There's the alarm": "警报响了",
        "How fast can you run": "你跑得多快",
        "Think I preferred the Oni's castle": "我还是更喜欢鬼的城堡",
        "What do you think Saito has planned for Oyuki": "你觉得斋藤给熏子安排了什么",
        "Nothing good": "肯定没好事",
        "After the Dragon's death, he wants blood": "龙死后，他就想要鲜血",
        "All you have are empty words": "你说的都是空话",
        "Stay very still": "一动也别动",
        "We don't have time for this": "我们没时间耗在这儿",
        "I never should have left Kiku alone": "我真不该把菊一个人留下",
        "More mushrooms than we could eat": "蘑菇多得我们吃不完",
        "The snow will start soon": "很快就会下雪",
        "We will be quick": "我们会很快",
        "Jubeis l 've had so many nightmares about this place": "我做过无数关于这里的噩梦",
        "The oramge one": "橙色的那朵",
        "Atsu Someone's house": "某人的家",
        "Kikur Atsu": "笃",
        "ARROW (FULL) Then I'll take him down and take the entire bounty for myself": "然后我再干掉他，把全部赏金都拿到手",
        "(((e)) ((e))": "（哭声）",
        "AND PRESS FD TO SELECT THE TANZUITSU HOLD": "按下 FD 选择丹津住握持",
        "WS (FULL) Someone was storing weapons, supplies": "有人在这里囤放武器和补给",
        "E STANDOFF Atsu: It doesn't look like they-found the armour yet": "看起来他们还没找到盔甲",
        "1_STANDOFF If clan Matsumae get this armour,": "如果松前家拿到这副盔甲，",
        "The Spider: What else is there": "蜘蛛：还能怎样",
        "NOTYEI The Spider: Hurry up—": "蜘蛛：快点——",
        "NOTYEI The Spider: Hurry up- The Spider: before I change my mind": "蜘蛛：快点，不然我会改变主意",
        "Atsu: 'Saito Fumi'.": "笃：“斋藤富美”。",
        "Atsu: I wonder who that was.": "笃：我不知道那是谁。",
        "Atsu: Fine. We'll do it the hard way.": "笃：好吧。那我们就来硬的。",
        "Atsu: Some other time": "笃：改天吧",
        "Atsu: There's the Spider...": "笃：蜘蛛在那里……",
        "Atsu: They must be further in.": "笃：他们一定在更里面。",
        "Atsu: Charcoal,": "笃：木炭，",
        "Atsu: saltpetre, sulphur..": "笃：硝石，硫磺……",
        "Bu:kiku saian Atsu: She's like you when she's angry": "她生气时跟你很像",
        "Jubei: Is she all right? Atsu: She will be": "她还好吗？她会没事的",
        "p moving! Jubei: time-": "快，动起来！时间——",
        "Kiku": "菊",
        "Atsu": "笃",
        "Oyuki": "熏子",
        "Matsumae": "松前",
        "Now Atsu": "现在，笃",
        "After they separated us": "在他们把我们分开后",
        "I was so scared": "我当时吓坏了",
        "Even now": "即使现在",
        "Safe But Saito's sons won't stop until its walls crumble": "暂时安全，但斋藤的儿子们不会停，直到城墙崩塌",
        "Opel-uncgate-": "开门",
        "WS (FULL) Atsu: Someone was storing weapons, supplies.": "有人在这里囤放武器和补给",
        "E STANDOFF Atsu: It doesn't look like they-found the armour yet.": "看起来他们还没找到盔甲",
        "1_STANDOFF Saito Outlaw: If clan Matsumae get this armour,": "如果松前家拿到这副盔甲，",
        "Jubei: And then-our army will ambush him when he tries.": "等他来救时，我们的军队就会伏击他",
        "Kiku: But what's it like when you kill them—": "那你杀人的时候是什么感觉——",
        "Jubei: Now Oyuki has her own-lesson to teach you—": "现在，熏子也有她自己的课要教你——",
        "tber Now Oyukihas hct ewrlesson to teach you Jubei: and Twant to reach the temple by sundown.": "而且我想在日落前赶到寺庙",
        "Jubei:-Run ahead, Kiku. We'll catch up.": "你先跑，菊。我们会追上去",
        "Kiku: Atsu and I duelled!": "笃和我切磋过了！",
        "Oyuki: Atsu and I will show you.": "笃和我会带你看。",
        "Oyuki: Atsu has a delicate touch when it comes to art.": "笃在艺术上很有灵气。",
        "Atsu: Oyuki exaggerates.": "熏子夸张了。",
        "Master Enomoto: Now Atsu!": "榎本师傅：现在，笃！",
        "The Spider: She needs to learn. The Spider: mr families have been at war fora long time": "她需要学会这些。我们的家族已经交战很久了",
        "The Spider: I wasn't given a choice. That night,if my brother and I didn't shoot you The Spider: our father would've done worse to us": "我没有选择。那晚如果我和哥哥不向你开枪，我们的父亲会对我们做得更糟",
        "The Spider: our father would've done worse to us. Atsu: You destroyed our family": "我们的父亲会对我们做得更糟。是你毁了我们的家族",
        "The Spider: That's my father's way. Atsu: Excuses don't wash away the blood": "那就是我父亲的做法。借口洗不掉血债",
        "Atsu: He's here! The Snider: I'm here. Father!": "他来了！我在这儿。父亲！",
        "Kiku: Oyuki's gone. Atsu: They aren't dead, Kiku.": "熏子走了。他们没死，菊。",
        "Atsu: Jubei created a new life for himself..": "十兵卫为自己重新过上了新生活",
        "Atsu: Kiku?": "笃？",
        "Atsu: Kiku!": "笃！",
        "Kiku: I'll kill you! I'll kill you!": "我要杀了你！我要杀了你！",
        "Atsu: Are you? Takezo: (Chuckles) This will be the greatest day of my life.": "你是吗？（轻笑）这会是我人生中最美好的一天。",
        "Ainu Merchant: Stay clear of bad kamuy.": "阿伊努商人：离坏神灵远点。",
        "Saito Outlaw: We need to go before that thing kills the rest of us. Saito Outlaw: Run away if you want, but I'm staying.": "我们得在那东西杀光我们之前离开。想跑你就跑吧，我要留下。",
        "General Tominaga: Trespassers!": "富永将军：擅入者！",
        "General Tominaga: (anguished wail)": "富永将军：（痛苦的哀嚎）",
        "Atsu: The Spider Lily General's armour.": "彼岸花将军的盔甲。",
        "Atsu: 'Saito Fumi'.": "“斋藤富美”。",
        "Atsu: I wonder who that was.": "我不知道那是谁。",
        "Atsu: Fine. We'll do it the hard way.": "好吧。那我们就来硬的。",
        "The Spider: What else is there": "蜘蛛：还能怎样",
        "Atsu: Some other time": "笃：改天吧",
        "Atsu: There's the Spider...": "笃：蜘蛛在那里……",
        "NOTYEI The Spider: Hurry up—": "蜘蛛：快点——",
        "NOTYEI The Spider: Hurry up- The Spider: before I change my mind.": "蜘蛛：快点，不然我会改变主意。",
        "Atsu: They must be further in.": "他们一定在更里面。",
        "Atsu: Charcoal,": "木炭，",
        "Atsu: saltpetre, sulphur..": "硝石，硫磺……",
        "Atsu: Kiku said it first.": "是菊先说的。",
        "Bu:kiku saian Atsu: She's like you when she's angry": "她生气时跟你很像",
        "Jubei: Is she all right? Atsu: She will be": "她还好吗？她会没事的",
        "p moving! Jubei: time-": "快，动起来！时间——",
        "After they separated us": "在他们把我们分开后",
        "I was so scared": "我当时吓坏了",
        "Even now": "即使现在",
        "Safe But Saito's sons won't stop until its walls crumble": "暂时安全，但斋藤的儿子们不会停，直到城墙崩塌",
        "Matsumae,": "松前，",
        "ARROW (FULL) Then I'll take him down and take the entire bounty for myself": "然后我再干掉他，把全部赏金都拿到手",
        "WS (FULL) Someone was storing weapons, supplies": "有人在这里囤放武器和补给",
        "It doesn't look like they-found the armour yet": "看起来他们还没找到盔甲",
        "1_STANDOFF If clan Matsumae get this armour,": "如果松前家拿到这副盔甲，",
        "And then-our army will ambush him when he tries": "等他来救时，我们的军队就会伏击他",
        "But what's it like when you kill them—": "那你杀人的时候是什么感觉——",
        "Now Oyuki has her own-lesson to teach you—": "现在，熏子也有她自己的课要教你——",
        "tber Now Oyukihas hct and Twant to reach the temple by sundown": "而且我想在日落前赶到寺庙",
        "-Run ahead, Kiku. We'll catch up": "你先跑，菊。我们会追上去",
        "Atsu and I duelled": "笃和我切磋过了",
        "Atsu and I will show you": "笃和我会带你看",
        "Atsu has a delicate touch when it comes to art": "笃在艺术上很有灵气",
        "Oyuki exaggerates": "熏子夸张了",
        "She needs to learn. mr families have been at war fora long time": "她需要学会这些。我们的家族已经交战很久了",
        "I wasn't given a choice. That night,if my brother and our father would've done worse to us": "我没有选择。那晚如果我和哥哥不向你开枪，我们的父亲会对我们做得更糟",
        "our father would've done worse to us. You destroyed our family": "我们的父亲会对我们做得更糟。是你毁了我们的家族",
        "That's my father's way. Excuses don't wash away the blood": "那就是我父亲的做法。借口洗不掉血债",
        "He's here! I'm here. Father": "他来了！我在这儿。父亲！",
        "Oyuki's gone. They aren't dead, Kiku": "熏子走了。他们没死，菊",
        "Jubei created a new life for himself": "十兵卫为自己重新过上了新生活",
        "I'll kill you! I'll kill you": "我要杀了你！我要杀了你！",
        "Are you? (Chuckles) This will be the greatest day of my life": "你是吗？（轻笑）这会是我人生中最美好的一天",
        "Stay clear of bad kamuy": "离坏神灵远点",
        "We need to go before that thing kills the rest of us. Run away if you want, but I'm staying": "我们得在那东西杀光我们之前离开。想跑你就跑吧，我要留下",
        "Trespassers": "擅入者",
        "(anguished wail)": "（痛苦的哀嚎）",
        "The Spider Lily General's armour": "彼岸花将军的盔甲",
        "'Saito Fumi'": "“斋藤富美”",
        "I wonder who that was": "我不知道那是谁",
        "Fine. We'll do it the hard way": "好吧。那我们就来硬的",
        "What else is there": "还能怎样",
        "Some other time": "改天吧",
        "There's the Spider": "蜘蛛在那里",
        "Hurry up—": "快点——",
        "Hurry before I change my mind": "快点，不然我会改变主意",
        "They must be further in": "他们一定在更里面",
        "Charcoal,": "木炭，",
        "saltpetre, sulphur": "硝石，硫磺",
        "Kiku said it first": "是菊先说的",
        "kiku She's like you when she's angry": "她生气时跟你很像",
        "Is she all right? She will be": "她还好吗？她会没事的",
        "p moving! time-": "快，动起来！时间——",
        "Atsu: After they separated us,": "在他们把我们分开后",
        "Jubei: I was so scared,": "我当时吓坏了",
        "Atsu: Even now,": "即使现在",
        "Oyuki: Safe for the moment Oyuki: But Saito's sons won't stop until its walls crumble": "暂时安全，但斋藤的儿子们不会停，直到城墙崩塌",
        "ARROW (FULL) Ronin: Then I'll take him down and take the entire bounty for myself.": "然后我再干掉他，把全部赏金都拿到手",
        "WS (FULL) Atsu: Someone was storing weapons, supplies.": "有人在这里囤放武器和补给",
        "E STANDOFF Atsu: It doesn't look like they-found the armour yet.": "看起来他们还没找到盔甲",
        "1_STANDOFF Saito Outlaw: If clan Matsumae get this armour,": "如果松前家拿到这副盔甲，",
        "Jubei: And then-our army will ambush him when he tries.": "等他来救时，我们的军队就会伏击他",
        "Kiku: But what's it like when you kill them—": "那你杀人的时候是什么感觉——",
        "Jubei: Now Oyuki has her own-lesson to teach you—": "现在，熏子也有她自己的课要教你——",
        "tber Now Oyukihas hct ewrlesson to teach you Jubei: and Twant to reach the temple by sundown.": "而且我想在日落前赶到寺庙",
        "Jubei:-Run ahead, Kiku. We'll catch up.": "你先跑，菊。我们会追上去",
        "Kiku: Atsu and I duelled!": "笃和我切磋过了！",
        "Oyuki: Atsu and I will show you.": "笃和我会带你看。",
        "Oyuki: Atsu has a delicate touch when it comes to art.": "笃在艺术上很有灵气。",
        "Atsu: Oyuki exaggerates.": "熏子夸张了。",
        "The Spider: I wasn't given a choice. That night,if my brother and I didn't shoot you The Spider: our father would've done worse to us": "我没有选择。那晚如果我和哥哥不向你开枪，我们的父亲会对我们做得更糟",
        "Atsu: Jubei created a new life for himself..": "十兵卫为自己重新过上了新生活",
        "Atsu: The Spider Lily General's armour.": "彼岸花将军的盔甲。",
        "NOTYEI The Spider: Hurry up- The Spider: before I change my mind.": "蜘蛛：快点，不然我会改变主意。",
        "Atsu: Kiku said it first.": "是菊先说的。",
        "Bu:kiku saian Atsu: She's like you when she's angry": "她生气时跟你很像",
        "Safe But Saito's sons won't stop until its walls crumble": "暂时安全，但斋藤的儿子们不会停，直到城墙崩塌",
        "Rage wins the battle": "愤怒能赢一场仗",
        "1_STANDOFF If clan Matsumae get this armour": "如果松前家拿到这副盔甲，",
        "tber Now Oyukihas hct and Twant to reach the temple by sundown": "而且我想在日落前赶到寺庙",
        "Atsu and I duelled": "笃和我切磋过了",
        "Atsu and I will show you": "笃和我会带你看",
        "Atsu has a delicate touch when it comes to art": "笃在艺术上很有灵气",
        "Oyuki exaggerates": "熏子夸张了",
        "The Dragon has done monstrous things": "龙做过很多恶事",
        "Father": "父亲",
        "The Night of the Burning Tree wasn't war": "燃树之夜不是战争",
        "I wasn't given a choice. That night, if my brother and I didn't shoot you": "我没有选择。那晚如果我和哥哥不向你开枪，",
        "I wasn't given a choice. That night,if my brother and our father would've done worse to us": "我没有选择。那晚如果我和哥哥不向你开枪，我们的父亲会对我们做得更糟",
        "Jubei created a new life for himself": "十兵卫为自己重新过上了新生活",
        "One of the locks had a cave engraving": "有一把锁上刻着洞窟图案",
        "Medicine": "药",
        "The Spider Lily General's armour": "彼岸花将军的盔甲",
        "Hurry before I change my mind": "快点，不然我会改变主意",
        "Charcoal": "木炭",
        "The main gate": "正门",
        "Kiku said it first": "是菊先说的",
        "kiku She's like you when she's angry": "她生气时跟你很像",
        "Safe But Saito's sons won't stop until its walls crumble": "暂时安全，但斋藤的儿子们不会停，直到城墙崩塌",
        "1_STANDOFF If clan Matsumae get this armour": "如果松前家拿到这副盔甲，",
        "tber Now Oyukihas hct ewrlesson to teach you Jubei and Twant to reach the temple by sundown": "而且我想在日落前赶到寺庙",
        "Atsu and I duelled": "笃和我切磋过了",
        "Atsu and I will show you": "笃和我会带你看",
        "Atsu has a delicate touch when it comes to art": "笃在艺术上很有灵气",
        "Oyuki exaggerates": "熏子夸张了",
        "I wasn't given a choice. That night if my brother and I didn't shoot you": "我没有选择。那晚如果我和哥哥不向你开枪，",
        "I wasn't given a choice. That night,if my brother and our father would've done worse to us": "我没有选择。那晚如果我和哥哥不向你开枪，我们的父亲会对我们做得更糟",
        "Jubei created a new life for himself": "十兵卫为自己重新过上了新生活",
        "The Spider Lily General's armour": "彼岸花将军的盔甲",
        "Hurry before I change my mind": "快点，不然我会改变主意",
        "Kiku said it first": "是菊先说的",
        "YÔOTEI RIVER": "羊蹄河",
        "Their eyes gazing at the true Mount Ytei": "他们的目光凝视着真正的羊蹄山",
        "I bring gifts for the Onil": "我给鬼送礼物",
        "Look—I admit our last plan was hasty": "我承认我们上次的计划太草率了",
        "You knowlI can't Climb that": "你知道我爬不上去",
        "Yari... Eor sparring": "长枪……用于比试",
        "You can handle them": "你能应付它们",
        "You just might learn something": "你或许还能学到点东西",
        "You're incredible": "你太厉害了",
        "Trust me": "相信我",
        "I'll find my fight elsewhere": "我会去别处找我的对手",
        "Come at me": "来啊",
        "Have a drink with a tired old ronin, stranger": "来陪一个疲惫的老浪人喝一杯吧，陌生人",
        "Every mask is carefully designed": "每一张面具都经过精心设计",
        "I pose a riddle You answer": "我出个谜题，你来答",
        "What am I": "我是什么",
        "I am blind when I am alone": "独自一人时我便是盲的",
        "Begin with a wide stance": "先摆开宽站姿",
        "Atsu! Ina and I need you to settle a debate": "笃！伊娜和我需要你来评理",
        "Thank you! Thank you": "谢谢！谢谢！",
        "I'll split the reward with anyone who helps me cut her down": "谁帮我把她砍倒，我就把赏金分他一半",
        "You're more insightful than you look. Our commander fell out of Lord Matsumae's favour": "你比看上去更敏锐。我们的指挥官失去了松前大人的信任",
        "Is that a compliment? You don't hide from your shamisen": "这是在夸我吗？别躲着你的三味线",
        "Completely": "完全",
        "A shrine? Howw is this a leadp": "神社？这怎么会是线索",
        "Yes! I can move again. (Chuckles)": "是！我又能动了。（轻笑）",
        "An old trick I learned to keep my more enthusiastic admirers in line": "我学过一个老把戏，用来压住那些过于热情的仰慕者",
        "Fantastic choice": "非常好的选择",
        "You'rejoking The same conviction that brought you here can warm you from within": "你在开玩笑。带你来这里的那份信念，也能从内心温暖你",
        "childlike": "孩子气",
        "Do you hear anything": "你听到什么了吗",
        "If Saito suspected disloyalty, why not iust kill you": "如果斋藤怀疑你不忠，为什么不直接杀了你",
        "Shunpei said the Nine Tails' clothes were wet": "俊平说九尾的衣服是湿的",
        "Every waterfall has its secrets": "每座瀑布都有秘密",
        "There's something I don't understand": "有件事我不明白",
        "Damn things won't stay put": "该死的东西就是不肯老实待着",
        "It must be hard, seeing the man Dojun's become": "看着道俊变成这样，一定很难受",
        "Careful. This is the perfect place for an ambush": "小心。这里最适合埋伏",
        "But the base on that one is frozen": "但那一个底座冻住了",
        "Dead. Your pet doesn't scare me": "死了。你的宠物吓不到我",
        "Burned adoption papers for a 'clan Shimura": "一份烧毁的收养文书，写着“岛村家族”",
        "Saito Fumi": "斋藤富美",
        "Atsu: Kiku said it first": "是菊先说的",
        "Bu:kiku saian Atsu: She's like you when she's angry": "她生气时跟你很像",
        "Atsu: After they separated us,": "在他们把我们分开后",
        "Jubei: I was so scared,": "我当时吓坏了",
        "Atsu: Even now,": "即使现在",
        "Safe But Saito's sons won't stop until its walls crumble": "暂时安全，但斋藤的儿子们不会停，直到城墙崩塌",
        "1_STANDOFF If clan Matsumae get this armour": "如果松前家拿到这副盔甲，",
        "tber Now Oyukihas hct ewrlesson to teach you Jubei and Twant to reach the temple by sundown": "而且我想在日落前赶到寺庙",
        "Atsu and I duelled": "笃和我切磋过了",
        "Atsu and I will show you": "笃和我会带你看",
        "Atsu has a delicate touch when it comes to art": "笃在艺术上很有灵气",
        "Oyuki exaggerates": "熏子夸张了",
        "I wasn't given a choice. That night if my brother and I didn't shoot you": "我没有选择。那晚如果我和哥哥不向你开枪，",
        "I wasn't given a choice. That night,if my brother and our father would've done worse to us": "我没有选择。那晚如果我和哥哥不向你开枪，我们的父亲会对我们做得更糟",
        "Jubei created a new life for himself": "十兵卫为自己重新过上了新生活",
        "The Spider Lily General's armour": "彼岸花将军的盔甲",
        "Hurry before I change my mind": "快点，不然我会改变主意",
        "Kiku said it first": "是菊先说的",
        "The Ont Display de bodwnea Asmelltherots": "把尸体摆在关押室附近，好让他们闻见腐臭",
        "Ronin: Come at mel": "来啊",
        "Oni Raider: I pose a riddle Oni Raider: You answer": "我出个谜题，你来答",
        "Oni Raider: What am I?": "我是什么",
        "Oni Raider: I am blind when I am alone": "独自一人时我便是盲的",
        "Atsu: \"Begin with a wide stance.\"": "先摆开宽站姿",
        "Safe for the moment Oyuki: But Saito's sons won't stop until its walls crumble": "暂时安全，但斋藤的儿子们不会停，直到城墙崩塌",
        "AND PRESS FD TO SELECT THE TANZUITSU HOLD": "按下 FD 选择丹津住握持",
        "HOLD": "握持",
        "1_STANDOFF Saito Outlaw: If clan Matsumae get this armour,": "如果松前家拿到这副盔甲，",
        "tber Now Oyukihas hct ewrlesson to teach you Jubei: and Twant to reach the temple by sundown.": "而且我想在日落前赶到寺庙",
        "Jubei: I said, 'Aunt'. Not 'Mother'": "我说的是“姑姑”，不是“妈妈”",
        "The Spider: I wasn't given a choice. That night,if my brother and I didn't shoot you The Spider: our father would've done worse to us": "我没有选择。那晚如果我和哥哥不向你开枪，我们的父亲会对我们做得更糟",
        "NOTYEI The Spider: Hurry up- The Spider: before I change my mind": "快点，不然我会改变主意",
    }
    if text in base_map:
        prefix = f"{speaker}：" if speaker else ""
        return prefix + base_map[text]
    return ""


def decide(input_row: dict[str, Any], prior_payload: dict[str, Any]) -> dict[str, Any]:
    status = str(input_row.get("status") or "")
    current_chinese_text = str(input_row.get("current_chinese_text") or "").strip()
    english_text = str(input_row.get("english_text") or "").strip()
    english_context = str(input_row.get("english_context_text") or "").strip()
    previous_decision = str(prior_payload.get("decision") or "").strip()
    previous_confidence = normalize_confidence(prior_payload.get("confidence"))
    speaker = infer_english_speaker(english_text)
    phrasebook = phrasebook_translation(english_text, speaker)
    corrected_text = correction_candidate(input_row)

    if phrasebook:
        return {
            "decision": "suggest_new_match",
            "confidence": max(previous_confidence, 0.78),
            "suggested_chinese_text": phrasebook,
            "reason": "固定短句可直接翻译，优先补挂。",
        }

    if status == "matched-low":
        if corrected_text:
            if current_chinese_text and len(corrected_text) >= max(4, len(current_chinese_text) - 3):
                return {
                    "decision": "suggest_new_match",
                    "confidence": max(previous_confidence, 0.83),
                    "suggested_chinese_text": corrected_text,
                    "reason": "存在可读 OCR 修正，保留原意并修正字形噪声。",
                }
            if not current_chinese_text:
                return {
                    "decision": "suggest_new_match",
                    "confidence": max(previous_confidence, 0.83),
                    "suggested_chinese_text": corrected_text,
                    "reason": "可直接补出稳定中文。",
                }
            return {
                "decision": "keep_current_match",
                "confidence": max(previous_confidence, 0.78),
                "suggested_chinese_text": "",
                "reason": "虽可修字，但当前句子整体仍可读，先保留。",
            }
        if looks_garbled(current_chinese_text):
            return {
                "decision": "reject_current_match",
                "confidence": max(previous_confidence, 0.82),
                "suggested_chinese_text": "",
                "reason": "当前中文明显有 OCR/拼接噪声，第二遍不保留。",
            }
        return {
            "decision": "keep_current_match",
            "confidence": max(previous_confidence, 0.72),
            "suggested_chinese_text": "",
            "reason": "当前中文可读且与上下文未见明显冲突，保守保留。",
        }

    if previous_decision == "no_match":
        if english_text and english_context and not looks_garbled(current_chinese_text):
            return {
                "decision": "no_match",
                "confidence": max(previous_confidence, 0.68),
                "suggested_chinese_text": "",
                "reason": "未见足够稳定的中文锚点，维持不挂。",
            }
        return {
            "decision": "no_match",
            "confidence": max(previous_confidence, 0.72),
            "suggested_chinese_text": "",
            "reason": "上下文仍不足以稳定对齐。",
        }

    if previous_decision == "keep_current_match":
        if corrected_text:
            return {
                "decision": "suggest_new_match",
                "confidence": max(previous_confidence, 0.84),
                "suggested_chinese_text": corrected_text,
                "reason": "当前行可读，但存在安全可修的 OCR 错字。",
            }
        if looks_garbled(current_chinese_text):
            return {
                "decision": "reject_current_match",
                "confidence": max(previous_confidence, 0.8),
                "suggested_chinese_text": "",
                "reason": "低分强配里当前中文噪声较重，第二遍改判。",
            }
        return {
            "decision": "keep_current_match",
            "confidence": max(previous_confidence, 0.75),
            "suggested_chinese_text": "",
            "reason": "第二遍仍然认为当前中文可保留。",
        }

    if previous_decision == "suggest_new_match":
        suggested = str(prior_payload.get("suggested_chinese_text") or "").strip()
        if suggested:
            return {
                "decision": "suggest_new_match",
                "confidence": max(previous_confidence, 0.8),
                "suggested_chinese_text": suggested,
                "reason": "保留此前可用建议，未见更强反证。",
            }
        return {
            "decision": "no_match",
            "confidence": 0.7,
            "suggested_chinese_text": "",
            "reason": "未能恢复稳定建议文本，退回不挂。",
        }

    return {
        "decision": "unsure",
        "confidence": 0.5,
        "suggested_chinese_text": "",
        "reason": "仍无法稳定判断。",
    }


def main() -> None:
    args = parse_args()
    queue_dir = args.request_root / args.queue_name
    batch_dir = queue_dir / "batches"
    response_dir = args.output_dir / args.queue_name
    response_dir.mkdir(parents=True, exist_ok=True)

    batch_no = 0
    total = 0
    for request_path in sorted(batch_dir.glob("*.jsonl")):
        batch_no += 1
        requests = load_jsonl(request_path)
        responses: list[dict[str, Any]] = []
        for request in requests:
            custom_id = str(request.get("custom_id") or "")
            user_content = response_text(request)
            input_row = extract_input_json(user_content)
            prior_payload = {}
            prior_text = user_content.split("Previous model result:", 1)[-1].strip() if "Previous model result:" in user_content else ""
            if prior_text:
                try:
                    prior_payload = json.loads(prior_text)
                except json.JSONDecodeError:
                    prior_payload = {}
            output = decide(input_row, prior_payload)
            responses.append({"custom_id": custom_id, "output": output})
            total += 1
        write_jsonl(response_dir / f"{args.queue_name}_responses_{batch_no:03d}.jsonl", responses)

    manifest = {
        "queue_name": args.queue_name,
        "request_root": str(args.request_root),
        "response_dir": str(response_dir),
        "response_file_count": batch_no,
        "response_count": total,
        "policy": "ocr-aware-local-second-pass",
    }
    (response_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote local retry responses -> {response_dir}")


if __name__ == "__main__":
    main()
