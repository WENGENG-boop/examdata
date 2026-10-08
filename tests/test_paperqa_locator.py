"""locator 的算法分支测试：全部用内存合成 PDF，不依赖真实试卷。

真实试卷只在最后一条回归测试里用，且文件不存在时跳过。
"""
import re
import unicodedata
from pathlib import Path

import pymupdf
import pytest

from examdata.paperqa import locator
from examdata.paperqa.errors import LocationError
from examdata.paperqa.locator import Crop, crop_question, locate

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


def bitmap(rgb=(200, 0, 0)):
    return pymupdf.Pixmap(pymupdf.csRGB, 8, 8, bytes(rgb) * 64, False)


@pytest.mark.parametrize('rotation', [0, 90, 180, 270])
@pytest.mark.parametrize('role', ['qp', 'ms'])
def test_rotated_question_has_consistent_bounds_and_nonwhite_png(rotation, role):
    with pymupdf.open() as pdf:
        pdf.new_page()
        page = furniture(write(pdf.new_page(), [
            (43, 600, '1'), (80, 620, 'Explain the rotated diagram'),
            (43, 740, '(Total for Question 1 = 1 mark)'),
        ]))
        page.insert_image(pymupdf.Rect(80, 650, 380, 700), pixmap=bitmap(), keep_proportion=False)
        write(pdf.new_page(), [(43, 100, '2'), (80, 120, 'Next question')])
        expected = tuple(locate(pdf, '1', role)[0][1])
        page = pdf[1]
        page.set_rotation(rotation)
        clips = locate(pdf, '1', role)
        assert [index for index, _ in clips] == [1]
        assert tuple(clips[0][1]) == pytest.approx(expected)
        assert 'Explain the rotated diagram' in clip_text(pdf, clips)
        assert 'Next question' not in clip_text(pdf, clips)
        assert not NOISE.search(clip_text(pdf, clips))
        data = pdf.tobytes()
    crop = crop_question(data, '1', role)[0]
    assert crop.page == 2
    assert crop.bbox == pytest.approx(expected)
    pix = pymupdf.Pixmap(crop.png)
    assert min(pix.samples) < 255
    assert len(set(pix.samples)) > 1
    render_rect = pymupdf.Rect(crop.bbox)
    if rotation in (90, 270):
        render_rect = pymupdf.Rect(0, 0, render_rect.height, render_rect.width)
    assert abs(pix.width - render_rect.width * 1.5) <= 2
    assert abs(pix.height - render_rect.height * 1.5) <= 2


@pytest.mark.parametrize('rotation', [0, 90, 180, 270])
def test_raster_images_count_actual_placements_without_next_question_or_footer(rotation):
    with pymupdf.open() as pdf:
        pdf.new_page()
        page = write(pdf.new_page(), [
            (43, 100, '1'), (80, 120, 'Use the raster diagram'),
            (43, 450, '2'), (80, 470, 'Next question'),
        ])
        xref = page.insert_image(pymupdf.Rect(60, 200, 300, 300),
                                 pixmap=bitmap(), keep_proportion=False)
        page.insert_image(pymupdf.Rect(380, 320, 500, 400), xref=xref, keep_proportion=False)
        page.insert_image(pymupdf.Rect(60, 500, 560, 700), xref=xref, keep_proportion=False)
        page.insert_image(pymupdf.Rect(40, 805, 560, 825), xref=xref, keep_proportion=False)
        page.set_rotation(rotation)
        clips = locate(pdf, '1', 'qp')
        rect = clips[0][1]
        assert rect.x1 == pytest.approx(505)
        assert rect.y1 == pytest.approx(405)
        assert 'Next question' not in clip_text(pdf, clips)
        data = pdf.tobytes()
    crop = crop_question(data, '1', 'qp')[0]
    pix = pymupdf.Pixmap(crop.png)
    pixels = zip(*(iter(pix.samples),) * pix.n)
    assert any(pixel[:3] == (200, 0, 0) for pixel in pixels)


def test_image_only_continuation_is_not_cropped_away():
    with pymupdf.open() as pdf:
        pdf.new_page()
        write(pdf.new_page(), [(43, 100, '1'), (80, 120, 'Use the diagram on the next page')])
        page = pdf.new_page()
        page.insert_image(pymupdf.Rect(50, 200, 550, 500), pixmap=bitmap(), keep_proportion=False)
        write(pdf.new_page(), [(43, 100, '2')])
        clips = locate(pdf, '1', 'qp')
        assert [index for index, _ in clips] == [1, 2]
        assert tuple(clips[1][1]) == pytest.approx((45, 195, 555, 505))


