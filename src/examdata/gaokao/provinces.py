"""省份 / 卷组归一表。

设计原则
========
1. 所有 HTTP 入口参数 ``province`` 接受简称 / 拼音码 / 虚拟卷组名，统一归一。
2. 虚拟卷组 (``全国1``/``全国2``/...) 走 ``group_key``，具体省份走 ``province``。
3. 年份维度不在本表——数据源自带当年度覆盖省份清单，本表只提供稳定映射。

来源：各省教育考试院 + 教育部历年公布（若某省出现两套卷由数据源文件名区分，
本表不参与）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# 31 省级行政区
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Province:
    code: str            # "SH" / "BJ" … 两位大写字母
    name: str            # "上海" / "北京"
    aliases: tuple[str, ...]


def _provs() -> tuple[Province, ...]:
    return (
        Province("BJ", "北京", ("北京", "京", "北京卷")),
        Province("TJ", "天津", ("天津", "津", "天津卷")),
        Province("SH", "上海", ("上海", "沪", "上海卷")),
        Province("CQ", "重庆", ("重庆", "渝", "重庆卷")),
        Province("HE", "河北", ("河北", "冀", "河北卷")),
        Province("SX", "山西", ("山西", "晋", "山西卷")),
        Province("NM", "内蒙古", ("内蒙古", "蒙", "内蒙", "内")),
        Province("LN", "辽宁", ("辽宁", "辽", "辽宁卷")),
        Province("JL", "吉林", ("吉林", "吉", "吉林卷")),
        Province("HL", "黑龙江", ("黑龙江", "黑")),
        Province("JS", "江苏", ("江苏", "苏", "江苏卷")),
        Province("ZJ", "浙江", ("浙江", "浙", "浙江卷")),
        Province("AH", "安徽", ("安徽", "皖", "安徽卷")),
        Province("FJ", "福建", ("福建", "闽", "福建卷")),
        Province("JX", "江西", ("江西", "赣", "江西卷")),
        Province("SD", "山东", ("山东", "鲁", "山东卷")),
        Province("HA", "河南", ("河南", "豫", "河南卷")),
        Province("HB", "湖北", ("湖北", "鄂", "湖北卷")),
        Province("HN", "湖南", ("湖南", "湘", "湖南卷")),
        Province("GD", "广东", ("广东", "粤", "广东卷")),
        Province("GX", "广西", ("广西", "桂", "广西卷")),
        Province("HI", "海南", ("海南", "琼", "海南卷")),
        Province("SC", "四川", ("四川", "川", "蜀", "四川卷")),
        Province("GZ", "贵州", ("贵州", "黔", "贵州卷")),
        Province("YN", "云南", ("云南", "滇", "云", "云南卷")),
        Province("XZ", "西藏", ("西藏", "藏", "西藏卷")),
        Province("SN", "陕西", ("陕西", "陕", "秦", "陕西卷")),
        Province("GS", "甘肃", ("甘肃", "甘", "陇", "甘肃卷")),
        Province("QH", "青海", ("青海", "青", "青海卷")),
        Province("NX", "宁夏", ("宁夏", "宁", "宁夏卷")),
        Province("XJ", "新疆", ("新疆", "新", "新疆卷")),
    )


PROVINCES = _provs()


# ---------------------------------------------------------------------------
# 索引：别名 / 简码 -> 简称
# ---------------------------------------------------------------------------

_ALIAS_TO_NAME: dict[str, str] = {}
_CODE_TO_NAME: dict[str, str] = {}
for _p in PROVINCES:
    for _a in _p.aliases:
        _ALIAS_TO_NAME.setdefault(_a, _p.name)
    _CODE_TO_NAME[_p.code.upper()] = _p.name


# ---------------------------------------------------------------------------
# 虚拟卷组
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PaperGroup:
    key: str
    aliases: tuple[str, ...]
    provinces: frozenset[str]


# 教育部历年公布（覆盖范围逐年可能微调，以当年度考院公告为准）
_NATIONAL_GROUPS: tuple[PaperGroup, ...] = (
    PaperGroup(
        "全国1",
        ("全国1", "全国I卷", "新高考1", "新课标I卷", "新课标Ⅰ", "新课标1",
         "新课标Ⅰ语文", "新课标Ⅰ英语", "新课标I卷语文", "全国I卷语文"),
        frozenset({"山东", "广东", "湖南", "湖北", "河北", "江苏", "福建",
                    "浙江", "河南", "江西", "安徽"}),
    ),
    PaperGroup(
        "全国2",
        ("全国2", "全国II卷", "新高考2", "新课标II卷", "新课标Ⅱ", "新课标2",
         "新课标Ⅱ语文", "新课标Ⅱ英语", "II卷"),
        frozenset({"辽宁", "重庆", "海南", "吉林", "黑龙江", "山西", "云南",
                    "广西", "甘肃", "贵州", "新疆", "四川", "内蒙古", "陕西",
                    "青海", "宁夏", "西藏"}),
    ),
    PaperGroup(
        "全国甲卷",
        ("全国甲卷", "全国甲", "甲卷", "甲卷理科", "甲卷文科"),
        frozenset({"四川", "广西", "贵州", "西藏", "云南", "内蒙古", "青海",
                    "宁夏"}),
    ),
    PaperGroup(
        "全国乙卷",
        ("全国乙卷", "全国乙", "乙卷"),
        frozenset({"山西", "河南", "陕西", "江西", "安徽"}),
    ),
    PaperGroup(
        "黑吉辽蒙",
        ("黑吉辽蒙", "黑吉辽", "东北四省", "东北"),
        frozenset({"黑龙江", "吉林", "辽宁", "内蒙古"}),
    ),
    PaperGroup(
        "陕晋青宁",
        ("陕晋青宁", "陕晋宁青", "陕晋青宁卷"),
        frozenset({"陕西", "山西", "青海", "宁夏"}),
    ),
)

_BY_ALIAS: dict[str, PaperGroup] = {}
for _g in _NATIONAL_GROUPS:
    for _a in _g.aliases:
        _BY_ALIAS[_a] = _g
        _BY_ALIAS[_a.upper()] = _g
    _BY_ALIAS.setdefault(_g.key, _g)


class ProvinceError(ValueError):
    """无法识别的省份或卷组名（调用方转 422）。"""


def normalize_province(value: str) -> tuple[Optional[str], Optional[str]]:
    """归一任意省份 / 卷组别名。

    返回 ``(province_name, group_key)``：
      - 具体省份：``("山东", None)``
      - 虚拟卷组：``(None, "全国1")``
      - 识别不了：``(None, None)``（调用方负责 422）
    """
    s = str(value or "").strip()
    if not s:
        return (None, None)

    # 1. 汉字别名（不区分大小写时先试裸匹配）
    if s in _ALIAS_TO_NAME:
        return (_ALIAS_TO_NAME[s], None)
    s_up = s.upper()
    if s_up in _ALIAS_TO_NAME:
        return (_ALIAS_TO_NAME[s_up], None)

    # 2. 拼音码（SH / BJ / …）
    if s_up in _CODE_TO_NAME:
        return (_CODE_TO_NAME[s_up], None)

    # 3. 虚拟卷组
    if s in _BY_ALIAS:
        g = _BY_ALIAS[s]
        return (None, g.key)
    if s_up in _BY_ALIAS:
        g = _BY_ALIAS[s_up]
        return (None, g.key)

    # 4. 去括号内的“省/市/自治区/特别行政区”后缀
    m = re.match(r"^(.*?)(?:省|市|特别行政区)$", s)
    if m:
        inner = m.group(1)
        if inner in _ALIAS_TO_NAME:
            return (_ALIAS_TO_NAME[inner], None)
        if inner in _CODE_TO_NAME:
            return (_CODE_TO_NAME[inner], None)

    return (None, None)


def group_members(group_key: str) -> frozenset[str]:
    g = _BY_ALIAS.get(group_key) or _BY_ALIAS.get(group_key.upper())
    return g.provinces if g else frozenset()


def group_aliases(group_key: str) -> tuple[str, ...]:
    g = _BY_ALIAS.get(group_key) or _BY_ALIAS.get(group_key.upper())
    return g.aliases if g else (group_key,)


def all_group_keys() -> list[str]:
    return [g.key for g in _NATIONAL_GROUPS]


def all_province_names() -> list[str]:
    return [p.name for p in PROVINCES]


# 文件名里可能出现的卷组简称序列（用于 deekur / qingshuo 解析）。
# 匹配顺序敏感：长别名在前。
_GROUP_LITERAL_ORDER: tuple[str, ...] = (
    "全国1",
    "全国I卷",
    "新课标I卷",
    "新课标Ⅰ",
    "新高考1",
    "全国2",
    "全国II卷",
    "新课标II卷",
    "新课标Ⅱ",
    "新高考2",
    "全国甲卷",
    "全国甲",
    "甲卷",
    "全国乙卷",
    "全国乙",
    "乙卷",
    "黑吉辽蒙",
    "黑吉辽",
    "陕晋青宁",
    "陕晋宁青",
)


def find_group_in_text(text: str) -> Optional[str]:
    """在一段文件名 / 标注里找虚拟卷组别名，命中返回 ``group_key``。"""
    if not text:
        return None
    for lit in _GROUP_LITERAL_ORDER:
        if lit in text:
            g = _BY_ALIAS.get(lit)
            if g is not None:
                return g.key
    return None


def find_province_in_text(text: str) -> Optional[str]:
    """在一段文件名 / 标注里找具体省份别名，命中返回简称。"""
    if not text:
        return None
    # 先试长别名（避免“黑吉辽蒙”被截成“蒙”之类）
    for p in sorted(PROVINCES, key=lambda pv: -len(max(pv.aliases, key=len)) if pv.aliases else 0):
        for a in sorted(p.aliases, key=len, reverse=True):
            if a and a in text:
                return p.name
    return None