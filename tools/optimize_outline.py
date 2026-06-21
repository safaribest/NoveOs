#!/usr/bin/env python3
"""执行全部大纲优化：修复严重问题+中等问题，优化章节内容。"""
import re
from pathlib import Path

PY_PATH = Path("books/村超系统：我带侗寨球队踢爆世界杯/book_data.py")
text = PY_PATH.read_text(encoding="utf-8")

# ── 1. 提取 OUTLINE 列表 ──
outline_start = text.find("OUTLINE = [")
outline_end = text.find("]\n\n# 2.")
ns = {}
exec(compile(text, '<string>', 'exec'), ns)
outline = ns["OUTLINE"]
ch_to_idx = {item["chapter"]: i for i, item in enumerate(outline)}

def mod(ch, **kwargs):
    """修改指定章节的字段"""
    idx = ch_to_idx[ch]
    for k, v in kwargs.items():
        outline[idx][k] = v

# ═══════════════════════════════════════════════════════
# P0 优化：缓冲章加隐藏爽点 + 固定黑粉
# ═══════════════════════════════════════════════════════

# 第3章：引入固定黑粉 @黑子一号
mod(3,
    core_event="主角说服堂弟陆小虎重组球队，训练赛中首次使用鼓楼视野，预判射门路线，围观村民从嘲笑到震惊。吴小银意外开启直播，直播间37人。@黑子一号刷弹幕：'开挂实锤，已录屏举报。'37人同时发了同样的弹幕：???",
    chapter_hook="陆远舟笑了：不是邪术，是神瞳。他不知道，村口吴小银的手机直播，把这画面全程录了下来。直播间37人，同时发了同样的弹幕：???")

# 第4章：加隐藏爽点（面板数字跳动）
mod(4,
    core_event="系统规则展开，面板首次展示具体数字跳动（声浪值37→42→51→68）。新人物登场：吴小银（直播方案）、杨阿婆（风水定首发）、潘石头（木匠替补）。球队困境：凑不齐球鞋。系统提示：检测到潜在直播运营人才，建议绑定吴小银为直播间管理员，声浪值获取效率+20%",
    face_slap_method="用直播思路化解——没有球鞋就直播'barefoot football'的反差感，网友被'职业队凑不齐鞋'逗笑，声浪值+50")

# 第5章：固定黑粉打脸 + 官方邀请
mod(5,
    core_event="首场直播友谊赛，对手是王富贵二队，上半场0:1落后。@黑子一号刷屏：'就这？前职业？'主角首次实战使用'铜鼓震步'，5秒爆发加速绝杀扳平，直播间从37人涨到800人。800条弹幕800个卧槽。@黑子一号沉默。贵州村超官方发来私信：请问贵队是否有意向参加正式村超联赛？",
    face_slap_target="王富贵二队/对手嘲讽/@黑子一号",
    face_slap_method="铜鼓震步实战——脚下闪过铜鼓纹涟漪，从两人之间穿过，单刀破门。直播间弹幕停滞2秒，然后800个卧槽刷屏。@黑子一号被当场打脸")

# 第6章：加隐藏爽点（买鞋直播意外开启）
mod(6,
    core_event="系统结算，属性升级。全队凑钱买混搭球鞋，直播意外开启，网友被'每人只买一只鞋'逗笑，声浪值意外暴涨+200。王富贵派人偷拍主角训练。主角膝盖旧伤复发，系统警告过度使用铜鼓震步将加速损伤。面板弹出：【警告：左膝半月板陈旧性损伤。建议寻找侗医传承修复方案】",
    face_slap_method="",
    chapter_hook="系统面板弹出：【警告：左膝半月板陈旧性损伤。过度使用铜鼓震步将加速损伤恶化。建议：寻找侗医传承修复方案。他想起村里那个神神叨叨的李医生。远处黑影举着手机，把主角跪地捂膝的画面录了下来。王富贵：继续跟。我要知道他到底有什么秘密。")

# 第8章：加隐藏爽点（@足球老炮 赌吃键盘小打脸）
mod(8,
    core_event="赛前战术布置，主角发现对手左路冲刺频率比右路低23%。网友投票选择4-3-3阵型，@足球老炮发弹幕'投4-3-3我直播吃键盘'，结果真选了4-3-3——小打脸。杨阿婆带全队跳踩堂歌热身，直播间网友被民族文化震撼。直播间在线突破12847人",
    face_slap_target="@足球老炮",
    face_slap_method="网友投票真选了4-3-3，@足球老炮的赌约弹幕被顶到最上面，点赞3421——小打脸预热",
    chapter_hook="直播间在线突破12,847人。@足球老炮发弹幕：'这场比赛如果他能赢，我直播吃键盘。'点赞3421。陆远舟笑了：出去。让他们看看，侗族人怎么踢球。")