def test_full_page_raster_is_clipped_to_question_window_not_discarded_as_frame():
    with pymupdf.open() as pdf:
        pdf.new_page()
        page = pdf.new_page()
        page.insert_image(page.rect, pixmap=bitmap(), keep_proportion=False)
        write(page, [(43, 100, '1'), (80, 120, 'Question text'),
                     (43, 300, '2'), (80, 320, 'Next question')])
        clips = locate(pdf, '1', 'qp')
        rect = clips[0][1]
        assert rect.x0 == 0 and rect.x1 == page.rect.width
        assert 270 < rect.y1 < 295
        assert 'Question text' in clip_text(pdf, clips)
        assert 'Next question' not in clip_text(pdf, clips)


@pytest.mark.parametrize('rotation', [0, 90, 180, 270])
def test_rotated_cropbox_origin_is_not_used_as_text_origin(rotation):
    with pymupdf.open() as pdf:
        pdf.new_page()
        page = write(pdf.new_page(width=650, height=920), [
            (83, 150, '1'), (120, 170, 'Cropped page content'),
            (83, 350, '2'),
        ])
        page.set_cropbox(pymupdf.Rect(40, 50, 635, 892))
        page.set_rotation(rotation)
        clips = locate(pdf, '1', 'qp')
        assert 'Cropped page content' in clip_text(pdf, clips)
        data = pdf.tobytes()
    crop = crop_question(data, '1', 'qp')[0]
    assert crop.bbox[0] == pytest.approx(38)
    assert crop.bbox[1] == pytest.approx(83.175, abs=0.001)
    assert min(pymupdf.Pixmap(crop.png).samples) < 255


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


def test_numeric_table_column_is_not_question_numbering():
    """统计表左栏的连续整数（卡方临界值表的 df 列）不能被当题号。

    表行内其余列全是小数，题号行后面跟的是题目文字——用"行内是否几乎
    全数值"区分。旧实现把 df 列的 1..30 当题号后，真正题号 1、2 被
    单调序列挡掉，最后一题一路拖到卷尾，整卷报 "spans too many pages"。
    """
    with pymupdf.open() as pdf:
        pdf.new_page()
        table = pdf.new_page()
        for i in range(30):
            y = 60 + i * 14.5
            table.insert_text((62, y), str(i + 1))
            table.insert_text((100, y), '1.64')
            table.insert_text((140, y), '2.71')
        write(pdf.new_page(), [(43, 100, '1'), (80, 120, 'Real question one'),
                               (43, 300, '(Total for Question 1 = 1 mark)')])
        write(pdf.new_page(), [(43, 100, '2'), (80, 120, 'Real question two')])
        clips = locate(pdf, '1', 'qp')
        assert [page for page, _ in clips] == [2]
        assert 'Real question one' in clip_text(pdf, clips)


def test_dotted_question_number_with_numeric_first_line_is_kept():
    """带尾点题号（数学卷 `4.`）与题目首行数据列表同行时不能被当统计表行。

    真实版式（ial-maths doc 3200 p4）：`4.` 与题目数据 23 18 27 ... 同排，
    整行 9/10 是数字。旧判据丢弃该题号后，子题锚点挂到上一题，整卷索引
    报 "Question 3(e) could not be located reliably"。
    """
    with pymupdf.open() as pdf:
        pdf.new_page()
        write(pdf.new_page(), [(43, 100, '1'), (80, 120, 'Question one text'),
                               (43, 300, '(Total for Question 1 = 1 mark)')])
        write(pdf.new_page(), [(43, 100, '2'), (80, 120, 'Question two text')])
        write(pdf.new_page(), [(43, 100, '3'), (80, 120, 'Question three text')])
        write(pdf.new_page(), [(43, 100, '4.')] +
              [(100 + 40 * i, 100, t) for i, t in enumerate(['23', '18', '27', '9', '25', '10'])])
        write(pdf.new_page(), [(43, 100, '5'), (80, 120, 'Question five text')])
        clips = locate(pdf, '4', 'qp')
        assert [page for page, _ in clips] == [4]
        assert '23' in clip_text(pdf, clips)


