from __future__ import annotations

from typing import Any

import pandas as pd
from core.utils import write_json


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
   if len(df) < 4:
      raise ValueError("At least four clean documents are required to build the test set.")
   rows = df.sort_values("paper_id").head(10).to_dict(orient="records")
   templates = (
      ("summary", "What is the summary of '{title}'?", "summary"),
      ("authors", "Who authored '{title}'?", "authors_joined"),
      ("date", "When was '{title}' published?", "published"),
      ("categories", "What categories describe '{title}'?", "categories_joined"),
   )
   questions = []
   for index, row in enumerate(rows):
      question_type, template, answer_column = templates[index % len(templates)]
      questions.append(
         {
            "id": f"q-{index + 1:02d}",
            "question_type": question_type,
            "question": template.format(title=row["title"]),
            "ground_truth": str(row[answer_column]),
            "ground_truth_doc_ids": [row["paper_id"]],
         }
      )
   write_json(output_path, questions)
   return questions
