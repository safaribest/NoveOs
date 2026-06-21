#!/usr/bin/env python3
"""修复剩余的系统不稳定逻辑和第200章结局。"""
from pathlib import Path

PY_PATH = Path("books/村超系统：我带侗寨球队踢爆世界杯/book_data.py")
text = PY_PATH.read_text(encoding="utf-8")

# 替换系统不稳定逻辑（覆盖所有可能出现的位置）
replacements = [
    # 旧 → 新
    ("系统在进入美国境内后出现异常：【警告：检测到未知信仰体系冲突，侗神瞳进入不稳定状态】",
     "跨国直播延迟导致声浪值获取效率下降50%，美墨加时区下国内弹幕峰值与比赛时间错开。系统面板：【警告：检测到时差干扰，声浪值获取效率-50%，建议激活本地信仰节点】"),
    ("系统异常：检测到未知信仰体系冲突，侗神瞳进入不稳定状态",
     "时差干扰：声浪值获取效率-50%，建议激活本地信仰节点"),
    ("检测到未知信仰体系冲突，侗神瞳进入不稳定状态",
     "检测到时差干扰，声浪值获取效率-50%"),
    ("未知信仰体系冲突",
     "时差干扰导致声浪值效率下降"),
    ("侗神瞳进入不稳定状态",
     "声浪值获取效率-50%"),
]

count = 0
for old, new in replacements:
    if old in text:
        text = text.replace(old, new)
        count += 1

print(f"Replaced {count} occurrences of system instability logic")

# 修复第200章结局（如果还没改的话）
old_ending = "下半场第10分钟，主角没有使用任何技能，用最普通的推射破门。进球后他没有跳舞，只是跪在草地上，额头抵着草皮——像萨玛节那晚额头抵着铜鼓。直播间弹幕没有666，没有卧槽，只有同一句话刷了十万遍：陆远舟，你不是神，你是人。但你是我们最想成为的那种人"
new_ending = "下半场第10分钟，主角没有使用任何技能，用最普通的推射破门。进球后他没有跳舞，只是跪在草地上，额头抵着草皮——像萨玛节那晚额头抵着铜鼓。但全场十万观众的呐喊声汇聚成淡金色虚影，一座世界级的鼓楼笼罩球场。系统面板闪烁：【世界之眼，解锁中】。直播间没有666，只有同一句话刷了十万遍：陆远舟，你不是神，你是人。但你是我们最想成为的那种人"

if old_ending in text:
    text = text.replace(old_ending, new_ending)
    print("Fixed chapter 200 ending")
else:
    # 检查是否已经修改过
    if "世界级的鼓楼笼罩球场" in text:
        print("Chapter 200 ending already fixed")
    else:
        print("Chapter 200 ending pattern not matched, may need manual check")

PY_PATH.write_text(text, encoding="utf-8")

# Verify
import py_compile
py_compile.compile(str(PY_PATH), doraise=True)
print("Syntax OK")