def test_empty_span_reports_dedicated_error():
    """空区间单独报 'Question span is empty'，不再和 >25 页上限共用一条文案。

    构造的是"题号贴着页顶"的极端版式：页高 18pt，题号 y0≈2，区间上界
    被 _PAD 夹到 0；下一题锚点在 y0≈8，把下界收到 3，整个区间不足 4pt。
    字号压到 6pt 是为了让两个题号在 6pt 间距下仍是独立词——贴太近
    PyMuPDF 会把它们并成 `12`。
    """
    with pymupdf.open() as pdf:
        pdf.new_page()
        page = pdf.new_page(width=595, height=18)
        page.insert_text((43, 8.45), '1', fontsize=6)
        page.insert_text((43, 14.45), '2', fontsize=6)
        with pytest.raises(LocationError) as excinfo:
            locate(pdf, '1', 'qp')
    assert str(excinfo.value) == 'Question span is empty'


def test_crop_rejects_span_over_page_limit(monkeypatch):
    """crop_question 的页数上限：locate 给出 26 个 clip 时直接报错，不渲染 PNG。

    上限不在 locate 上（它的结果之后还要追加 booklet 上下文页），所以这里
    monkeypatch 掉 locate，免得为凑 26 页真的铺版式。
    """
    with pymupdf.open() as pdf:
        write(pdf.new_page(), [(43, 100, '1'), (80, 120, 'Short question')])
        data = pdf.tobytes()
    clips = [(0, pymupdf.Rect(40, 95, 300, 140))] * 26
    monkeypatch.setattr(locator, 'locate', lambda *args, **kwargs: clips)
    with pytest.raises(LocationError, match='implausibly large'):
        crop_question(data, '1', 'qp')


def test_crop_accepts_span_at_page_limit(monkeypatch):
    """25 页（上限内）照常返回 Crop 列表，元素数与 clip 数一致。"""
    with pymupdf.open() as pdf:
        write(pdf.new_page(), [(43, 100, '1'), (80, 120, 'Short question')])
        data = pdf.tobytes()
    clips = [(0, pymupdf.Rect(40, 95, 300, 140))] * 25
    monkeypatch.setattr(locator, 'locate', lambda *args, **kwargs: clips)
    crops = crop_question(data, '1', 'qp')
    assert len(crops) == len(clips) == 25
    assert all(isinstance(crop, Crop) for crop in crops)
    assert {crop.page for crop in crops} == {1}
    assert all(crop.png.startswith(b'\x89PNG') for crop in crops)


def test_page_limit_counts_booklet_context_pages(monkeypatch):
    """上限在 booklet 上下文页追加之后才算：locate 只给 25 页，追加的
    Figure 页让它变成 26 页，同样要报错——只限制 locate 挡不住最终列表膨胀。"""
    with pymupdf.open() as pdf:
        write(pdf.new_page(), [(43, 100, '1'), (80, 120, 'Use Figure 1')])
        cover = write(pdf.new_page(), [(80, 400, 'Source Booklet')])
        cover.insert_text((80, 420), 'Do not return this Booklet')
        write(pdf.new_page(), [(80, 200, 'Figure 1')])
        data = pdf.tobytes()
    clips = [(0, pymupdf.Rect(40, 95, 300, 140))] * 25
    monkeypatch.setattr(locator, 'locate', lambda *args, **kwargs: clips)
    with pytest.raises(LocationError, match='implausibly large'):
        crop_question(data, '1', 'qp')


def test_booklet_acknowledgements_before_questions_does_not_stop_scan():
    """合订本：Source Booklet 的 Acknowledgements 排在题目之前，不能截断扫描。

    Business 2022（WBS11–14）把 Source Booklet 装订在题目之前，
    Acknowledgements 落在题目区之前；旧实现见到它就停止扫描，整卷
    认不出任何题号，只能报 LocationError。
    """
    with pymupdf.open() as pdf:
        pdf.new_page()  # 封面
        write(pdf.new_page(), [(80, 100, 'Extract A'), (80, 300, 'Acknowledgements')])
        write(pdf.new_page(), [(43, 100, '1'), (80, 120, 'Question one'),
                               (43, 300, '(Total for Question 1 = 1 mark)')])
        write(pdf.new_page(), [(43, 100, '2'), (80, 120, 'Question two')])
        clips = locate(pdf, '1', 'qp')
        assert [page for page, _ in clips] == [2]
        text = clip_text(pdf, clips)
        assert 'Question one' in text and 'Total for Question 1' in text


