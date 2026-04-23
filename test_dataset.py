import os
from datasets import load_dataset
import pandas as pd

def test_download():
    print("Bắt đầu tải dataset: th1nhng0/vietnamese-legal-documents (config: content)")
    print("Vui lòng đợi (có thể mất 5-10 phút tùy mạng do file nặng)...")
    
    try:
        # Tắt streaming để tải toàn bộ parquet về máy, tránh lỗi PyArrow
        ds = load_dataset(
            "th1nhng0/vietnamese-legal-documents", 
            "content", 
            split="data",
            streaming=False
        )
        
        print(f"\n[OK] Tải thành công! Tổng số văn bản: {len(ds)}")
        
        # Lấy thử 5 văn bản đầu tiên
        print("\n=== Lấy thử 5 văn bản đầu tiên ===")
        import re
        for i in range(5):
            doc = ds[i]
            title = doc.get("title") or doc.get("name") or doc.get("ten_van_ban") or doc.get("id") or "Không có tiêu đề"
            
            raw_content = doc.get("text") or doc.get("content") or doc.get("content_html") or "Không có nội dung"
            if "<html" in raw_content or "<body" in raw_content or "<div" in raw_content or "<p" in raw_content:
                raw_content = re.sub('<[^<]+>', ' ', raw_content).strip()
                raw_content = re.sub(r'\s+', ' ', raw_content)
                
            print(f"\n[{i+1}] Tiêu đề (ID): {title}")
            print(f"Trích đoạn: {raw_content[:200]}...")
            print("-" * 50)
            
    except Exception as e:
        print(f"\n[LỖI] Không thể tải dataset: {str(e)}")
        
if __name__ == "__main__":
    test_download()
