"""locator 的算法分支测试：全部用内存合成 PDF，不依赖真实试卷。

真实试卷只在最后一条回归测试里用，且文件不存在时跳过。
"""
import re
from pathlib import Path

import pymupdf
import pytest

from examdata.paperqa.locator import locate

# 真正的版式噪声：页边竖排水印 / 试卷代码 / 条码 / 版权行 / "Turn over"。
# 注意不要用 `\bSECTION\b`：正文里的 `TOTAL FOR SECTION B = 20 MARKS` 是
# 合法的分节合计行，按文字匹配会把它误判成噪声。页顶 `SECTION A/B/C`
# 横幅的排除由 `test_continuation_page_starts_at_first_content` 按位置验证。
NOISE = re.compile(r'DO NOT WRITE|\bP\d{5}[A-Z]\b|turn over|\*P[A-Z0-9]{4,}\*|©', re.I)

PROBE = Path(__file__).resolve().parents[1] / 'tmpwork' / 'probe'


def write(page, rows):
    for x, y, text in rows:
        page.insert_text((x, y), text)
    return page


def furniture(page, banner=False):
    """铺满一页真实的版式噪声：左边竖排水印、页脚条码/页码/Turn over、页顶横幅。"""
    page.insert_text((9.6, 500), 'DO NOT WRITE IN THIS AREA', rotate=90)
    page.insert_text((43, 806), '*P75888A0328*')
    page.insert_text((49, 798), '2')
    page.insert_text((200, 816), 'Turn over')
    if banner:
        # 间距要和真实试卷一致：贴太近 PyMuPDF 会把两个 token 并成一个词
        page.insert_text((269, 59.5), 'SECTION')
        page.insert_text((320, 59.5), 'A')
    return page


def clip_text(pdf, clips):
    return ' '.join(pdf[page].get_text(clip=rect) for page, rect in clips)


def test_question_ends_at_total_line():
    """整题收在 `(Total for Question N = X marks)` 上，而不是下一个题号。"""
    with pymupdf.open() as pdf:
        pdf.new_page()
        furniture(write(pdf.new_page(), [(43, 100, '1'), (80, 120, 'Explain the concept'),
                                         (43, 300, '(Total for Question 1 = 1 mark)')]))
        write(pdf.new_page(), [(43, 100, '2'), (80, 120, 'Next question')])
        clips = locate(pdf, '1', 'qp')
        assert [page for page, _ in clips] == [1]
        assert 300 <= clips[0][1].y1 < 320
        text = clip_text(pdf, clips)
        assert 'Total for Question 1' in text
        assert 'Next question' not in text
        assert not NOISE.search(text)


def test_crop_is_tightened_to_content():
    """窗口给到页底，但空白与页脚都被裁掉，只剩内容包围盒。"""
    with pymupdf.open() as pdf:
        pdf.new_page()
        furniture(write(pdf.new_page(), [(43, 100, '1'), (80, 120, 'Short question')]))
        write(pdf.new_page(), [(43, 100, '2')])
        rect = locate(pdf, '1', 'qp')[0][1]
        assert rect.y1 < 200
        assert rect.x1 < 300
        assert rect.x0 >= 0 and rect.y0 >= 0


def test_continuation_page_starts_at_first_content():
    """续页从该页第一行内容起步：页顶横幅、页脚条码/页码、页边水印都不算内容。"""
    with pymupdf.open() as pdf:
        pdf.new_page()
        write(pdf.new_page(), [(43, 100, '1'), (80, 120, 'Question one'), (80, 700, 'answer space')])
        furniture(write(pdf.new_page(), [(80, 200, 'continued')]), banner=True)
        write(pdf.new_page(), [(43, 100, '2')])
        clips = locate(pdf, '1', 'qp')
        assert [page for page, _ in clips] == [1, 2]
        assert clips[1][1].y0 > 150
        text = clip_text(pdf, clips)
        assert 'continued' in text
        assert not NOISE.search(text)


def test_subquestion_boundaries():
    """子题收在下一个同级锚点；最后一个子题收在父题总分行。"""
    with pymupdf.open() as pdf:
        pdf.new_page()
        write(pdf.new_page(), [
            (43, 100, '1'), (80, 120, 'intro'),
            (60, 200, '(a)'), (80, 220, 'text a'),
            (60, 400, '(b)'), (80, 420, 'text b'),
            (60, 600, '(c)'), (80, 620, 'text c'),
            (43, 750, '(Total for Question 1 = 3 marks)'),
        ])
        write(pdf.new_page(), [(43, 100, '2')])

        first = clip_text(pdf, locate(pdf, '1(a)', 'qp'))
        assert 'text a' in first and 'text b' not in first

        last = clip_text(pdf, locate(pdf, '1(c)', 'qp'))
        assert 'text c' in last
        assert 'Total for Question 1' in last


