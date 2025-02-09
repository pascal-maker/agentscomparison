import gradio as gr
import ai_gradio

# Create a simple chat interface using OpenAI's GPT-4 Turbo.
chat_interface = gr.load(
    name='openai:gpt-4-turbo',  # Use the provider:model syntax.
    src=ai_gradio.registry,
    title='AI Chat',
    description='Chat with GPT-4 Turbo via OpenAI'
)

# Launch the interface.
chat_interface.launch()
