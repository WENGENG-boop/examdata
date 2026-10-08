"""一次性检查：未修复的删除路径（只删 question）在 FK 开启时确实报错。"""
from sqlalchemy import create_engine, delete, event
from sqlalchemy.orm import sessionmaker

from examdata.core.models import (
    Base,
    Board,
    Document,
    ExamSeries,
    Paper,
    Question,
    QuestionTaxonomy,
    Qualification,
    Subject,
    TaxonomyNode,
)

engine = create_engine("sqlite://", future=True)


@event.listens_for(engine, "connect")
def _fk_on(dbapi_conn, _record):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


Base.metadata.create_all(engine)
s = sessionmaker(bind=engine, expire_on_commit=False, future=True)()

board = Board(key="edexcel", name="Pearson Edexcel")
s.add(board)
s.flush()
qual = Qualification(board_id=board.id, key="edexcel-ial", name="IAL")
s.add(qual)
s.flush()
subject = Subject(qualification_id=qual.id, code="ial18-test", title="Biology")
s.add(subject)
s.flush()
series = ExamSeries(year=2021, session="june 2021", month=6, attrs={})
s.add(series)
s.flush()
doc = Document(
    identity_key="qp-fk-check",
    board_id=board.id,
    subject_id=subject.id,
    series_id=series.id,
    doc_type="question_paper",
    paper_code="wbi11-01",
    attrs={},
)
s.add(doc)
s.flush()
paper = Paper(document_id=doc.id, attrs={})
s.add(paper)
s.flush()
q = Question(
    paper_id=paper.id,
    number_label="1",
    number_path="1",
    display_order=0,
    depth=0,
    kind="question",
    attrs={},
)
s.add(q)
s.flush()
node = TaxonomyNode(
    board_id=board.id, code="1.2", name="Cells", node_type="topic", source="official", attrs={}
)
s.add(node)
s.flush()
s.add(QuestionTaxonomy(question_id=q.id, node_id=node.id, source="auto", confidence=0.9))
s.commit()

try:
    s.execute(delete(Question).where(Question.paper_id == paper.id))
    s.commit()
    print("NO ERROR: FK not enforced, test setup would be broken")
except Exception as exc:  # noqa: BLE001 - 就是要看错误类型
    print("raised:", type(exc).__name__)
