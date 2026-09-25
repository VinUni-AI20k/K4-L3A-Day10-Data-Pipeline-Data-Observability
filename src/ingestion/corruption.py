from __future__ import annotations

import pandas as pd


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    import json
    import os
    import random
    from datetime import timedelta
    
    corrupted_df = df.copy()
    logs = []
    
    # 1. Drop mot so latest records (top 20%)
    if len(corrupted_df) > 5:
        corrupted_df['published_dt'] = pd.to_datetime(corrupted_df['published'])
        corrupted_df = corrupted_df.sort_values(by='published_dt', ascending=False)
        drop_count = max(1, int(len(corrupted_df) * 0.2))
        dropped_ids = corrupted_df.iloc[:drop_count]['paper_id'].tolist()
        corrupted_df = corrupted_df.iloc[drop_count:].copy()
        corrupted_df = corrupted_df.drop(columns=['published_dt'])
        logs.append({"type": "drop_latest", "dropped_count": drop_count, "dropped_ids": dropped_ids})

    corrupted_df = corrupted_df.reset_index(drop=True)
    n = len(corrupted_df)
    
    if n > 0:
        # 2. Blank summary
        idx_blank = random.randint(0, n - 1)
        corrupted_df.at[idx_blank, 'summary'] = ""
        logs.append({"type": "blank_summary", "paper_id": corrupted_df.at[idx_blank, 'paper_id']})
        
        # 3. Inject noise
        idx_noise = random.randint(0, n - 1)
        corrupted_df.at[idx_noise, 'summary'] = str(corrupted_df.at[idx_noise, 'summary']) + " 0xDEADBEEF ERROR DATA NOISE!@#"
        logs.append({"type": "inject_noise", "paper_id": corrupted_df.at[idx_noise, 'paper_id']})
        
        # 4. Truncate title
        idx_trunc = random.randint(0, n - 1)
        title = str(corrupted_df.at[idx_trunc, 'title'])
        corrupted_df.at[idx_trunc, 'title'] = title[:7] if len(title) > 7 else title
        logs.append({"type": "truncate_title", "paper_id": corrupted_df.at[idx_trunc, 'paper_id']})
        
        # 5. Stale date (lui ve 365 ngay)
        idx_stale = random.randint(0, n - 1)
        try:
            pub_date = pd.to_datetime(corrupted_df.at[idx_stale, 'published'])
            new_date = pub_date - timedelta(days=365)
            corrupted_df.at[idx_stale, 'published'] = new_date.isoformat()
            if 'age_days' in corrupted_df.columns:
                corrupted_df.at[idx_stale, 'age_days'] += 365
        except Exception:
            pass
        logs.append({"type": "stale_date", "paper_id": corrupted_df.at[idx_stale, 'paper_id']})
        
        # 6. Add duplicate rows
        idx_dup = random.randint(0, n - 1)
        dup_row = corrupted_df.iloc[[idx_dup]].copy()
        corrupted_df = pd.concat([corrupted_df, dup_row], ignore_index=True)
        logs.append({"type": "duplicate_row", "paper_id": dup_row.iloc[0]['paper_id']})

    # 7. Rebuild text_for_embedding
    def rebuild_text(row):
        return (f"Title: {row.get('title', '')}\n"
                f"Authors: {row.get('authors_joined', '')}\n"
                f"Published: {row.get('published', '')}\n"
                f"Categories: {row.get('categories_joined', '')}\n"
                f"Summary: {row.get('summary', '')}")
                
    corrupted_df['text_for_embedding'] = corrupted_df.apply(rebuild_text, axis=1)
    if 'summary_chars' in corrupted_df.columns:
        corrupted_df['summary_chars'] = corrupted_df['summary'].fillna("").astype(str).str.len()

    # 8. Ghi corruption log
    os.makedirs(os.path.dirname(output_log_path), exist_ok=True)
    with open(output_log_path, 'w', encoding='utf-8') as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)
        
    return corrupted_df
