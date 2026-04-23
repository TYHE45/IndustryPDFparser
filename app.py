from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from config import AppConfig
from src.exporter import export_all
from src.pipeline import run_iterative_pipeline
from src.utils import safe_write_json



def _build_output_dir(input_path: Path, base_output_dir: Path) -> Path:
    source_name = input_path.stem
    parent_parts = _relative_parent_under_input(input_path)
    return _build_output_dir_from_parts(source_name, parent_parts, base_output_dir)


def _build_output_dir_from_parts(
    source_name: str,
    parent_parts: tuple[str, ...],
    base_output_dir: Path,
) -> Path:
    if parent_parts:
        return base_output_dir.joinpath(*parent_parts, source_name)
    return base_output_dir / source_name


def _relative_parent_under_input(input_path: Path) -> tuple[str, ...]:
    normalized_parts = [part.lower() for part in input_path.parts]
    try:
        input_index = normalized_parts.index("input")
    except ValueError:
        return ()

    relative_parts = input_path.parts[input_index + 1 : -1]
    return tuple(part for part in relative_parts if part not in {"", "."})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="面向产品数据相关 PDF 的结构化清洗与抽取工具")
    parser.add_argument("--input", required=True, help="输入 PDF 路径")
    parser.add_argument("--output", default="output", help="输出根目录，默认使用 output")
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()
    input_path = Path(args.input)
    base_output_dir = Path(args.output)

    if not input_path.exists():
        print(f"输入文件不存在: {input_path}", file=sys.stderr)
        return 1
    if input_path.suffix.lower() != ".pdf":
        print("当前版本仅支持 PDF 输入。", file=sys.stderr)
        return 1

    output_dir = _build_output_dir(input_path, base_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    config = AppConfig(input_path=input_path, output_dir=output_dir)
    result = run_iterative_pipeline(config)

    export_all(output_dir, result["document"], result["markdown"], result["summary"], result["tags"], result["process_log"])
    safe_write_json(output_dir / "review.json", result["review"])
    safe_write_json(output_dir / "review_rounds.json", result["review_rounds"])

    review = result["review"]
    review_round_count = len(result["review_rounds"])

    print("处理完成")
    print(f"输出目录: {output_dir}")
    if getattr(result["document"], "文档画像", None) is not None:
        profile = result["document"].文档画像
        print(f"文档类型: {profile.文档类型}")
        print(f"画像置信度: {profile.置信度}")
    print(f"评审轮次: {review_round_count}")
    print(f"最终总评: {review['最终总评']}")
    print(f"基础质量分: {review['基础质量分']}")
    print(f"事实正确性分: {review['事实正确性分']}")
    print(f"一致性与可追溯性分: {review['一致性与可追溯性分']}")
    print(f"红线是否触发: {review['红线是否触发']}")
    print(f"最终通过: {review['最终通过']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
