"""
Module for summarizing text using OpenAI's API.
"""
import os
from typing import Optional, List
import openai
from dotenv import load_dotenv
import tiktoken
import logging

class OpenAISummarizerAgent:
    """
    A class to handle text summarization using the OpenAI API.
    It supports chunking and recursive summarization for long texts.
    """
    # gpt-3.5-turbo has a context window of 4096 tokens, but let's be conservative.
    TOKEN_LIMIT = 4000
    # Define a target size for each chunk to leave space for the prompt.
    CHUNK_TARGET_SIZE = 3000

    def __init__(self, is_openai_runtime: bool = False, logger: Optional[logging.Logger] = None):
        """
        Initializes the OpenAISummarizerAgent.

        Args:
            is_openai_runtime (bool): If True, makes real API calls. Otherwise, returns raw text.
            logger (Optional[logging.Logger]): Logger for logging messages.
        """
        self.is_openai_runtime = is_openai_runtime
        self.logger = logger
        self._setup_api()
        try:
            self.encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self.encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")

    def _setup_api(self):
        """Loads the OpenAI API key from environment variables."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("API key not found. Make sure you have a .env file with your OPENAI_API_KEY.")
        openai.api_key = api_key

    def _get_token_count(self, text: str) -> int:
        """Calculates the number of tokens in a given text."""
        return len(self.encoding.encode(text))

    def _split_text_into_chunks(self, text: str) -> List[str]:
        """
        Splits text into chunks, each under the CHUNK_TARGET_SIZE token limit.
        """
        tokens = self.encoding.encode(text)
        chunks = []
        start = 0
        while start < len(tokens):
            end = start + self.CHUNK_TARGET_SIZE
            chunk_tokens = tokens[start:end]
            chunks.append(self.encoding.decode(chunk_tokens))
            start = end
        return chunks

    def _summarize_text(self, text: str, prompt: str) -> Optional[str]:
        """
        Makes a single call to the OpenAI API to summarize a piece of text.
        """
        try:
            self.logger.info("Making a call to the OpenAI API...")
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Summarize this: {text}"}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"An error occurred during OpenAI API call: {e}")
            return None

    def _recursive_summarize(self, text: str) -> Optional[str]:
        """
        Recursively summarizes a long text by splitting it into chunks.
        """
        token_count = self._get_token_count(text)
        self.logger.info(f"Starting recursive summarization for text with {token_count} tokens.")

        if token_count <= self.CHUNK_TARGET_SIZE:
            prompt = "You are a summary assistant. Write a summary of the transcribed audio. Don't forget new lines."
            return self._summarize_text(text, prompt)

        chunks = self._split_text_into_chunks(text)
        self.logger.info(f"Text split into {len(chunks)} chunks for summarization.")
        
        summaries = []
        for i, chunk in enumerate(chunks):
            self.logger.info(f"Summarizing chunk {i+1}/{len(chunks)}...")
            prompt = "You are a summary assistant. Summarize this chunk of a larger transcription."
            summary = self._summarize_text(chunk, prompt)
            if summary:
                summaries.append(summary)
        
        combined_summary = " ".join(summaries)
        self.logger.info("All chunks summarized. Now summarizing the combined summary.")
        # Recursively call to summarize the combined summaries if it's still too long
        return self._recursive_summarize(combined_summary)

    def summary_call(self, transcription: str) -> Optional[str]:
        """
        Generate a summary of the provided transcription.
        This is the main entry point for summarization.
        """
        if not self.is_openai_runtime:
            self.logger.info("OpenAI runtime is OFF. Returning raw transcription as summary.")
            return transcription

        return self._recursive_summarize(transcription)