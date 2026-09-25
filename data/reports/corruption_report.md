# Corruption Report - Doi Chieu Baseline vs Corrupted vs Repaired

_Sinh tu dong luc 2026-09-25T09:56:28+00:00._

## 1. Bang So Sanh Hieu Nang 3 Trang Thai

| Chi so | Baseline | Corrupted | Repaired | Corrupted vs Baseline | Repaired vs Baseline |
| --- | --- | --- | --- | --- | --- |
| So cau hoi danh gia | 10 | 10 | 10 | 0.0000 (=) | 0.0000 (=) |
| Retrieval Hit Rate | 1.0000 | 0.7000 | 1.0000 | -0.3000 (xau di) | 0.0000 (=) |
| Mean Token F1 | 0.8000 | 0.3440 | 0.8000 | -0.4560 (xau di) | 0.0000 (=) |
| LLM Judge Accuracy | 0.8000 | 0.3000 | 0.8000 | -0.5000 (xau di) | 0.0000 (=) |
| Mean Judge Score (1-5) | 4.2000 | 2.2000 | 4.2000 | -2.0000 (xau di) | 0.0000 (=) |

## 2. Data Quality Gate

| Trang thai | Ket qua tong the | Expectation khong dat |
| --- | --- | --- |
| Corrupted | FAIL | `paper_id_unique`, `summary_length_at_least_30`, `freshness_threshold_check` |
| Repaired | PASS | - |

## 3. Freshness SLA

| Hang muc | Corrupted | Repaired |
| --- | --- | --- |
| So dong qua han | 8 | 0 |
| Tong so dong | 22 | 24 |
| Ty le qua han | 0.3636 | 0.0000 |
| Dat Freshness SLA | FAIL | PASS |
| Bai moi nhat | 2026-08-27 | 2026-09-15 |

## 4. Phan Tich

- **Retrieval Hit Rate**: 1.0000 -> 0.7000 khi du lieu bi lam ban (giam 30.0%). Sau repair ve dung muc baseline (1.0000).
- **Mean Token F1**: 0.8000 -> 0.3440 khi du lieu bi lam ban (giam 57.0%). Sau repair ve dung muc baseline (0.8000).
- **LLM Judge Accuracy**: 0.8000 -> 0.3000 khi du lieu bi lam ban (giam 62.5%). Sau repair ve dung muc baseline (0.8000).
- **Mean Judge Score (1-5)**: 4.2000 -> 2.2000 khi du lieu bi lam ban (giam 47.6%). Sau repair ve dung muc baseline (4.2000).

**Ket luan:** Idempotent repair doc lai tu raw snapshot da khoi phuc hoan toan cac chi so ve muc baseline.
