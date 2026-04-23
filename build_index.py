import os
import sys
import asyncio

# Setup environment paths relative to current directory
current_dir = os.getcwd()
data_dir = os.path.join(current_dir, "data")
vector_store_dir = os.path.join(data_dir, "vector_store")

os.environ["VECTOR_STORE_PATH"] = vector_store_dir
os.environ["AUTO_INDEX"] = "false"
os.environ["EMBEDDING_MODEL"] = "mainguyen9/vietlegal-harrier-0.6b"

# Create directories and wipe old data
import shutil
if os.path.exists(vector_store_dir):
    print("🧹 Xóa bộ nhớ Vector cũ để nạp lại từ đầu...")
    shutil.rmtree(vector_store_dir)
os.makedirs(vector_store_dir, exist_ok=True)

# Add current dir to python path so it can find backend module
sys.path.append(current_dir)

from backend.services.rag_service import rag_service

async def main():
    print("==================================================")
    print("🚀 BẮT ĐẦU TẠO VECTOR DATABASE ĐỘC LẬP")
    print("==================================================")
    print(f"📂 Thư mục lưu dữ liệu: {vector_store_dir}\n")
    
    # Chỉ định số văn bản cần xử lý (VD: 200000 để nạp toàn bộ)
    MAX_DOCS = 200000
    
    result = await rag_service.index_dataset(max_docs=MAX_DOCS)
    
    if result.get("status") == "complete":
        print("\n✅ [THÀNH CÔNG] Đã tạo xong Vector Database!")
        print(f"Tổng số văn bản: {result.get('total_documents')}")
        print(f"Tổng số chunks (đoạn): {result.get('total_chunks')}")
        print("\n➡️ BÂY GIỜ BẠN CÓ THỂ CHẠY DOCKER, API SẼ TỰ ĐỘNG NHẬN DATA NÀY!")
    else:
        print(f"\n❌ [LỖI] Tạo database thất bại: {result}")

if __name__ == "__main__":
    asyncio.run(main())
