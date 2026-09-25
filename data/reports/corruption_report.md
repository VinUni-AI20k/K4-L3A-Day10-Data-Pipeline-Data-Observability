# Corruption, Repair & Comparison Report

Generated: 2026-09-25T10:13:18.517984+00:00

## Bang Doi Chieu 3 Trang Thai

| Metric | Baseline (Sach) | Corrupted (Loi) | Repaired (Phuc hoi) |
| :--- | :--- | :--- | :--- |
| Data Quality Gate | PASS (rows=24) | FAIL (rows=21) | PASS (rows=24) |
| Freshness Check | PASS (stale=4.17%) | PASS (stale=9.52%) | PASS (stale=4.17%) |
| Retrieval Hit Rate | 1.0000 | 0.0000 | 1.0000 |
| Mean Token F1 | 0.7745 | 0.5430 | 0.7745 |
| LLM Judge Accuracy | 0.6000 | 0.4000 | 0.6000 |

## Phan Tich Suy Giam & Phuc Hoi

- **Data Corruption gay sut giam Hit Rate**: +1.0000 (silent failure phat hien).
- **Data Corruption gay sut giam Token F1**: +0.2314.
- **Sau Idempotent Repair, Hit Rate phuc hoi ve muc baseline**: PASS.
- **Sau Idempotent Repair, Token F1 phuc hoi ve muc baseline**: PASS.
- **Data Quality Gate sau phuc hoi**: PASS.

