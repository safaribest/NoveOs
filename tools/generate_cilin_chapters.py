#!/usr/bin/env python3
"""
辞林式前5章生成脚本 v1.0
基于《写作辞林1982》体例改造：
- 每个场景从场景辞林中选取词条
- 每个角色对话通过对话红线检查
- 生成后应用 AntiDetectReviser（含辞林过滤层）

章节列表（匹配前5章大纲）：
1. 暴击开局——被职业抛弃的人，连村队都不要（解约/告别 + 返乡/归家）
2. 侗神瞳觉醒——千年铜鼓里的第三只眼（系统觉醒 + 疼痛中的幻觉）
3. 第一次小规模打脸——鼓楼视野，开！（初次训练 + 被围观的窘迫）
4. 七个人踢个屁（隐藏实力 + 碾压/打脸）
5. 铜山响了？（系统确认 + 夜色独坐）
"""

import os
import sys
import yaml
import time
import json
from pathlib import Path
from datetime import datetime

# 将 novel-os 核心加入路径
sys.path.insert(0, str(Path(__file__).parent.parent / "novel-os"))

from core.anti_detect_reviser import AntiDetectReviser

# 配置
API_KEY = os.environ.get("OPENAI_API_KEY", "")
API_BASE = "https://api.deepseek.com/v1"
MODEL = "deepseek-chat"
TEMPERATURE = 1.0
MAX_TOKENS = 12000
TARGET_WORDS = 2200
TOLERANCE = 300
MIN_WORDS = 1900
MAX_WORDS = 2600

