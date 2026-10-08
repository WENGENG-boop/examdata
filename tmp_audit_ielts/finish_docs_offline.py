"""Correct claims against retained evidence, without upstream requests."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
paths=[root/'ielts-api/API.md',root/'ielts-api/DEVELOPMENT.md',root/'examdata/docs/IELTS_API.md']
for p in paths:
    t=p.read_text(encoding='utf-8')
    t=t.replace('剑1–20 整本 PDF 20/20','剑1–20 PDF 文件 20/20（剑20为Test1分册）')
    t=t.replace('| **S3 整本 PDF** | 原版整本书 |','| **S3 PDF** | 剑1–19整本；剑20分册 |')
    t=t.replace('整本 PDF         20/20  剑1–20，642 MB，oid 全部一致','PDF 文件         20/20  剑1–19整本 + 剑20 Test1，642.4 MiB，oid 全部一致')
    t=t.replace('整本 PDF         20/20   剑1–20','PDF 文件         20/20   剑1–19整本 + 剑20 Test1（分册）')
    t=t.replace('整本 PDF    20/20   剑1–20（Git LFS）+ 剑21（社区镜像，146 页）','PDF 文件    20/20   剑1–19整本 + 剑20 Test1（Git LFS）；另有剑21社区镜像146页')
    t=t.replace('剑1–20 原版整本 PDF，走 GitHub **Git LFS**。','剑1–19整本 PDF、剑20 Test1 分册走 GitHub **Git LFS**。剑20其余分册见 `book20Set()`；单个 `pdfLfs(20)` 不代表整本。')
    t=t.replace('**唯一覆盖剑桥21 的源**','**提供剑桥21结构化数据的源**')
    note='\n> 覆盖数字为2026-10-01保留的联网审查证据，不保证源站持续可用。84/84表示可调用套数，不等于每套40个独立题干完整；组合题与 `questions_missing` 必须单独检查。319 Part 表示剑1–20有可用原文，剑20仍缺1段。PDF哈希一致证明所下载文件与LFS指针相符，不证明整本教材内容完整。本轮续作及未完成检查见 `AUDIT_REPORT.md`（位于工作区旁ielts-api）。\n'
    t=t.replace('\n---\n',note+'\n---\n',1) if '\n---\n' in t else t+note
    p.write_text(t,encoding='utf-8')
