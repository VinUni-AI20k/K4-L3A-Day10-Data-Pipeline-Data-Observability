from __future__ import annotations

<<<<<<< HEAD
=======
from dataclasses import dataclass
>>>>>>> a42a52f (feat: complete Day 10 data pipeline, observability and repair flow)
from pathlib import Path
from typing import Any

import pandas as pd

<<<<<<< HEAD
from core.utils import first_sentence, normalize_whitespace, read_json, write_json


class BenchmarkTestSet(list[dict[str, Any]]):
    """List-compatible benchmark result with the checkpoint's ``samples`` API."""

    @property
    def samples(self) -> "BenchmarkTestSet":
        return self


def _as_text(value: Any) -> str:
    """Convert a dataframe value to stable, human-readable benchmark text."""
    if isinstance(value, (list, tuple)):
        return ", ".join(normalize_whitespace(str(item)) for item in value if str(item).strip())
    return normalize_whitespace(str(value)) if pd.notna(value) else ""


def _published_label(value: Any) -> str:
    published = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(published):
        return "Unknown"
    return published.strftime("%B %Y")


def _category_label(value: Any) -> str:
    return _as_text(value) or "Crossref did not supply a specialist category."


def _sample(sample_id: int, question_type: str, question: str, ground_truth: str,
            doc_ids: list[str]) -> dict[str, Any]:
    return {
        "id": f"eval_{sample_id:03d}",
        "type": question_type,
        # The evaluator in this starter repo uses question_type.  Keeping both
        # fields preserves compatibility while exposing the requested schema.
        "question_type": question_type,
        "question": question,
        "ground_truth": ground_truth,
        "ground_truth_doc_ids": doc_ids,
    }


