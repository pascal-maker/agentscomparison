from transformers import pipeline

def format_messages(messages):
    prompt = ""
    for message in messages:
        if message['role'] == 'user':
            prompt += f"User: {message['content']}\n"
        elif message['role'] == 'assistant':
            prompt += f"Assistant: {message['content']}\n"
    prompt += "Assistant: "
    return prompt

messages = [{"role": "user", "content": "Who are you?"}]
formatted_prompt = format_messages(messages)
pipe = pipeline("text-generation", model="deepseek-ai/DeepSeek-R1-Distill-Llama-8B")
result = pipe(formatted_prompt, max_new_tokens=100, temperature=0.6)
print(result[0]['generated_text'])