# 输出目录
OUTPUT_DIR = Path(r"D:\noveos\post_reform_chapters")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 辞林数据
SCENE_LEXICON = {
    "ch1": {
        "scene_types": ["解约/告别", "返乡/归家"],
        "emotion_subtypes": ["被抛弃的尊严", "熟悉中的陌生"],
        "lexicon_entries": [
            {"word": "纸很薄", "context": "合同/协议被撕毁时，用纸张的物理特性反衬决定的轻率"},
            {"word": "椅子又响了一声", "context": "身体动作泄露情绪，不是动作本身而是家具的回应"},
            {"word": "教练的声音很平静，像在念一份早就背好的稿子", "context": "权威者的冷漠，用'背稿'暗示决定的非个人性"},
            {"word": "碎片落在地上", "context": "撕毁的东西落下，用碎片而非整体暗示关系的破裂"},
            {"word": "那盆绿萝", "context": "离开时指向无关之物，暗示自己已经不在这个空间里"},
            {"word": "草长得有膝盖高", "context": "用身体的参照物衡量荒废，而非直接说'荒废'"},
            {"word": "球门框上挂着一只破鞋", "context": "用荒诞的细节暗示被遗忘，破鞋在风中晃"},
            {"word": "地上还有几块碎砖头", "context": "孩子们留下的痕迹，暗示这里还有人在用，只是不是你了"},
        ],
        "taboo": ["其实", "说白了", "归根结底", "值得注意的是", "可以理解", "缓缓", "微微", "淡淡", "轻轻", "默默", "悄然"],
        "character_address": {
            "陆远舟": {
                "愤怒": ["你的膝盖，还能支撑全场冲刺吗？", "态度？我他妈在这支球队踢了八年。", "不能什么？", "那你让谁上？"],
                "悲伤": ["我走。", "那盆绿萝。再不浇水就真死了。", "疼。但还能顶住。"],
                "对弟弟": ["你跑得比风快，但射门像瞎子。", "我说人够了。开始。", "你抬脚时重心偏了3厘米。"],
            }
        }
    },
    "ch2": {
        "scene_types": ["系统觉醒", "伤病发作"],
        "emotion_subtypes": ["疼痛中的幻觉", "被迫接受", "旧伤的警报"],
        "lexicon_entries": [
            {"word": "声音直接在他脑子里响", "context": "系统不是外部声音，而是颅内体验，强调侵入性"},
            {"word": "像有人站在颅骨里说话", "context": "用空间比喻形容声音的压迫感，颅骨是密闭的"},
            {"word": "眼睛猛地烧了一下", "context": "激活不是舒适的，而是灼痛的，强调代价"},
            {"word": "像有人拿烧红的铁丝往眼球上按", "context": "极端的痛感比喻，必须用金属+高温的组合"},
            {"word": "绑定强制完成", "context": "系统用强制语气，暗示主角的被动性"},
            {"word": "他等了五秒，又等了三秒", "context": "用精确的时间等待反衬无回应的荒谬"},
            {"word": "操，撞出幻觉了", "context": "用脏话否认现实，是主角的典型防御机制"},
            {"word": "膝盖又疼了", "context": "'又'字暗示这是常态，不是突发事件"},
            {"word": "像有人拿生锈的锥子往骨头缝里钻", "context": "用工具+钝感的组合形容旧伤，不是尖锐而是钝痛"},
            {"word": "咔嗒响了一声", "context": "用骨骼的声音代替疼痛描述，暗示结构性损坏"},
        ],
        "taboo": ["其实", "说白了", "归根结底", "值得注意的是", "可以理解", "缓缓", "微微", "淡淡", "轻轻", "默默", "悄然", "太神奇了", "感谢系统", "我要变强了"],
        "character_address": {
            "陆远舟": {
                "对系统": ["操，撞出幻觉了。", "你他妈是什么？", "新手任务？"],
                "疼痛": ["疼。", "咔嗒响了一声。", "膝盖又疼了。"],
            }
        }
    },
    "ch3": {
        "scene_types": ["初次训练", "碾压/打脸"],
        "emotion_subtypes": ["被围观的窘迫", "隐藏实力", "不动声色的碾压"],
        "lexicon_entries": [
            {"word": "笑声像石子砸过来", "context": "用物理痛感比喻嘲笑，强调攻击性"},
            {"word": "陆小虎咬指甲，指甲盖被啃得秃了皮", "context": "用身体的小动作泄露焦虑，重复两次强调紧张"},
            {"word": "球门框在太阳底下发白", "context": "用环境的光学现象反衬主角的黯淡"},
            {"word": "直播间标题叫什么？", "context": "用自嘲的口吻确认自己的处境，主角的嘴臭防御"},
            {"word": "左膝隐隐发烫", "context": "旧伤不是疼痛而是'发烫'，暗示身体在抗议"},
            {"word": "趁机按了按膝盖", "context": "用'趁机'暗示动作需要掩饰，不是公开的"},
            {"word": "疼，但还能顶住", "context": "简短陈述，不抒情，是主角的硬汉风格"},
            {"word": "你抬脚时重心偏了3厘米", "context": "用精确数据碾压，不是感觉而是测量"},
            {"word": "球像被钉在了草地上", "context": "用反常的物理现象形容碾压，球不该停的地方停了"},
            {"word": "鼓楼视野，开", "context": "技能释放时简短命令式，不解释"},
        ],
        "taboo": ["其实", "说白了", "归根结底", "值得注意的是", "可以理解", "缓缓", "微微", "淡淡", "轻轻", "默默", "悄然", "加油", "我相信你", "你真的很厉害"],
        "character_address": {
            "陆远舟": {
                "对围观": ["直播间标题叫什么？", "够真实吧？", "我说人够了。开始。"],
                "碾压": ["你抬脚时重心偏了3厘米。", "你跑得比风快，但射门像瞎子。", "球像被钉在了草地上。"],
                "对弟弟": ["你跑得比风快，但射门像瞎子。", "我说人够了。开始。", "你抬脚时重心偏了3厘米。"],
            },
            "陆小虎": {
                "紧张": ["哥，要不……算了吧。", "我是不是真的不行？", "（咬指甲，指甲盖被啃得秃了皮）"],
            }
        }
    },
    "ch4": {
        "scene_types": ["碾压/打脸", "初次训练"],
        "emotion_subtypes": ["不动声色的碾压", "隐藏实力"],
        "lexicon_entries": [
            {"word": "球像被钉在了草地上", "context": "用反常的物理现象形容碾压，球不该停的地方停了"},
            {"word": "鼓楼视野，开", "context": "技能释放时简短命令式，不解释"},
            {"word": "七个踢个屁", "context": "用粗话表达现实，不是抱怨而是陈述"},
            {"word": "笑声像石子砸过来", "context": "用物理痛感比喻嘲笑，强调攻击性"},
            {"word": "直播间标题叫什么？", "context": "用自嘲的口吻确认自己的处境，主角的嘴臭防御"},
            {"word": "左膝隐隐发烫", "context": "旧伤不是疼痛而是'发烫'，暗示身体在抗议"},
            {"word": "弹幕飘过——", "context": "用破折号制造停顿，暗示弹幕是流动的、不可控的"},
            {"word": "这什么鬼", "context": "短句，无标点，符合直播弹幕的语言风格"},
        ],
        "taboo": ["其实", "说白了", "归根结底", "值得注意的是", "可以理解", "缓缓", "微微", "淡淡", "轻轻", "默默", "悄然"],
        "character_address": {
            "陆远舟": {
                "碾压": ["你抬脚时重心偏了3厘米。", "球像被钉在了草地上。", "鼓楼视野，开。"],
                "对弹幕": ["直播间标题叫什么？", "够真实吧？"],
            },
            "吴小银": {
                "调侃": ["《侗寨瘸子踢球实录》。够真实吧？", "（眨眼）"],
            }
        }
    },
    "ch5": {
        "scene_types": ["系统觉醒", "夜色独坐"],
        "emotion_subtypes": ["被迫接受", "独处时的真相"],
        "lexicon_entries": [
            {"word": "绑定强制完成", "context": "系统用强制语气，暗示主角的被动性"},
            {"word": "他等了五秒，又等了三秒", "context": "用精确的时间等待反衬无回应的荒谬"},
            {"word": "操，撞出幻觉了", "context": "用脏话否认现实，是主角的典型防御机制"},
            {"word": "天阴沉沉的", "context": "天气不是背景，而是情绪的延迟释放"},
            {"word": "像一只困在笼子里的苍蝇", "context": "用被困的昆虫比喻主角的状态，小而烦躁"},
            {"word": "玻璃冰凉，能闻到一股柴油味", "context": "用多感官细节（触觉+嗅觉）堆叠独处时的感官放大"},
            {"word": "寨子里的灯还没全亮", "context": "天快黑了但还没完全黑，暗示尴尬的时间点"},
            {"word": "炊烟从屋顶飘起来", "context": "别人家的生活还在继续，你只是一个路过的人"},
        ],
        "taboo": ["其实", "说白了", "归根结底", "值得注意的是", "可以理解", "缓缓", "微微", "淡淡", "轻轻", "默默", "悄然"],
        "character_address": {
            "陆远舟": {
                "对系统": ["操，撞出幻觉了。", "你他妈是什么？", "新手任务？"],
                "独处": ["疼。", "天阴沉沉的。", "玻璃冰凉。"],
            }
        }
    }
}