# 第9章：加陆小虎发现弱点的小爽点
mod(9,
    core_event="上半场0:2落后，退役前锋梅开二度。主角未开系统，纯靠基本功硬撑。中场休息，陆小虎发现对手过人前左脚多垫半步——队友战术意识觉醒的小爽点。鼓楼视野被动积累完成，生成对手跑位热力图。主角睁开眼：下半场所有人给我往左路打，他的左腿已经没力了",
    husband_moment="陆小虎：哥，我发现那家伙每次过人前，左脚都会多垫半步。陆远舟愣了一下，然后笑了：你也看见了？系统面板弹出：【检测到队友战术意识觉醒。陆小虎观察力+1。】——队友成长的小爽点",
    chapter_hook="中场休息，比分0:2。陆远舟坐在角落，闭上眼睛。系统面板浮现：【上半场被动收集信息完成。鼓楼视野已生成对手跑位热力图。】他看到了——退役前锋左路冲刺频率比右路低23%。他的膝盖，确实撑不住了。陆远舟睁开眼，笑了。下半场，所有人给我往左路打。")

# ═══════════════════════════════════════════════════════
# P1 优化：压缩第1卷到35章 + 修复系统逻辑 + 结局彩蛋
# ═══════════════════════════════════════════════════════

# 第36-45章：修改 arc 为第二阶段（县赛预热），并优化内容
# 这些章原属第一阶段，现在作为第二阶段的预热
count = 0
for ch in range(36, 46):
    if ch in ch_to_idx:
        item = outline[ch_to_idx[ch]]
        item["arc"] = "第二阶段：县赛突围·直播破圈（预热）"
        count += 1
print(f"已将第36-45章的 arc 调整为第二阶段（{count}章）")

# 第186-200章：修复系统在美国不稳定的逻辑
# 核心修改：把"未知信仰体系冲突"改为"跨国直播延迟+时差干扰"
fixed_count = 0
for ch in range(186, 201):
    if ch in ch_to_idx:
        item = outline[ch_to_idx[ch]]
        old = item["core_event"]
        # 替换系统异常描述
        new = old.replace(
            "系统在进入美国境内后出现异常：【警告：检测到未知信仰体系冲突，侗神瞳进入不稳定状态】",
            "跨国直播延迟导致声浪值获取效率下降50%，美墨加时区下国内弹幕峰值与比赛时间错开。系统面板：【警告：检测到时差干扰，声浪值获取效率-50%，建议激活本地信仰节点】"
        )
        new = new.replace(
            "系统不稳定状态",
            "声浪值获取效率-50%"
        )
        if new != old:
            item["core_event"] = new
            fixed_count += 1
print(f"已修复 {fixed_count} 章的系统不稳定逻辑")

# 第200章：加神迹彩蛋
mod(200,
    core_event="下半场第10分钟，主角没有使用任何技能，用最普通的推射破门。进球后他没有跳舞，只是跪在草地上，额头抵着草皮——像萨玛节那晚额头抵着铜鼓。但全场十万观众的呐喊声汇聚成淡金色虚影，一座世界级的鼓楼笼罩球场。系统面板闪烁：【世界之眼，解锁中】。直播间没有666，只有同一句话刷了十万遍：陆远舟，你不是神，你是人。但你是我们最想成为的那种人",
    chapter_hook="进球后他没有跳舞，只是跪在草地上，额头抵着草皮。但全场十万观众的呐喊汇聚成淡金色虚影——一座世界级的鼓楼笼罩球场。系统面板：【世界之眼，解锁中】。直播间没有666，只有同一句话刷了十万遍：陆远舟，你不是神，你是人。但你是我们最想成为的那种人。",
    emotion_ratio="2:4:4",
    skill_unlocked="世界之眼（解锁中）")

# ═══════════════════════════════════════════════════════
# 重新组装 book_data.py
# ═══════════════════════════════════════════════════════

def format_entry(e):
    lines = ['    {']
    order = ["chapter", "title", "arc", "core_event", "face_slap_target",
             "face_slap_method", "husband_moment", "chapter_hook",
             "emotion_ratio", "skill_unlocked"]
    for k in order:
        if k in e:
            v = e[k]
            if isinstance(v, int):
                lines.append(f'        "{k}": {v},')
            else:
                lines.append(f'        "{k}": "{v}",')
    lines.append('    },')
    return "\n".join(lines)

# 按 arc 分组，添加注释
sections = []
current_arc = ""
for e in outline:
    if e["arc"] != current_arc:
        current_arc = e["arc"]
        sections.append(f'    # ── {current_arc} ──')
    sections.append(format_entry(e))

new_outline = "OUTLINE = [\n" + "\n".join(sections) + "\n]"

# 替换原文件中的 OUTLINE 部分
new_text = text[:outline_start] + new_outline + text[outline_end + 1:]
PY_PATH.write_text(new_text, encoding="utf-8")

# 验证
import py_compile
py_compile.compile(str(PY_PATH), doraise=True)
print("✅ book_data.py 语法验证通过")
print(f"✅ 共优化 {len(outline)} 章")
