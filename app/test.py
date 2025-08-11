from rag.rag import RAG
import fitz

question = 'Hành vi nào bị cấm khi thực hiện khi dùng thẻ'
test = RAG(corpus_path='data/corpus.csv')
# test.delete_table()
# test.document_embedding()
results = test.search(question)

print('Kết quả tìm kiếm:')

for i, doc in enumerate(results):
    print(f'[{i + 1} ID: {doc['cid']} Score: {doc['score']}]')
    print(f'content\n {doc['content']}\n')
    print('_'*50)

print(test.generate_answer(question, results[:5]))
