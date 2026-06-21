#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
番茄短故事洞察信源自动评级与统计脚本
基于域名/来源类型对300条信源进行星级初评，并输出分布统计。
"""
import re
import json
from collections import Counter
from urllib.parse import urlparse

INPUT_FILE = "reports/fanqie_shortstory_insight_urls.txt"
OUTPUT_FILE = "reports/fanqie_shortstory_sources_rated.txt"
STATS_FILE = "reports/fanqie_shortstory_source_stats.json"

# 星级映射
STAR_LABELS = {
    5: "★★★★★",
    4: "★★★★☆",
    3: "★★★☆☆",
    2: "★★☆☆☆",
    1: "★☆☆☆☆",
}

# 域名到星级与类别的规则（域名包含匹配）
DOMAIN_RULES = [
    # 5星：官方、学术、顶级权威
    ("fanqienovel.com", 5, "番茄官方"),
    ("notice.fanqienovel.com", 5, "番茄官方"),
    ("mp.toutiao.com/docs/novel", 5, "番茄官方文档"),
    ("cssn.cn", 5, "中国社科院/学术"),
    ("literature.cass.cn", 5, "中国社科院"),
    ("chinawriter.com.cn", 5, "中国作家网/官方文艺"),
    ("news.cn", 5, "新华社"),
    ("chinadaily.com.cn", 5, "中国日报"),
    ("stdaily.com", 5, "科技日报"),
    ("cnr.cn", 5, "央广网"),
    ("pku.edu.cn", 5, "北京大学/学术"),
    ("questmobile.com.cn", 5, "QuestMobile权威数据"),
    ("runwise.co", 5, "研究报告"),
    # 4星：权威财经/科技媒体、研究机构转载
    ("sina.com.cn", 4, "新浪财经/新浪科技"),
    ("sina.cn", 4, "新浪"),
    ("qq.com", 4, "腾讯新闻"),
    ("163.com", 4, "网易"),
    ("sohu.com", 4, "搜狐"),
    ("ifeng.com", 4, "凤凰网"),
    ("jiemian.com", 4, "界面新闻"),
    ("huxiu.com", 4, "虎嗅"),
    ("36kr.com", 4, "36氪"),
    ("thepaper.cn", 4, "澎湃新闻"),
    ("bjd.com.cn", 4, "京报网"),
    ("jfdaily.com", 4, "上观新闻"),
    ("donews.com", 4, "DoNews"),
    ("21jingji.com", 4, "21经济网"),
    ("chinanews.com", 4, "中新网"),
    ("cnbeta.com", 4, "cnBeta"),
    ("csdn.net", 4, "CSDN"),
    ("cloud.tencent.com", 4, "腾讯云开发者社区"),
    ("toutiao.com", 4, "今日头条"),
    ("weibo.com", 4, "微博"),
    ("dzwww.com", 4, "大众网"),
    ("chinadaily.com.cn", 4, "中国日报"),
    ("cnpiw.cn", 4, "中国出版传媒商报"),
    ("xueqiu.com", 4, "雪球"),
    ("fortunechina.com", 4, "财富中文网"),
    # 3星：垂直媒体、行业自媒体、知识社区
    ("zhihu.com", 3, "知乎"),
    ("zhihu", 3, "知乎"),
    ("zhuanlan.zhihu.com", 3, "知乎专栏"),
    ("wangwen666.com", 3, "网文666"),
    ("maliangwriter.com", 3, "码良写作"),
    ("woshipm.com", 3, "人人都是产品经理"),
    ("smzdm.com", 3, "什么值得买"),
    ("post.smzdm.com", 3, "什么值得买"),
    ("appgrowing.net", 3, "AppGrowing"),
    ("kchuhai.com", 3, "快出海"),
    ("wezonet.com", 3, "WEZO维卓"),
    ("pinwall.cn", 3, "品物设计"),
    ("docs.feishu.cn", 3, "飞书文档/经验分享"),
    ("jianshu.com", 3, "简书"),
    ("9ku.com", 3, "九酷网"),
    ("biniku.com", 3, "教程之家"),
    ("jiaochengzhi", 3, "教程之家"),
    ("maigoo.com", 3, "买购网"),
    ("dangdang.com", 3, "当当"),
    ("17k.com", 3, "17K"),
    ("qidian.com", 3, "起点"),
    ("weihusm.com", 3, "2025常识网"),
    ("jianshu", 3, "简书"),
    # 2星：论坛、贴吧、社交平台经验分享
    ("tieba.baidu.com", 2, "百度贴吧"),
    ("tieba", 2, "百度贴吧"),
    ("ngabbs.com", 2, "NGA论坛"),
    ("douban.com", 2, "豆瓣"),
    ("bbs.kgm.cn", 2, "网文之家论坛"),
    ("guba.eastmoney.com", 2, "东方财富股吧"),
    ("bilibili.com", 2, "B站"),
    ("xiaoyuzhoufm.com", 2, "小宇宙FM"),
    # 1星：低质量/营销/电商/不可访问
    ("taobao.com", 1, "淘宝/电商"),
    ("world.taobao.com", 1, "淘宝台湾"),
    ("bk.taobao.com", 1, "淘宝百科"),
    ("otakada.org", 1, "电商/外文"),
    ("pdf", 1, "PDF/未明确来源"),
    ("search.", 1, "搜索页"),
    ("adsero.me", 1, "广告/竞赛"),
    ("wenchuan.oss", 1, "PDF/未明确来源"),
    ("huamaoshuo.com", 1, "PDF/未明确来源"),
    ("snac.fr", 1, "外文PDF"),
    ("library.qiangtu.com", 1, "PDF/未明确来源"),
    ("gordonkessler.com", 1, "外文PDF"),
    ("gaia-vivofs.vivo.com.cn", 1, "PDF/未明确来源"),
    ("ednet.ns.ca", 1, "外文PDF"),
]


def rate_source(domain: str, source_name: str, title: str) -> tuple:
    """根据域名、来源名、标题返回(星级, 类别)"""
    domain_lc = domain.lower()
    source_lc = source_name.lower()
    title_lc = title.lower()

    # 1. 先按域名规则匹配
    for pattern, star, cat in DOMAIN_RULES:
        if pattern in domain_lc:
            return star, cat

    # 2. 按来源名关键词匹配
    official_keywords = ["番茄官方", "番茄小说网", "番茄作家助手", "番茄小说小课堂"]
    for kw in official_keywords:
        if kw in source_lc:
            return 5, "番茄官方"

    media_keywords_4 = ["新闻", "财经", "日报", "周报", "周刊", "晨报", "晚报", "时报", "网", "报"]
    for kw in media_keywords_4:
        if kw in source_name and "公众号" not in source_lc and "微信" not in source_lc:
            return 4, "权威/综合媒体"

    # 3. 公众号/微信文章默认3星（如果无其他规则）
    if "mp.weixin.qq.com" in domain_lc or "公众号" in source_lc:
        return 3, "微信公众号"

    # 4. 默认3星（未知域名）
    return 3, "其他"


def parse_sources(path: str):
    sources = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("##"):
                continue
            # 格式: S001|URL|来源|标题|日期
            parts = line.split("|")
            if len(parts) < 4:
                continue
            sid = parts[0].strip()
            url = parts[1].strip()
            source_name = parts[2].strip() if len(parts) > 2 else ""
            title = parts[3].strip() if len(parts) > 3 else ""
            date = parts[4].strip() if len(parts) > 4 else ""
            parsed = urlparse(url)
            domain = parsed.netloc or url
            star, category = rate_source(domain, source_name, title)
            sources.append({
                "id": sid,
                "url": url,
                "domain": domain,
                "source_name": source_name,
                "title": title,
                "date": date,
                "star": star,
                "category": category,
            })
    return sources


def generate_outputs(sources):
    # 统计
    star_counts = Counter([s["star"] for s in sources])
    cat_counts = Counter([s["category"] for s in sources])
    domain_counts = Counter([s["domain"] for s in sources])

    # 输出评级文件
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("# 番茄短故事洞察信源评级汇总\n\n")
        f.write(f"总信源数：{len(sources)}\n\n")
        for s in sources:
            f.write(f"{s['id']}|{STAR_LABELS[s['star']]}|{s['category']}|{s['source_name']}|{s['title']}|{s['url']}|{s['date']}\n")

    # 输出统计JSON
    stats = {
        "total": len(sources),
        "star_distribution": {STAR_LABELS[k]: star_counts[k] for k in sorted(star_counts, reverse=True)},
        "category_distribution": dict(cat_counts.most_common()),
        "domain_distribution": dict(domain_counts.most_common(30)),
    }
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    # 打印摘要
    print(f"总信源数：{len(sources)}")
    print("星级分布：")
    for k in sorted(star_counts, reverse=True):
        print(f"  {STAR_LABELS[k]}: {star_counts[k]} ({star_counts[k]/len(sources)*100:.1f}%)")
    print("\n来源类别TOP15：")
    for cat, cnt in cat_counts.most_common(15):
        print(f"  {cat}: {cnt}")
    print("\n域名TOP15：")
    for dom, cnt in domain_counts.most_common(15):
        print(f"  {dom}: {cnt}")


if __name__ == "__main__":
    sources = parse_sources(INPUT_FILE)
    generate_outputs(sources)
    print(f"\n已输出：{OUTPUT_FILE}, {STATS_FILE}")
