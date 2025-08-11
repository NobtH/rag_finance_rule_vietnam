from config.settings import get_settings
from openai import OpenAI

class Generator:
    def __init__(self):
        config = get_settings()
        self.model_name = config.deepseek.model_name
        self.client = OpenAI(
            api_key=config.deepseek.api_key,
            base_url=config.deepseek.base_url
        )
    
    def generate_answer(self, question, context):
        prompt = (
            f'Dưới đây là 1 vài đoạn trích trong lĩnh vực tài chình ngân hàng:\n{context}'
            f'Dựa vào những nội dung trên, hãy trả lời câu hỏi sau:\n{question}'
        )
        response = self.client.chat.completions.create(
            model = self.model_name,
            messages=[
                {"role": "system", "content": "Bạn là trợ lý tài chình Tiếng Việt"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2
        )

        return response.choices[0].message.content
    