from __future__ import annotations

from datetime import datetime
import pandas as pd

from ingestion.crossref import PaperRecord
# Giả định module utils đã được import để sử dụng các hàm hỗ trợ
from core import utils 


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records thành dataframe sẵn sàng để embed.

    Pseudo-code:
    1. Normalize title, summary, authors, categories.
    2. Parse published/updated date.
    3. Tinh age_days.
    4. Tao cot helper:
       - authors_joined
       - categories_joined
       - summary_chars
       - text_for_embedding
    5. Drop duplicates va filter row xau.
    6. Sort dataframe va return.
    """
    clean_rows = []
    
    for rec in records:
        # 1. Normalize title, summary, authors, categories
        # Sử dụng hàm normalize_whitespace để xóa khoảng trắng thừa
        title = utils.normalize_whitespace(rec.title)
        summary = utils.normalize_whitespace(rec.summary)
        authors = [utils.normalize_whitespace(a) for a in rec.authors if a]
        categories = [utils.normalize_whitespace(c) for c in rec.categories if c]
        primary_cat = utils.normalize_whitespace(rec.primary_category)
        
        # Bỏ qua các bản ghi rác không có tiêu đề hoặc mã ID
        if not rec.paper_id or not title:
            continue

        # 4. Tạo các cột helper
        # Sử dụng compact_join để ghép nối danh sách thành chuỗi cách nhau bởi dấu phẩy[cite: 1]
        authors_joined = utils.compact_join(authors)
        categories_joined = utils.compact_join(categories)
        summary_chars = len(summary)
        
        # Tạo khối văn bản nguyên khối (text_for_embedding) làm dữ liệu gốc cho Vector DB
        text_for_embedding = (
            f"Title: {title}\n"
            f"Authors: {authors_joined}\n"
            f"Published: {rec.published}\n"
            f"Categories: {categories_joined}\n"
            f"Summary: {summary}"
        )
        
        clean_rows.append({
            "paper_id": rec.paper_id,
            "title": title,
            "summary": summary,
            "authors_joined": authors_joined,
            "categories_joined": categories_joined,
            "primary_category": primary_cat,
            "published": rec.published,
            "updated": rec.updated,
            "abs_url": rec.abs_url,
            "pdf_url": rec.pdf_url,
            "comment": rec.comment,
            "summary_chars": summary_chars,
            "text_for_embedding": text_for_embedding
        })

    # Tạo DataFrame từ danh sách các bản ghi đã được làm sạch cơ bản
    df = pd.DataFrame(clean_rows)
    if df.empty:
        return df
        
    # 2 & 3. Parse published date và tính age_days bằng Pandas
    # Chuyển đổi run_date và cột published về cùng chuẩn UTC (để có thể trừ đi nhau một cách an toàn)
    run_date_utc = pd.to_datetime(run_date, utc=True)
    published_dt = pd.to_datetime(df["published"], errors="coerce", utc=True)
    
    # Tính tuổi đời bài báo theo ngày (những bài báo thiếu ngày xuất bản hợp lệ sẽ bị null)
    df["age_days"] = (run_date_utc - published_dt).dt.days
    
    # 5. Drop duplicates và filter row xấu
    # Lọc bỏ các bài tóm tắt quá ngắn (dưới 10 ký tự là vô nghĩa) hoặc không có thông tin ngày tháng
    df = df[df["summary_chars"] > 10]
    
    # Khử trùng lặp theo khóa duy nhất paper_id, ưu tiên giữ lại dòng xuất hiện đầu tiên
    df = df.drop_duplicates(subset=["paper_id"], keep="first")
    
    # 6. Sort dataframe và return
    # Sắp xếp bài báo có tuổi đời nhỏ nhất (mới nhất) lên đầu
    df = df.sort_values(by=["age_days", "paper_id"], ascending=[True, True])
    
    # Reset index để dataframe sạch sẽ trước khi trả về
    return df.reset_index(drop=True)