def test_figure_drawings_count_as_content():
    """图只有 drawing 没有文字，必须计入包围盒，否则带图题会把图裁掉。"""
    with pymupdf.open() as pdf:
        pdf.new_page()
        page = write(pdf.new_page(), [(43, 100, '1'), (80, 120, 'Use the diagram')])
        page.draw_rect(pymupdf.Rect(60, 200, 500, 600))
        write(pdf.new_page(), [(43, 100, '2')])
        clips = locate(pdf, '1', 'qp')
        rect = clips[0][1]
        assert rect.x1 > 495 and rect.y1 > 595
        assert not NOISE.search(clip_text(pdf, clips))


def test_full_page_frame_is_not_content():
    """整页外框（宽高都超过页面的 85%）是版式装饰，不是内容。"""
    with pymupdf.open() as pdf:
        pdf.new_page()
        page = write(pdf.new_page(), [(43, 100, '1'), (80, 120, 'Short question')])
        page.draw_rect(pymupdf.Rect(35, 36.4, 560.3, 794.1))
        write(pdf.new_page(), [(43, 100, '2')])
        rect = locate(pdf, '1', 'qp')[0][1]
        assert rect.y1 < 200


def test_section_word_in_body_is_kept():
    """正文里的 `TOTAL FOR SECTION B = 6 MARKS` 位置在页中，不能当页顶横幅丢掉。"""
    with pymupdf.open() as pdf:
        pdf.new_page()
        write(pdf.new_page(), [(43, 100, '1'), (80, 120, 'Question text'),
                               (43, 585, 'TOTAL FOR SECTION B = 6 MARKS')])
        write(pdf.new_page(), [(43, 100, '2')])
        text = clip_text(pdf, locate(pdf, '1', 'qp'))
        assert 'TOTAL FOR SECTION B' in text


def test_banner_needs_section_letter_to_its_right():
    """页顶 `Answer ALL questions in this section...` 右侧没有单字母，是正文不是横幅。"""
    with pymupdf.open() as pdf:
        pdf.new_page()
        write(pdf.new_page(), [(43, 100, '1'), (80, 700, 'Question one')])
        write(pdf.new_page(), [(43, 83.5, 'Answer ALL questions in this section in the spaces provided.'),
                               (80, 200, 'continued')])
        write(pdf.new_page(), [(43, 100, '2')])
        text = clip_text(pdf, locate(pdf, '1', 'qp'))
        assert 'in this section' in text
        assert 'continued' in text


@pytest.mark.skipif(not (PROBE / 'wec11.pdf').exists(), reason='真实试卷样本不在仓库里')
def test_real_exam_pdf_crops_are_tight():
    """真实 Edexcel 试卷回归：收紧后仍然不丢内容、不混版式噪声。"""
    with pymupdf.open(PROBE / 'wec11.pdf') as qp:
        clips = locate(qp, '4', 'qp')
        assert [page for page, _ in clips] == [2]
        assert clips[0][1].y1 < 600
        text = clip_text(qp, clips)
        assert 'Total for Question 4' in text
        # 图（drawing）在 y≈93..365，必须仍被包含
        assert clips[0][1].y0 < 100

        for question in ['1', '4', '9', '11', '12', '12(b)', '13', '14']:
            page_text = clip_text(qp, locate(qp, question, 'qp'))
            assert not NOISE.search(page_text), question
            # 裁剪框必须留在页眉带以下、页脚带以上
            for page, rect in locate(qp, question, 'qp'):
                assert rect.y0 > qp[page].rect.height * 0.045
                assert rect.y1 < qp[page].rect.height * 0.95

        # 旧实现会把 Q11 拖到分节合计行 `TOTAL FOR SECTION B = 20 MARKS` 上
        assert 'TOTAL FOR SECTION' not in clip_text(qp, locate(qp, '11', 'qp'))
        # Q14 是最后一题，后面没有题号锚点，旧实现一路拖到第 25 页的
        # 分节合计行 `TOTAL FOR SECTION D = 20 MARKS`
        assert [page for page, _ in locate(qp, '14', 'qp')] == [19]
        assert 'TOTAL FOR SECTION' not in clip_text(qp, locate(qp, '14', 'qp'))

    with pymupdf.open(PROBE / 'wec11_rms.pdf') as ms:
        clips = locate(ms, '12(a)', 'ms')
        assert [page for page, _ in clips] == [10]
        assert clips[0][1].height < 250
        assert 'Answer' in clip_text(ms, clips)