# 章节大纲（匹配原著前5章）
CHAPTER_OUTLINES = {
    1: {
        "title": "暴击开局——被职业抛弃的人，连村队都不要",
        "beats": [
            "省队训练基地，教练递解约协议，陆远舟膝盖旧伤被戳穿",
            "陆远舟撕毁协议，嘴臭怼教练（王磊他爸捐钱上位），摔门离开",
            "回村长途班车上，回忆碎片，窗外景色从城市变山林",
            "到达榕江侗寨，天快黑了，球场荒废，草长膝盖高，破鞋挂球门",
            "杨阿婆（侗族长老）出现，铜鼓响起，血滴铜鼓——系统觉醒前兆",
        ],
        "key_scene": "解约告别 + 返乡归家",
        "lexicon_chapter": "ch1",
    },
    2: {
        "title": "侗神瞳觉醒——千年铜鼓里的第三只眼",
        "beats": [
            "陆远舟跪在铜鼓前，额头流血，膝盖剧痛",
            "系统声音颅内响起：'绑定倒计时：10秒'，'检测到侗族血脉——侗神瞳，激活中'",
            "眼睛灼痛，看到金色网格（鼓楼视野雏形），系统绑定完成",
            "陆远舟否认现实（'撞出幻觉了'），但身体反应（咔嗒声）无法否认",
            "走出鼓楼，发现空球场，尝试新手任务（有效射门），解锁'鼓楼视野'",
        ],
        "key_scene": "系统觉醒 + 伤病发作",
        "lexicon_chapter": "ch2",
    },
    3: {
        "title": "第一次小规模打脸——鼓楼视野，开！",
        "beats": [
            "陆小虎召集七人（含陆远舟），村民嘲笑'七个踢个屁'",
            "吴小银开直播，标题《侗寨瘸子踢球实录》，在线3人",
            "五对二对抗，陆小虎失误，村民哄笑，辣条小孩围观",
            "陆远舟开启鼓楼视野，看穿对手重心偏3厘米，精准拦截+传球",
            "陆小虎射门得分，直播弹幕从嘲讽转震惊，第一个打脸时刻",
        ],
        "key_scene": "初次训练 + 被围观的窘迫",
        "lexicon_chapter": "ch3",
    },
    4: {
        "title": "七个人踢个屁",
        "beats": [
            "直播在线人数增长到50人，弹幕开始认真讨论",
            "陆远舟继续用鼓楼视野指导防守，七人队打出配合",
            "对手（邻村青年队）加强进攻，陆远舟膝盖旧伤发作（隐隐发烫）",
            "关键时刻陆远舟忍痛开启鼓楼视野第二阶段，看穿全场轨迹",
            "绝杀传球，陆小虎帽子戏法，直播弹幕爆炸，'这瘸子开挂了吧'",
        ],
        "key_scene": "碾压/打脸 + 隐藏实力",
        "lexicon_chapter": "ch4",
    },
    5: {
        "title": "铜山响了？",
        "beats": [
            "比赛结束后，陆远舟独自坐在球场边，膝盖疼得冒汗",
            "吴小银直播复盘，粉丝数突破200，弹幕求'瘸子哥'继续播",
            "系统提示：新手任务完成，奖励'鼓楼视野'永久解锁，声浪值+50",
            "陆远舟查看属性面板（系统数据可视化），发现自己的真实数据和潜力",
            "夜色中，杨阿婆再次出现，铜鼓又响了一声——暗示更大的秘密",
        ],
        "key_scene": "系统觉醒 + 夜色独坐",
        "lexicon_chapter": "ch5",
    }
}


