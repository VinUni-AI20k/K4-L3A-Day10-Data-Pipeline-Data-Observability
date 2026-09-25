from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, read_json, write_json


class TestSet(list):
    """TestSet wrapper ke thua list, cung cap thuoc tinh .samples de tuong thich moi lenh kiem tra."""
    @property
    def samples(self) -> list[dict[str, Any]]:
        return self


def build_test_set(df: pd.DataFrame, output_path: Path | str, num_questions: int = 5) -> TestSet:
    """Tao bo evaluation test set 5 dang cau hoi dua tren noi dung thuc te cua cac bai bao:
    1. summary: Tom tat noi dung nghien cuu chinh.
    2. authors: Ai la tac gia cua nghien cuu ve chu de X?
    3. date: Nghien cuu Y duoc cong bo vao nam/thang nao?
    4. category: Cong trinh nay thuoc linh vuc chuyen mon nao?
    5. multi_hop: Cau hoi ket hop lien nganh giua hai chu de.

    Moi mau bat buoc co: id, type, question_type, question, ground_truth, ground_truth_doc_ids.
    """
    if len(df) < 5:
        raise ValueError(f"Dataframe phai co it nhat 5 bai bao de sinh test set, hien co: {len(df)}")

    records = df.to_dict(orient="records")
    p0 = records[0]
    p1 = records[1]
    p2 = records[2]
    p3 = records[3]
    p4 = records[4]

    raw_items = [
        {
            "id": "eval_001",
            "type": "summary",
            "question_type": "summary",
            "question": f"What is the summary of the paper '{p0['title']}'?",
            "ground_truth": first_sentence(p0["summary"]),
            "ground_truth_doc_ids": [p0["paper_id"]],
        },
        {
            "id": "eval_002",
            "type": "authors",
            "question_type": "authors",
            "question": f"Who authored the paper '{p1['title']}'?",
            "ground_truth": p1["authors_joined"],
            "ground_truth_doc_ids": [p1["paper_id"]],
        },
        {
            "id": "eval_003",
            "type": "date",
            "question_type": "date",
            "question": f"When was the paper '{p2['title']}' published?",
            "ground_truth": str(p2["published"]),
            "ground_truth_doc_ids": [p2["paper_id"]],
        },
        {
            "id": "eval_004",
            "type": "category",
            "question_type": "category",
            "question": f"What categories are associated with the paper '{p3['title']}'?",
            "ground_truth": p3["categories_joined"],
            "ground_truth_doc_ids": [p3["paper_id"]],
        },
        {
            "id": "eval_005",
            "type": "multi_hop",
            "question_type": "multi_hop",
            "question": f"What is the summary of the paper '{p4['title']}' in relation to '{p0['title']}'?",
            "ground_truth": first_sentence(p4["summary"]),
            "ground_truth_doc_ids": [p4["paper_id"], p0["paper_id"]],
        },
    ]

    target = Path(output_path)
    write_json(target, raw_items)
    return TestSet(raw_items)


def load_or_create_test_set(
    df: pd.DataFrame,
    output_path: Path | str,
    force_refresh: bool = False,
) -> TestSet:
    """Doc test set co san neu hop le (5 cau), nguoc lai sinh moi."""
    target = Path(output_path)
    if target.exists() and not force_refresh:
        try:
            data = read_json(target)
            if isinstance(data, list) and len(data) == 5:
                return TestSet(data)
        except Exception:
            pass
    return build_test_set(df, target, num_questions=5)
