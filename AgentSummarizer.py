"""
Module for summarizing text using OpenAI's API.
"""

import os
import openai
from dotenv import load_dotenv
from typing import Optional


class OpenAISummarizerAgent:
    def __init__(self, is_openai_runtime: bool = False, logger=None):
        self.is_openai_runtime = is_openai_runtime
        self.logger = logger
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("API key not found. Make sure you have created a .env file with your OPENAI_API_KEY.")
        openai.api_key = api_key

    def summary_call(self, transcription: str) -> Optional[str]:
        """
        Generate a summary of the provided transcription.
        
        :param transcription: Text to summarize
        :return: Summary text or None if an error occurred
        """
        if not self.is_openai_runtime:
            self.logger.info("Runtime flag is False. Skipping actual OpenAI API call.")
            return "Mocked response: Hello! (runtime off)"

        try:
            self.logger.info("Making a call to the OpenAI API...")
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a summary assistant."},
                    {"role": "user", "content": f"Summarize this: {transcription}"}
                ]
            )
            assistant_message = response.choices[0].message.content
            self.logger.info(f"\nSuccess! Assistant's response: '{assistant_message}'")
            return assistant_message
        except Exception as e:
            self.logger.error(f"\nAn error occurred during OpenAI API call: {e}")
            return None