def build_test_set(df: pd.DataFrame, output_path) -> BenchmarkTestSet:
    """Build a deterministic, source-grounded benchmark from clean papers.
=======
from core.utils import normalize_whitespace, read_json, write_json

QUESTION_TYPES = ('summary', 'authors', 'date', 'category', 'multi_hop')
>>>>>>> a42a52f (feat: complete Day 10 data pipeline, observability and repair flow)


@dataclass
class BenchmarkTestSet:
    samples: list[dict[str, Any]]

    def __post_init__(self) -> None:
        if not isinstance(self.samples, list) or len(self.samples) != 5:
            raise ValueError('Benchmark must contain exactly five samples.')
        ids, types = set(), []
        for sample in self.samples:
            if not isinstance(sample, dict):
                raise ValueError('Each sample must be an object.')
            for key in ('id', 'type', 'question', 'ground_truth'):
                if not isinstance(sample.get(key), str) or not sample[key].strip():
                    raise ValueError(f'Sample requires a nonempty string: {key}')
            doc_ids = sample.get('ground_truth_doc_ids')
            if not isinstance(doc_ids, list) or not doc_ids or any(not isinstance(x, str) or not x.strip() for x in doc_ids):
                raise ValueError('ground_truth_doc_ids must be nonempty document ID strings.')
            if len(set(doc_ids)) != len(doc_ids):
                raise ValueError('Duplicate ground-truth document IDs.')
            if sample['type'] == 'multi_hop' and len(doc_ids) != 2:
                raise ValueError('multi_hop requires exactly two source documents.')
            if sample['id'] in ids:
                raise ValueError('Sample IDs must be unique.')
            ids.add(sample['id'])
            types.append(sample['type'])
            # Compatibility with the existing metrics evaluator.
            sample['question_type'] = sample['type']
        if set(types) != set(QUESTION_TYPES):
            raise ValueError('Benchmark requires one sample of each of the five types.')


def _text(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return ', '.join(filter(None, (_text(part) for part in value)))
    return normalize_whitespace(value) if isinstance(value, str) else ''


def build_test_set(df: pd.DataFrame, output_path: Path) -> list[dict[str, Any]]:
    """Explicitly generate five questions from the first usable, distinct papers.

    Missing subjects remain unknown; categories are never invented from titles.
    Use load_or_create_test_set for evaluations to preserve the baseline set.
    """
<<<<<<< HEAD
    required = {
        "paper_id", "title", "summary", "published", "authors_joined", "categories_joined"
    }
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"Cannot build test set; missing columns: {', '.join(missing)}")

    usable = df.copy()
    usable = usable.dropna(subset=["paper_id", "title", "summary"])
    usable = usable[
        usable["paper_id"].astype(str).str.strip().ne("")
        & usable["title"].astype(str).str.strip().ne("")
        & usable["summary"].astype(str).str.strip().ne("")
    ]
    usable = usable.drop_duplicates(subset=["paper_id"]).reset_index(drop=True)
    if len(usable) < 5:
        raise ValueError("At least 5 valid, unique papers are required to build the benchmark")

    # Deterministic spread across the corpus rather than relying on random state.
    positions = [round(index * (len(usable) - 1) / 9) for index in range(10)]
    papers = [usable.iloc[position] for position in positions]
    samples: list[dict[str, Any]] = []

    for row in papers[0:2]:
        title, paper_id = _as_text(row["title"]), _as_text(row["paper_id"])
        samples.append(_sample(
            len(samples) + 1,
            "summary",
            f'What is the main research contribution of "{title}"?',
            first_sentence(_as_text(row["summary"])),
            [paper_id],
        ))

    for row in papers[2:4]:
        title, paper_id = _as_text(row["title"]), _as_text(row["paper_id"])
        category = _category_label(row["categories_joined"])
        samples.append(_sample(
            len(samples) + 1,
            "authors",
            f'Who authored the research "{title}" about {category}?',
            _as_text(row["authors_joined"]),
            [paper_id],
        ))

    for row in papers[4:6]:
        title, paper_id = _as_text(row["title"]), _as_text(row["paper_id"])
        samples.append(_sample(
            len(samples) + 1,
            "date",
            f'In which month and year was "{title}" published?',
            _published_label(row["published"]),
            [paper_id],
        ))

    for row in papers[6:8]:
        title, paper_id = _as_text(row["title"]), _as_text(row["paper_id"])
        samples.append(_sample(
            len(samples) + 1,
            "category",
            f'Which specialist fields does the paper "{title}" belong to?',
            _category_label(row["categories_joined"]),
            [paper_id],
        ))

    for left, right in ((papers[8], papers[1]), (papers[9], papers[0])):
        left_title, right_title = _as_text(left["title"]), _as_text(right["title"])
        left_id, right_id = _as_text(left["paper_id"]), _as_text(right["paper_id"])
        left_category = _category_label(left["categories_joined"])
        right_category = _category_label(right["categories_joined"])
        ground_truth = (
            f'{left_title} ({left_category}): {first_sentence(_as_text(left["summary"]))} '
            f'{right_title} ({right_category}): {first_sentence(_as_text(right["summary"]))}'
        )
        samples.append(_sample(
            len(samples) + 1,
            "multi_hop",
            f'How do "{left_title}" and "{right_title}" complement each other across their fields?',
            ground_truth,
            [left_id, right_id],
        ))

    result = BenchmarkTestSet(samples)
    write_json(Path(output_path), result)
    return result


def load_or_create_test_set(df: pd.DataFrame, settings_or_path, refresh: bool | None = None) -> BenchmarkTestSet:
    """Load a stable benchmark unless it is missing or an explicit refresh is requested.

    ``settings_or_path`` accepts either the project Settings object or a direct
    output path, making the helper convenient in scripts and checkpoint commands.
    """
    if hasattr(settings_or_path, "paths"):
        output_path = Path(settings_or_path.paths.eval_testset)
        should_refresh = settings_or_path.refresh_test_set if refresh is None else refresh
    else:
        output_path = Path(settings_or_path)
        should_refresh = False if refresh is None else refresh

    if output_path.exists() and not should_refresh:
        payload = read_json(output_path)
        if isinstance(payload, list) and payload:
            return BenchmarkTestSet(payload)
    return build_test_set(df, output_path)
=======
    required = {'paper_id', 'title', 'summary', 'published'}
    if missing := required - set(df.columns):
        raise ValueError(f'Missing benchmark columns: {sorted(missing)}')
    papers, seen = [], set()
    for row in df.to_dict(orient='records'):
        paper = {key: _text(row.get(key)) for key in ('paper_id', 'title', 'summary')}
        published = pd.to_datetime(row.get('published'), errors='coerce')
        if not all(paper.values()) or pd.isna(published) or paper['paper_id'] in seen:
            continue
        paper['published'] = published.strftime('%Y-%m')
        paper['authors'] = _text(row.get('authors_joined')) or _text(row.get('authors')) or 'Unknown'
        paper['categories'] = _text(row.get('categories_joined')) or _text(row.get('categories'))
        seen.add(paper['paper_id'])
        papers.append(paper)
    if len(papers) < 2:
        raise ValueError('At least two distinct papers with title, summary and valid publication date are required.')
    left = papers[0]
    right = next((p for p in papers[1:] if p['title'].casefold() != left['title'].casefold()), None)
    if right is None:
        raise ValueError('Multi-hop requires two papers with different titles.')
    category_paper = next((p for p in papers if p['categories']), left)
    samples = []

    def add(kind: str, question: str, answer: str, sources: list[dict]) -> None:
        samples.append({'id': f'q_{kind}_{len(samples) + 1:02d}', 'type': kind,
                        'question': question, 'ground_truth': answer,
                        'ground_truth_doc_ids': [p['paper_id'] for p in sources]})

    add('summary', f"Summarize the main research in '{left['title']}'.", left['summary'], [left])
    add('authors', f"Who authored the study '{right['title']}'?", right['authors'], [right])
    add('date', f"When was '{left['title']}' published? Give the year and month (YYYY-MM).", left['published'], [left])
    add('category', f"What categories are recorded for '{category_paper['title']}'? State if the source metadata does not provide them.",
        category_paper['categories'] or 'Subject categories are not provided in the source metadata.', [category_paper])
    add('multi_hop', f"Compare the research problems addressed by '{left['title']}' and '{right['title']}'. Explain the focus of each study using both papers.",
        f"{left['title']}: {left['summary']}\n{right['title']}: {right['summary']}", [left, right])
    benchmark = BenchmarkTestSet(samples)
    write_json(Path(output_path), benchmark.samples)
    return benchmark.samples


def load_or_create_test_set(df: pd.DataFrame, output_path: Path) -> BenchmarkTestSet:
    """Load and validate the saved benchmark, or create it when absent.

    Invalid files raise ValueError rather than silently changing evaluation data.
    Loading does not depend on df, so corrupted data cannot alter ground truth.
    """
    path = Path(output_path)
    if path.exists():
        payload = read_json(path)
        return BenchmarkTestSet(payload)
    return BenchmarkTestSet(build_test_set(df, path))
>>>>>>> a42a52f (feat: complete Day 10 data pipeline, observability and repair flow)