def build_lexicon_prompt(chapter_num: int) -> str:
    """构建辞林式写作指令（v1.2 防重复版）。"""
    outline = CHAPTER_OUTLINES[chapter_num]
    lexicon = SCENE_LEXICON[outline["lexicon_chapter"]]
    
    # 选取词条（每章用 4-5 个，按章节偏移打散，避免相邻章重复）
    entries = lexicon["lexicon_entries"]
    offset = (chapter_num - 1) % max(1, len(entries) - 4)
    selected = entries[offset:offset+5]
    if len(selected) < 5:
        selected += entries[:5 - len(selected)]
    
    # 去重：同一个 word 只出现一次
    seen_words = set()
    deduped = []
    for e in selected:
        w = e.get("word", "")
        if w and w not in seen_words:
            seen_words.add(w)
            deduped.append(e)
    selected = deduped
    
    prompt = f"""# 第{chapter_num}章：{outline['title']}

## 本章任务卡

**场景类型**：{', '.join(lexicon['scene_types'])}
**情绪子类**：{', '.join(lexicon['emotion_subtypes'])}
**字数目标**：{TARGET_WORDS}±{TOLERANCE}字

---

## 场景辞林调用（必须选用以下词条，直接嵌入描写）

**关键规则**：每个词条不能只用1句带过。必须按"因果链"展开，每组因果链至少80字。

"""
    
    # 因果链定义
    causal_chains = {
        2: [
            ("咔嗒响了一声", "像有人拿烧红的铁丝往眼球上按", "因果关系：骨骼的机械故障 → 神经的灼痛感受"),
            ("声音直接在他脑子里响", "绑定强制完成", "递进关系：从感知异常 → 被动接受"),
        ],
        5: [
            ("天阴沉沉的", "玻璃冰凉", "并列关系：外部环境 → 身体触感，共同指向心理状态"),
            ("他等了五秒，又等了三秒", "像一只困在笼子里的苍蝇", "因果关系：无回应的等待 → 自我认知的崩塌"),
        ],
    }
    
    # 普通词条（非因果链）
    for i, entry in enumerate(selected, 1):
        prompt += f"""### 词条{i}：{entry['word']}
- **适用语境**：{entry['context']}
- **使用方式**：直接嵌入正文，不要加引号或解释。
- **展开要求**：这个词条出现时必须附带至少2句的上下文展开（写前因、后果、或周边细节）。

"""
    
    # 因果链（第2/5章专用）
    if chapter_num in causal_chains:
        prompt += "---\n\n## 因果链（必须执行，每组至少80字）\n\n"
        for i, (cause, effect, relation) in enumerate(causal_chains[chapter_num], 1):
            prompt += f"""### 因果链{i}：{cause} → {effect}
- **关系**：{relation}
- **展开步骤**（按顺序执行）：
  1. 先写"{cause}"的物理细节（来源、质感、声音的质地、身体的即时反应）
  2. 再写中间过渡（身体或环境的变化，时间感或空间感的扭曲）
  3. 然后写"{effect}"的爆发瞬间（不是突然发生，是累积后的必然）
  4. 最后写余波（身体或环境的后续状态，不是结束而是新的开始）
- **字数要求**：本因果链段落合计不少于80字。

"""
    
    prompt += f"""---

## 对话红线（角色台词禁止出现以下词汇）

"""
    for taboo in lexicon["taboo"]:
        prompt += f"- **{taboo}**（红线词，任何角色台词中禁用）\n"
    
    prompt += f"""
---

## 角色词汇地址（这些角色在以下情境下只能说这些话）

"""
    for char, situations in lexicon.get("character_address", {}).items():
        prompt += f"**{char}**：\n"
        for situation, lines in situations.items():
            prompt += f"  - {situation}时：{', '.join(lines)}\n"
        prompt += "\n"
    
    prompt += f"""---

## 情节节拍（按顺序展开）

"""
    for i, beat in enumerate(outline["beats"], 1):
        prompt += f"{i}. {beat}\n"
    
    prompt += f"""
---

## 写作规则（违反任何一条 = 重写）

1. **词条展开**：每个词条不能只用1句带过。必须写前因、后果或周边细节，至少2句上下文。
2. **因果链执行**：第{chapter_num}章的因果链必须按"展开步骤"1-2-3-4顺序写，不能跳过。
3. **字数补偿**：当前字数偏低，需要通过"展开"补足。每展开一个词条=增加30-40字。
4. **短句优先**：紧张场景每句不超过15字，制造窒息感。直播弹幕单独成段，无标点。
5. **感官顺序**：听觉>视觉>触觉。先写声音，再写画面，最后写身体感觉。
6. **情绪不写标签**：不准写"他很愤怒""她很悲伤"，用身体动作和对话表达。
7. **系统提示音**：单独成段，用引号，简短命令式。但系统面板数据不超过5行（属性列表禁止大段展开）。
8. **直播弹幕**：用引号直接插入，打断叙事节奏，占比10-15%。弹幕语言要短、碎、真实。
9. **章末钩子**：最后一句话必须留下悬念或转折，让读者必须点下一章。
10. **第一人称**：主角内心用"我"，但外部叙事保持客观视角。
11. **禁止使用概括性时间**：不准用"过了一会儿""不久之后""几天后"。
12. **"了"字控制**：每个自然段最多出现1个"了"字。超过则改写为状态描述（"球飞了"→"球飞出去"）。
13. **词条反重复**：本文选出的词条每个只能出现1次。禁止同一比喻、同一短语、同一句式在2200字内重复出现两次以上。

---

## 输出格式

直接输出正文，不要加任何解释、分析、总结。
标题格式：# 第X章：XXX
每章开头用标题，然后直接开始正文。

现在开始写第{chapter_num}章。
"""
    
    return prompt


