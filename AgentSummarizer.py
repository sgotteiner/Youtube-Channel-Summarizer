import os
import openai
from dotenv import load_dotenv

class OpenAISummarizerAgent:
    def __init__(self, is_runtime: bool = False):
        self.is_runtime = is_runtime
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("API key not found. Make sure you have created a .env file with your OPENAI_API_KEY.")
        openai.api_key = api_key

    def summary_call(self, transcription):
        if not self.is_runtime:
            print("Runtime flag is False. Skipping actual OpenAI API call.")
            return "Mocked response: Hello! (runtime off)"

        try:
            print("Making a call to the OpenAI API...")
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a summary assistant."},
                    {"role": "user", "content": f"Summarize this: {transcription}"}
                ]
            )
            assistant_message = response.choices[0].message.content
            print(f"\nSuccess! Assistant's response: '{assistant_message}'")
            return assistant_message
        except Exception as e:
            print(f"\nAn error occurred during OpenAI API call: {e}")
            return None