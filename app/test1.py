from rag.rag1 import RAG

test = RAG()
# test.vector_store.delete_table('document_table')
# test.vector_store.delete_table('chunk_table')
test.document_embedding()
test.chunk_and_embediing()
question = 'thông tin các loại taì khoản cho cá nhân'

results = test.vector_store.keyword_search(question, limit_docs=10, limit_chunks=10)

print("🔎 Kết quả tìm kiếm:")

print("\n--- Tài liệu khớp (Matched Documents) ---")
matched_docs = results["matched_docs"]
for i, doc in enumerate(matched_docs):
    doc_id, file_name, rank = doc
    print(f"[{i+1}] 📄 ID: {doc_id} | Tên file: {file_name} | Độ liên quan (Rank): {rank}")

print("\n--- Đoạn văn bản khớp (Matched Chunks) ---")
matched_chunks = results["matched_chunks"]
for i, chunk in enumerate(matched_chunks):
    chunk_id, content, doc_id, file_name, rank = chunk
    print(f"[{i+1}] 📖 ID: {chunk_id} | Doc ID: {doc_id} | Tên file: {file_name} | Độ liên quan (Rank): {rank}")
    print(f"    Nội dung:")
    print(f"    {content}")

# results = test.vector_store.semantic_search(question, limits_chunks=10)

# print("\n--- Đoạn văn bản khớp (Matched Chunks) ---")
# matched_chunks = results["matched_chunks"]
# for i, chunk in enumerate(matched_chunks):
#     cid, content = chunk
#     print(f"[{i + 1}] ID: {cid} | ")
#     print(f"{content}")