def call_llm(prompt: str) -> str:
    """调用 DeepSeek API，失败时使用备用 Key。"""
    api_keys = [
        os.environ.get("OPENAI_API_KEY", ""),
        os.environ.get("OPENAI_API_KEY_FALLBACK", ""),
    ]
    
    for i, api_key in enumerate(api_keys):
        if not api_key:
            continue
        try:
            import openai
            client = openai.OpenAI(api_key=api_key, base_url=API_BASE)
            
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "你是一位精通《写作辞林1982》体例的小说写作专家。你写的每一章都必须从给定的'场景辞林'中选取词条嵌入，并严格遵守'对话红线'。你的目标是写出有强烈画面感、节奏感、直播沉浸感的体育系统文。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                timeout=300,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"[ERROR] API Key {i+1} failed: {e}")
            if i < len(api_keys) - 1:
                print("[RETRY] 尝试备用 Key...")
                continue
            return None
    return None


def post_process(text: str) -> str:
    """后处理：应用 AntiDetectReviser。"""
    reviser = AntiDetectReviser()
    return reviser.revise(text, aggressiveness=0.7)


def count_chinese_words(text: str) -> int:
    """计算中文字数。"""
    return sum(1 for c in text if '\u4e00' <= c <= '\u9fff')


def generate_chapter(chapter_num: int) -> dict:
    """生成单章。"""
    print(f"\n{'='*60}")
    print(f"生成第{chapter_num}章...")
    print(f"{'='*60}")
    
    # 构建辞林式 prompt
    prompt = build_lexicon_prompt(chapter_num)
    
    # 保存 prompt 用于调试
    prompt_path = OUTPUT_DIR / f"prompt_ch{chapter_num:03d}.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    print(f"[保存] Prompt -> {prompt_path}")
    
    # 调用 LLM
    print("[调用] DeepSeek API...")
    raw_text = call_llm(prompt)
    if not raw_text:
        return {"ok": False, "reason": "API调用失败", "text": ""}
    
    # 后处理
    print("[处理] 应用 AntiDetectReviser...")
    processed_text = post_process(raw_text)
    
    # 字数检查
    wc = count_chinese_words(processed_text)
    print(f"[字数] {wc} 字")
    
    # 检查红线残留
    lexicon = SCENE_LEXICON[CHAPTER_OUTLINES[chapter_num]["lexicon_chapter"]]
    violations = [w for w in lexicon["taboo"] if w in processed_text]
    if violations:
        print(f"[警告] 发现红线残留: {violations}")
    
    # 保存
    output_path = OUTPUT_DIR / f"post_ch{chapter_num:03d}.txt"
    output_path.write_text(processed_text, encoding="utf-8")
    print(f"[保存] 正文 -> {output_path}")
    
    ok = MIN_WORDS <= wc <= MAX_WORDS and len(violations) == 0
    return {
        "ok": ok,
        "word_count": wc,
        "violations": violations,
        "text": processed_text,
    }


