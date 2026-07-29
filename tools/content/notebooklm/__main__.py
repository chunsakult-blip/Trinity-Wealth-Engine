"""CLI entry point — manual trigger เท่านั้น (ไม่ผูกกับ Agent/@tool)

Usage:
    python -m tools.content.notebooklm briefing_file.md --confirm-generation
"""
import argparse
import asyncio
from pathlib import Path

from tools.content.notebooklm.pipeline import run_notebooklm_post_production_pipeline
from tools.content.notebooklm.prompts import extract_notebooklm_prompts


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m tools.content.notebooklm")
    parser.add_argument("briefing_file", type=Path)
    parser.add_argument("--title", default=None, help="ชื่อ Notebook (ค่าเริ่มต้น: ชื่อไฟล์ briefing)")
    parser.add_argument("--confirm-generation", action="store_true", dest="confirm_generation")
    parser.add_argument(
        "--with-research", action="store_true", dest="with_research",
        help="บังคับเปิด Deep Research แม้ไฟล์จะไม่มี prompt แบบ [RESEARCH] (ปกติเปิดอัตโนมัติถ้ามี)",
    )
    parser.add_argument("--research-query", default=None, dest="research_query")
    parser.add_argument("--language", default="th", dest="audio_language")
    parser.add_argument("--timeout", type=int, default=5_400, dest="timeout_seconds")  # 1 ชม. 30 นาที
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    prompts = extract_notebooklm_prompts(args.briefing_file.read_text(encoding="utf-8"))
    result = asyncio.run(run_notebooklm_post_production_pipeline(
        args.briefing_file,
        confirm_generation=args.confirm_generation,
        with_research=args.with_research,
        research_query=args.research_query,
        notebooklm_prompts=prompts,
        audio_language=args.audio_language,
        timeout_seconds=args.timeout_seconds,
        title=args.title,
    ))
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
