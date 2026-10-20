import anthropic
from dotenv import load_dotenv

load_dotenv()  # reads your .env file
client = anthropic.Anthropic()  # finds the key automatically

response = client.messages.create(
    model='claude-haiku-5-5',
    max_tokens=1000,
    messages=[{'role': 'user', 'content': 'Say hello in one friendly sentence.'}],
)

for block in response.content:
    if block.type == 'text':
        print(block.text)