"""诊断 paper 34 q1 合计行与若干 sub-part 缺失原因（一次性脚本）。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pymupdf
from sqlalchemy import select

from examdata.core.config import get_settings
from examdata.core.db import get_session_factory
from examdata.core.models import (
    Artifact,
    Document,
    DocumentRevision,
    Paper,
    Question,
)
from examdata.core.storage import ContentAddressedStore


def artifact_path(session, store, doc):
    rev = session.get(DocumentRevision, doc.current_revision_id)
    artifact = session.get(Artifact, rev.artifact_id)
    return store.path_for_key(artifact.storage_key)


def main() -> None:
    settings = get_settings()
    session = get_session_factory()()
    store = ContentAddressedStore(settings.artifacts_dir)
    try:
        # paper 34 = wbi13-01
        paper = session.get(Paper, 34)
        doc = session.get(Document, paper.document_id)
        path = artifact_path(session, store, doc)
        with pymupdf.open(path) as pdf:
            for page_no in range(len(pdf)):
                text = pdf[page_no].get_text()
                if "Total for Question 1" in text:
                    idx = text.find("Total for Question 1")
                    print(f"--- wbi13-01 page {page_no + 1} around marker ---")
                    print(repr(text[max(0, idx - 120) : idx + 160]))
            # also show all total lines in the whole pdf
            print("--- all total lines (regex) ---")
            full = "\n".join(p.get_text() for p in pdf)
            for m in re.finditer(r"\(?\s*Total for Question[^\n]{0,60}", full):
                print(repr(m.group(0)))

        # sub-part diagnostics: paper 33 q8(a)
        paper = session.get(Paper, 33)
        doc = session.get(Document, paper.document_id)
        path = artifact_path(session, store, doc)
        with pymupdf.open(path) as pdf:
            q = session.scalar(
                select(Question).where(
                    Question.paper_id == 33, Question.number_path == "8(a)"
                )
            )
            attrs = q.attrs or {}
            for region in attrs.get("regions") or []:
                page = pdf[region["page"] - 1]
                text = page.get_text(clip=pymupdf.Rect(region["bbox"]))
                print(f"--- wbi11-01 8(a) region page {region['page']} ---")
                print(repr(text[-300:]))
    finally:
        session.close()


if __name__ == "__main__":
    main()