def test_acknowledgements_after_questions_still_stops_scan():
    """题目区之后的 Acknowledgements 仍是扫描终点：其后的题号不再入册。"""
    with pymupdf.open() as pdf:
        pdf.new_page()
        write(pdf.new_page(), [(43, 100, '1'), (80, 120, 'Question one')])
        write(pdf.new_page(), [(43, 100, '2'), (80, 120, 'Question two')])
        write(pdf.new_page(), [(80, 300, 'Acknowledgements')])
        write(pdf.new_page(), [(43, 100, '3'), (80, 120, 'After acknowledgements')])
        assert [page for page, _ in locate(pdf, '2', 'qp')] == [2, 3]
        with pytest.raises(LocationError, match='could not be located'):
            locate(pdf, '3', 'qp')


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


def test_double_dot_question_number_with_numeric_first_line_is_kept():
    """双点题号（`1..`）与题目首行数据列表同行时同样是题号。

    真实版式（ial18-mathematics doc 1336 wma02-01 首题）：`1..` 与数据
    23 18 27 ... 同排；旧正则只认单尾点，整卷认不出首题。
    """
    with pymupdf.open() as pdf:
        pdf.new_page()
        write(pdf.new_page(), [(43, 100, '1..')] +
              [(100 + 40 * i, 100, t) for i, t in enumerate(['23', '18', '27', '9', '25', '10'])])
        write(pdf.new_page(), [(43, 100, '2'), (80, 120, 'Second question')])
        clips = locate(pdf, '1', 'qp')
        assert [page for page, _ in clips] == [1]
        assert '23' in clip_text(pdf, clips)


def test_decode_cipher_text_restores_shifted_characters():
    """密码字体卷：GID = 真实字符 − 0x1D；空白码与范围外字符原样保留。"""
    assert locator.decode_cipher_text('\x14\x11') == '1.'
    assert locator.decode_cipher_text('\x0bD\x0c') == '(a)'
    assert locator.decode_cipher_text('\x03') == ' '
    assert locator.decode_cipher_text('x y\nz\tw') == 'x y\nz\tw'
    assert locator.decode_cipher_text('\x02') == '\x02'


def test_is_ciphered_detects_control_char_density():
    """前 3 页非空白控制字符 ≥ 200 → 密文卷；普通文本不误报。"""
    with pymupdf.open() as pdf:
        cover = pdf.new_page()
        for i in range(3):
            cover.insert_text((40, 100 + i * 20), '\x14' * 70)
        assert locator.is_ciphered(pdf)
    with pymupdf.open() as pdf:
        write(pdf.new_page(), [(43, 100, 'Normal question text')])
        assert not locator.is_ciphered(pdf)


def test_greek_question_number_after_question_word():
    """希腊语卷：题号是紧跟 "Ερώτηση" 的数字；NFC/NFD 两种形式都要认。"""
    bounds = pymupdf.Rect(0, 0, 595, 842)
    previous = (42.4, 100.0, 90.0, 110.0, 'Ερώτηση', 0, 0, 0)
    word = (93.5, 100.0, 100.0, 110.0, '13', 0, 0, 0)
    assert locator._greek_number_after_question_word(previous, word, bounds)
    nfd = unicodedata.normalize('NFD', 'Ερώτηση')
    assert locator._greek_number_after_question_word((42.4, 100.0, 90.0, 110.0, nfd, 0, 0, 0), word, bounds)
    # 反例：没有前词 / 间隙过大 / 不同排 / 位于右半页 / 前词不是 "Ερώτηση"
    assert not locator._greek_number_after_question_word(None, word, bounds)
    assert not locator._greek_number_after_question_word((42.4, 100.0, 60.0, 110.0, 'Ερώτηση', 0, 0, 0), word, bounds)
    assert not locator._greek_number_after_question_word((42.4, 120.0, 90.0, 130.0, 'Ερώτηση', 0, 0, 0), word, bounds)
    assert not locator._greek_number_after_question_word(previous, (200.0, 100.0, 207.0, 110.0, '13', 0, 0, 0), bounds)
    assert not locator._greek_number_after_question_word((42.4, 100.0, 90.0, 110.0, 'Ερωτηση', 0, 0, 0), word, bounds)