def main():
    print("="*60)
    print("辞林式前5章生成系统 v1.0")
    print("基于《写作辞林1982》体例改造")
    print("="*60)
    
    # 加载环境变量
    env_path = Path(r"D:\noveos\.env")
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip() and not line.startswith("#") and "=" in line:
                    key, value = line.strip().split("=", 1)
                    os.environ[key] = value
    
    global API_KEY
    API_KEY = os.environ.get("OPENAI_API_KEY", "")
    
    if not os.environ.get("OPENAI_API_KEY", ""):
        print("[错误] 无法获取 API Key，退出")
        return
    
    results = []
    for ch in range(1, 6):
        result = generate_chapter(ch)
        if result is None:
            result = {"ok": False, "reason": "API调用失败", "word_count": 0, "violations": [], "text": ""}
        results.append(result)
        if not result["ok"]:
            print(f"[第{ch}章] 生成未达标，原因: {result.get('reason', '未知')}")
        time.sleep(5)  # 避免API限流
    
    # 总结
    print("\n" + "="*60)
    print("生成总结")
    print("="*60)
    for i, r in enumerate(results, 1):
        status = "✅ 通过" if r["ok"] else "❌ 未通过"
        print(f"第{i}章: {status} | 字数: {r['word_count']} | 红线: {r['violations']}")
    
    print(f"\n输出目录: {OUTPUT_DIR}")
    print("对比命令: 对比 pre_reform_chapters vs post_reform_chapters")


if __name__ == "__main__":
    main()
