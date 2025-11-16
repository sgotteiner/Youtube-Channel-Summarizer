"""
Module for summarizing text using OpenAI's API.
"""
import os
from typing import Optional, List
from openai import AsyncOpenAI
import tiktoken
import logging
import asyncio

class OpenAISummarizerAgent:
    """
    An asynchronous class to handle text summarization using the OpenAI API.
    It supports chunking and recursive summarization for long texts.
    """
    TOKEN_LIMIT = 4000
    CHUNK_TARGET_SIZE = 3000

    def __init__(self, is_openai_runtime: bool = False, logger: Optional[logging.Logger] = None):
        """
        Initializes the OpenAISummarizerAgent.
        """
        self.is_openai_runtime = is_openai_runtime
        self.logger = logger
        self.client = self._setup_api_client()
        try:
            self.encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self.encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")

    def _setup_api_client(self) -> Optional[AsyncOpenAI]:
        """Loads the OpenAI API key and creates an async client."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            if self.is_openai_runtime:
                raise ValueError("API key not found for OpenAI runtime. Make sure you have a .env file with your OPENAI_API_KEY.")
            return None
        return AsyncOpenAI(api_key=api_key)

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

    async def _summarize_text(self, text: str, prompt: str) -> Optional[str]:
        """
        Makes a single async call to the OpenAI API to summarize a piece of text.
        """
        try:
            self.logger.info("Making an async call to the OpenAI API...")
            response = await self.client.chat.completions.create(
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

    async def _recursive_summarize(self, text: str) -> Optional[str]:
        """
        Recursively summarizes a long text by splitting it into chunks asynchronously.
        """
        token_count = self._get_token_count(text)
        self.logger.info(f"Starting recursive summarization for text with {token_count} tokens.")

        if token_count <= self.CHUNK_TARGET_SIZE:
            prompt = "You are a summary assistant. Write a summary of the transcribed audio. Don't forget new lines."
            return await self._summarize_text(text, prompt)

        chunks = self._split_text_into_chunks(text)
        self.logger.info(f"Text split into {len(chunks)} chunks for summarization.")

        # Process chunks concurrently for better performance
        tasks = []
        for i, chunk in enumerate(chunks):
            self.logger.info(f"Preparing to summarize chunk {i+1}/{len(chunks)}...")
            prompt = "You are a summary assistant. Summarize this chunk of a larger transcription."
            task = asyncio.create_task(self._summarize_text(chunk, prompt))
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect successful summaries, handling possible exceptions
        summaries = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Error processing chunk {i}: {result}")
                # Continue processing even if one chunk fails
            elif result:
                summaries.append(result)

        if not summaries:
            self.logger.error("No successful summaries were generated from any chunks.")
            return None

        combined_summary = " ".join(summaries)
        self.logger.info("All chunks summarized. Now summarizing the combined summary.")
        return await self._recursive_summarize(combined_summary)

    async def summary_call(self, transcription: str, video_id: str = None) -> Optional[str]:
        """
        Asynchronously generates a summary of the provided transcription.

        Args:
            transcription (str): The transcription to summarize
            video_id (str, optional): The video ID for logging purposes

        Returns:
            Optional[str]: The summary text, or None if failed
        """
        if not self.is_openai_runtime:
            self.logger.info("OpenAI runtime is OFF. Returning raw transcription as summary.")
            # Still log the completion status if video_id is provided
            if video_id:
                self.logger.info("[%s] Summarization task completed successfully", video_id)
            return transcription

        result = await self._recursive_summarize(transcription)

        # Log completion status with video_id if provided
        if video_id:
            if result:
                self.logger.info("[%s] Summarization task completed successfully", video_id)
            else:
                self.logger.error("[%s] Failed to generate summary", video_id)

        return result