def test_ciphered_pdf_is_detected_decoded_and_locatable():
    """密码字体卷端到端：检测 → 解码词表 → 题号锚点 → 裁剪文本可读。"""
    def cipher(text):
        return ''.join(chr(ord(c) - 0x1D) if 0x20 <= ord(c) <= 0x61 and c not in "&'()*" else c
                       for c in text)

    with pymupdf.open() as pdf:
        cover = pdf.new_page()
        for i in range(3):
            cover.insert_text((40, 100 + i * 20), '\x14' * 70)
        page = pdf.new_page()
        page.insert_text((43, 100), cipher('1'))
        page.insert_text((80, 120), cipher('Explain the concept'))
        page.insert_text((43, 300), cipher('2'))
        page.insert_text((80, 320), cipher('Second question'))
        assert locator.is_ciphered(pdf)
        clips = locate(pdf, '1', 'qp')
        assert [p for p, _ in clips] == [1]
        text = ' '.join(locator._decode_if(pdf[p].get_text(clip=r), True) for p, r in clips)
        assert 'Explain the concept' in text
        assert 'Second question' not in text
        data = pdf.tobytes()
    crops = crop_question(data, '1', 'qp')
    assert crops[0].page == 2
    assert min(pymupdf.Pixmap(crops[0].png).samples) < 255


def test_same_line_nested_subpart_anchor_is_not_a_stop():
    """同行嵌套子题号（`10. (i) (a) ...`）产出的同排锚点不能当终点。

    真实版式（ial18-mathematics doc 471 等 13 张）：题号行同排产出 `10(i)`
    与 `10(a)` 两个锚点；旧实现取同排的 `10(a)` 当 `10(i)` 的终点，停止位
    落在起点上方，整卷报 "Invalid question boundaries"。合成版用小号题号
    复现（检测器只接纳顺序递增的题号）。
    """
    with pymupdf.open() as pdf:
        pdf.new_page()
        write(pdf.new_page(), [(43, 100, '1'), (80, 120, 'Question one'),
                               (43, 300, '(Total for Question 1 = 1 mark)')])
        write(pdf.new_page(), [(43, 100, '2. (i) (a) Find, in ascending powers')])
        write(pdf.new_page(), [(43, 100, '3'), (80, 120, 'Question three')])
        assert {'2(i)', '2(a)'} <= {a.path for a in locator._anchors(pdf, 'qp')[0]}
        clips = locate(pdf, '2(i)', 'qp')
        assert [page for page, _ in clips] == [2]
        assert 'ascending powers' in clip_text(pdf, clips)


def test_summary_filter_falls_back_to_flagged_page_match():
    """摘要页过滤后没有该题时退回全量锚点，而不是报 "could not be located"。

    真实案例（ial-greek doc 2441 等 10 张）：内联 "(g)/(h)" 标记让真实题目
    所在页被摘要页启发式误判；过滤掉该页后该题锚点被清空，整卷失败。
    """
    with pymupdf.open() as pdf:
        pdf.new_page()
        write(pdf.new_page(), [(43, 100, '1'), (80, 120, '(a)'), (80, 130, '(b)'), (80, 140, '(c)'),
                               (80, 200, 'overview marker')])
        write(pdf.new_page(), [(43, 100, '1'), (80, 150, '(a)'), (80, 160, '(b)')])
        clips = locate(pdf, '1(c)', 'qp')
        assert [page for page, _ in clips] == [1]
        assert 'overview marker' in clip_text(pdf, clips)


def test_section_banner_restarts_question_numbering():
    """分节横幅后的题号从 1 重新开始时，清掉横幅前的假前缀（来源文章内部编号）。

    真实案例（ial-englang doc 1911 wen03-01）：来源文章的编号列表 `1.`-`5.`
    被当成题号，main 被推到 5；SECTION A 后的真实题 `1` 被单调性规则拒绝，
    Q5 一路拖到 28 页触发 "spans too many pages"。修复后 `1` 触发编号重启。
    """
    with pymupdf.open() as pdf:
        pdf.new_page()
        write(pdf.new_page(), [(43, 160, '1. Tell your home what to do'),
                               (43, 240, '2. Excuse me, my house is calling'),
                               (43, 334, '3. Customize your home')])
        write(furniture(pdf.new_page(), banner=True),
              [(43, 134, '1'), (80, 150, 'Using the material in the source texts')])
        write(furniture(pdf.new_page(), banner=True),
              [(43, 110, '2'), (80, 126, 'Write a commentary on your new text')])
        anchors, _ = locator._anchors(pdf, 'qp')
        assert [(a.path, a.page) for a in anchors] == [('1', 2), ('2', 3)]
        clips = locate(pdf, '1', 'qp')
        assert [page for page, _ in clips] == [2]
        assert 'Using the material' in clip_text(pdf, clips)
