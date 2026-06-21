"""风格规则库——基于多风格小说样本分析

为 Novel-OS 写作系统提供去 AI 味风格规则，供 PromptBuilder 和 ChapterValidator 使用。
"""

from typing import Dict, List, Any


class StyleRules:
    """风格规则库——基于多风格小说样本分析"""

    # ──────────────────────────────────────────────
    # 一、题材风格画像（句长/段落/对话/情绪等）
    # ──────────────────────────────────────────────
    GENRE_PROFILES: Dict[str, Dict[str, Any]] = {
        "urban_rebirth": {
            "name": "都市重生",
            "sentence_length": {"mean": 20, "min": 15, "max": 25, "cv": 0.6},
            "paragraph_length": {"mean": 2, "min": 1, "max": 3},
            "dialogue_ratio": 0.50,
            "dialogue_tags": ["骂道", "笑道", "打断", "嘟囔", "吼道"],
            "dialogue_style": "口语化，网络化，带情绪",
            "opening_pattern": "先写巅峰状态，再重生反差",
            "emotion_expression": "高频率+口语化",
            "emotion_density": "高",
            "sensory": {"visual": 3, "auditory": 3, "tactile": 3, "smell": 2, "taste": 2},
            "tone": "快节奏，对话推动，生活化",
            "forbidden_words": ["非常", "特别", "极其", "格外", "分外"],
        },
        "fantasy": {
            "name": "玄幻",
            "sentence_length": {"mean": 25, "min": 20, "max": 30, "cv": 0.5},
            "paragraph_length": {"mean": 4, "min": 3, "max": 5},
            "dialogue_ratio": 0.40,
            "dialogue_tags": ["说道", "问道", "回答", "叫道", "沉声道"],
            "dialogue_style": "正式，带设定信息",
            "opening_pattern": "直接进入世界，交代背景",
            "emotion_expression": "情绪随剧情起伏",
            "emotion_density": "中",
            "sensory": {"visual": 4, "auditory": 3, "tactile": 3, "smell": 2, "taste": 2},
            "tone": "描述性强，信息量大，世界观铺陈",
            "forbidden_words": ["很", "非常", "特别", "极其"],
        },
        "romance": {
            "name": "言情",
            "sentence_length": {"mean": 17, "min": 15, "max": 20, "cv": 0.7},
            "paragraph_length": {"mean": 3, "min": 2, "max": 4},
            "dialogue_ratio": 0.30,
            "dialogue_tags": ["轻声说", "沉默", "点头", "摇头", "低声道"],
            "dialogue_style": "含蓄，暗示，留白；少用标签，多用动作",
            "opening_pattern": "久别重逢，环境烘托",
            "emotion_expression": "细腻，多层次",
            "emotion_density": "高",
            "sensory": {"visual": 3, "auditory": 2, "tactile": 2, "smell": 2, "taste": 1},
            "tone": "舒缓，留白，情感细腻",
            "forbidden_words": ["很", "非常", "特别", "极其", "格外"],
        },
        "suspense": {
            "name": "悬疑",
            "sentence_length": {"mean": 15, "min": 10, "max": 20, "cv": 0.8},
            "paragraph_length": {"mean": 2, "min": 1, "max": 3},
            "dialogue_ratio": 0.40,
            "dialogue_tags": ["大吼", "大叫", "咳嗽", "低吼", "颤声道"],
            "dialogue_style": "方言，粗话，真实感",
            "opening_pattern": "直接进入恐怖场景",
            "emotion_expression": "恐惧、紧张、绝望",
            "emotion_density": "极高",
            "sensory": {"visual": 5, "auditory": 5, "tactile": 5, "smell": 3, "taste": 3},
            "tone": "紧张，快节奏，短句制造紧张感",
            "forbidden_words": ["很", "非常", "特别", "极其", "格外"],
        },
        "system": {
            "name": "系统流",
            "sentence_length": {"mean": 20, "min": 15, "max": 25, "cv": 0.6},
            "paragraph_length": {"mean": 2, "min": 1, "max": 3},
            "dialogue_ratio": 0.45,
            "dialogue_tags": ["笑道", "茫然", "激动", "吐槽", "兴奋道"],
            "dialogue_style": "网络化，中二，热血",
            "opening_pattern": "重生确认+世界观颠覆",
            "emotion_expression": "中二、热血、幽默",
            "emotion_density": "高",
            "sensory": {"visual": 3, "auditory": 3, "tactile": 2, "smell": 2, "taste": 1},
            "tone": "网络化，碎片化，中二感",
            "forbidden_words": ["非常", "特别", "极其", "格外"],
        },
    }

    # ──────────────────────────────────────────────
    # 二、去 AI 味核心规则（5 条）
    # ──────────────────────────────────────────────
    DE_AI_RULES: List[Dict[str, Any]] = [
        {
            "id": 1,
            "name": "用细节代替概括",
            "description": "将概括性情绪描述替换为具体细节描写",
            "ai_pattern": "概括性形容词 + 情绪词（他很X）",
            "examples": [
                {"ai": "他很累", "human": "仰头靠在真皮座椅上，脸上露出深深的疲倦"},
                {"ai": "他很害怕", "human": "顿觉得头皮发麻，胃里一阵翻腾"},
                {"ai": "他很高兴", "human": "不盲目地带着浅笑，简直是用感谢的心境倾听"},
                {"ai": "他很惊讶", "human": "满脑子浆糊，满脸的茫然，整个人都傻了"},
                {"ai": "他很绝望", "human": "苦笑了一声，索性就趴在地上等死"},
            ],
        },
        {
            "id": 2,
            "name": "用动作代替状态",
            "description": "将状态描述替换为具体动作或行为",
            "ai_pattern": "状态动词（拒绝了/逃跑了/摔倒了）",
            "examples": [
                {"ai": "他拒绝了", "human": "洒然一笑，不动声色的坐下"},
                {"ai": "他逃跑了", "human": "一把接住土耗子扭头就跑！一口气跑出有两里多地"},
                {"ai": "他摔倒了", "human": "脚下一绊，一个狗吃屎扑了出去，整张脸磕在一树墩上"},
                {"ai": "他中毒了", "human": "嗓子一甜，胆汁都被踩吐了出来。一阵奇痒从背上传来"},
                {"ai": "他重生了", "human": "脑袋突然有点晕，这俗套的桥段居然在自己身上发生了"},
            ],
        },
        {
            "id": 3,
            "name": "用对话推动剧情",
            "description": "用对话替代叙述性说明，增强现场感",
            "ai_pattern": "叙述性说明（他的朋友提醒他）",
            "examples": [
                {"ai": "他的朋友提醒他", "human": "\"狗日的陈汉升，你是不是咒我早点死？\""},
                {"ai": "他的下属建议", "human": "\"陈总，我送您回去。\" \"不用。\""},
                {"ai": "同学们很兴奋", "human": "\"马宗师突破八品了！\" \"真的假的？\""},
                {"ai": "盗墓者很害怕", "human": "\"三伢子，快跑！！！！！！\""},
            ],
        },
        {
            "id": 4,
            "name": "用环境暗示情绪",
            "description": "通过环境描写暗示人物情绪，而非直接陈述",
            "ai_pattern": "直接陈述情绪（他很孤独/压抑）",
            "examples": [
                {"ai": "他很孤独", "human": "天空湛蓝无云，马路还是泥土的，扬起的飞尘在阳光下一粒粒看的很清楚"},
                {"ai": "他很压抑", "human": "每次应酬后除了胃里满满的酒水，心情总是莫名的压抑，甚至还有一种不知所措的空虚"},
                {"ai": "他很迷茫", "human": "这剧本，好像有些不对劲啊！"},
                {"ai": "他很紧张", "human": "然后就是死一般的沉寂"},
            ],
        },
        {
            "id": 5,
            "name": "用生理反应代替心理描写",
            "description": "用生理反应描写替代直接心理叙述",
            "ai_pattern": "直接心理描写（他很紧张/害怕）",
            "examples": [
                {"ai": "他很紧张", "human": "喉咙再次鼓动了一下，觉得自己嘴唇有些干燥的厉害"},
                {"ai": "他很害怕", "human": "胃里一阵翻涌，忍不住走到路边吐了起来"},
                {"ai": "他很激动", "human": "眼睛突然瞪大了"},
                {"ai": "他很绝望", "human": "手脚都开始凉起来，按他以往的经验，现在他裤裆里肯定大小便一大堆"},
            ],
        },
    ]

    # ──────────────────────────────────────────────
    # 三、AI 味检测关键词
    # ──────────────────────────────────────────────
    AI_FINGERPRINTS: List[str] = [
        "很", "非常", "特别", "极其", "格外", "分外",
        "十分", "相当", "无比", "异常", "特别地",
        "他感到", "她觉得", "心中涌起", "内心深处",
        "不禁", "不由得", "下意识", "不由自主地",
        "突然意识到", "猛然发现", "恍然大悟",
        "一时间", "刹那间", "瞬间", "顷刻间",
        "陷入了沉思", "陷入了回忆", "陷入了沉默",
        "眼中闪过", "嘴角微微", "脸上露出",
        "不知道为什么", "不知为何", "不知怎的",
        "一种说不出的", "一种难以言喻的",
        "仿佛", "似乎", "好像", "宛如", "犹如",
    ]

    # ──────────────────────────────────────────────
    # 四、开篇模板
    # ──────────────────────────────────────────────
    OPENING_TEMPLATES: Dict[str, Dict[str, str]] = {
        "fantasy": {
            "pattern": "直接进入世界，交代背景",
            "example": "斗罗大陆，天斗帝国西南，法斯诺行省",
            "guideline": "开篇直接交代世界观背景，用具体地名、势力名建立世界感，避免抒情或回忆",
        },
        "urban_rebirth": {
            "pattern": "先写巅峰状态，再重生反差",
            "example": "35岁钻石王老五 → 18岁高中生",
            "guideline": "先写主角巅峰状态（事业/地位/年龄），然后用突发事件（死亡/意外）切入重生，形成强烈反差",
        },
        "romance": {
            "pattern": "久别重逢，环境烘托",
            "example": "再次见到他，是在七年之后，一家拥堵的超市",
            "guideline": "用环境描写烘托情感氛围，重逢场景要有时间跨度（多年未见），避免直接抒情",
        },
        "suspense": {
            "pattern": "直接进入恐怖场景",
            "example": "50年前，长沙镖子岭。四个土夫子正蹲在一个土丘上",
            "guideline": "开篇直接进入危险/恐怖场景，用具体时间地点建立真实感，短句制造紧张",
        },
        "system": {
            "pattern": "重生确认+世界观颠覆",
            "example": "方平花了半小时，总算确定了一件事，不是做梦",
            "guideline": "主角花一定时间确认重生/穿越事实，然后发现世界观与记忆不符，形成颠覆感",
        },
    }

    # ──────────────────────────────────────────────
    # 五、风格化改写对照（同一场景不同风格）
    # ──────────────────────────────────────────────
    STYLE_REWRITE_EXAMPLES: Dict[str, str] = {
        "fantasy": (
            "天刚蒙蒙亮，远处东方升起一抹淡淡的鱼肚白色。\n"
            "男孩儿在山顶上坐了下来，他的双眼死死的盯视着东方那抹渐渐明亮的鱼肚白色，\n"
            "鼻间缓缓吸气，再从口中徐徐吐出。"
        ),
        "urban_rebirth": (
            "迷迷糊糊之间，陈汉升被一个声音吵醒，睁眼是耀目的阳光，脑袋是酒后的刺痛。\n"
            "\"妈的，下次坚决不能喝这么多酒了。\"陈汉升皱着眉头骂道。"
        ),
        "romance": (
            "再次见到他，是在七年之后，一家拥堵的超市。\n"
            "赵默笙单独推着购物车，困难地在人群中走走停停。\n"
            "刚刚从国外回来的她，还不太顺应这样的拥堵。"
        ),
        "suspense": (
            "老三虽然被他二哥欺负的紧，但是兄弟之间的感情很深，\n"
            "一想到这次可能真的出大事情了，脑子就一热，就想豁出去救他二哥和老爹，\n"
            "刚一回头，突然看见背后的芦苇丛里，蹲着个血红血红的东西，似乎正直钩钩看着他。"
        ),
        "system": (
            "方平花了半小时，总算确定了一件事，不是做梦。\n"
            "不是拍戏——废话，拍戏能让自己那些同学返老还童，这剧组可以上天了！"
        ),
    }

    # ──────────────────────────────────────────────
    # 工具方法
    # ──────────────────────────────────────────────
    @classmethod
    def get_profile(cls, genre: str) -> Dict[str, Any]:
        """获取指定题材的风格画像"""
        return cls.GENRE_PROFILES.get(genre, {})

    @classmethod
    def get_de_ai_rules(cls) -> List[Dict[str, Any]]:
        """获取全部去 AI 味规则"""
        return cls.DE_AI_RULES

    @classmethod
    def get_opening_template(cls, genre: str) -> Dict[str, str]:
        """获取指定题材的开篇模板"""
        return cls.OPENING_TEMPLATES.get(genre, {})

    @classmethod
    def get_style_rewrite(cls, genre: str) -> str:
        """获取指定题材的风格化改写示例"""
        return cls.STYLE_REWRITE_EXAMPLES.get(genre, "")

    @classmethod
    def detect_ai_fingerprints(cls, text: str) -> List[str]:
        """检测文本中的 AI 味指纹词"""
        found = []
        for fp in cls.AI_FINGERPRINTS:
            if fp in text:
                found.append(fp)
        return found

    @classmethod
    def get_forbidden_words(cls, genre: str) -> List[str]:
        """获取指定题材的禁用词列表"""
        profile = cls.get_profile(genre)
        return profile.get("forbidden_words", [])

    @classmethod
    def get_all_genres(cls) -> List[str]:
        """获取所有支持的题材列表"""
        return list(cls.GENRE_PROFILES.keys())

    @classmethod
    def validate_text(cls, text: str, genre: str) -> Dict[str, Any]:
        """验证文本是否符合指定题材的风格特征

        返回包含检测结果的字典，供 ChapterValidator 使用。
        """
        profile = cls.get_profile(genre)
        if not profile:
            return {"valid": False, "error": f"未知题材: {genre}"}

        import re

        # 1. 检测 AI 指纹词
        fingerprints = cls.detect_ai_fingerprints(text)

        # 2. 检测禁用词
        forbidden = []
        for word in profile.get("forbidden_words", []):
            if word in text:
                forbidden.append(word)

        # 3. 粗略句长分析
        sentences = re.split(r'[。！？\n]', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if sentences:
            avg_len = sum(len(s) for s in sentences) / len(sentences)
            target_mean = profile["sentence_length"]["mean"]
            target_min = profile["sentence_length"]["min"]
            target_max = profile["sentence_length"]["max"]
            sentence_ok = target_min <= avg_len <= target_max
        else:
            avg_len = 0
            sentence_ok = False

        # 4. 粗略段落分析
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        if paragraphs:
            avg_para = sum(len(re.split(r'[。！？]', p)) for p in paragraphs) / len(paragraphs)
            target_para_mean = profile["paragraph_length"]["mean"]
            target_para_max = profile["paragraph_length"]["max"]
            paragraph_ok = avg_para <= target_para_max + 1
        else:
            avg_para = 0
            paragraph_ok = False

        # 5. 对话占比
        dialogue_pattern = re.compile(r'["""](.*?)["""]')
        dialogues = dialogue_pattern.findall(text)
        dialogue_chars = sum(len(d) for d in dialogues)
        total_chars = len(text)
        dialogue_ratio = dialogue_chars / total_chars if total_chars > 0 else 0
        target_ratio = profile.get("dialogue_ratio", 0.4)
        ratio_ok = abs(dialogue_ratio - target_ratio) <= 0.15

        return {
            "valid": sentence_ok and paragraph_ok and ratio_ok and len(fingerprints) <= 3,
            "fingerprints": fingerprints,
            "forbidden_words": forbidden,
            "sentence_length": {"avg": round(avg_len, 1), "target": profile["sentence_length"], "ok": sentence_ok},
            "paragraph_length": {"avg": round(avg_para, 1), "target": profile["paragraph_length"], "ok": paragraph_ok},
            "dialogue_ratio": {"actual": round(dialogue_ratio, 2), "target": target_ratio, "ok": ratio_ok},
        }

    @classmethod
    def get_rules_for_genre(cls, genre: str) -> dict:
        """根据题材名称获取风格规则。供 PromptBuilder 使用。"""
        # 题材映射
        genre_map = {
            "都市": "urban_rebirth",
            "都市重生": "urban_rebirth",
            "现言": "romance",
            "言情": "romance",
            "古言": "romance",
            "玄幻": "fantasy",
            "仙侠": "fantasy",
            "武侠": "fantasy",
            "悬疑": "suspense",
            "恐怖": "suspense",
            "盗墓": "suspense",
            "系统": "system",
            "系统流": "system",
            "科幻": "system",
            "网游": "system",
            "穿越": "urban_rebirth",
            "历史": "urban_rebirth",
            "军事": "suspense",
            "竞技": "system",
        }
        
        style_key = genre_map.get(genre, "general")
        return cls.GENRE_PROFILES.get(style_key, {})
