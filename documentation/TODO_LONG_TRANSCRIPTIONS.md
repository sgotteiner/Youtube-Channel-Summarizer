# Long Transcription Processing & Rate Limiting TODOs

## 1. Rate Limiting Implementation for OpenAI API
- Implement token-aware concurrency controller based on OpenAI TPM (Tokens Per Minute) limits
- Use TokenRateLimiter class to manage concurrent API calls respecting rate limits
- Calculate token usage based on estimated tokens per request and per minute allowance

## 2. Intelligent Retry Mechanism
- Implement exponential backoff retry logic for individual failed chunks only
- Use tenacity library for robust retry with `@retry` decorator
- Only retry specific chunks that fail due to rate limits, not entire batch

## 3. Fallback Mechanisms
- Add fallback to save raw transcriptions when summarization fails completely
- Preserve partial summaries from successful chunks
- Implement state saving to allow recovery from rate limit interruptions
- Graceful fallback to CPU-based summarization models if available

## 4. Enhanced Concurrency Control
- Allow configurable number of simultaneous API calls (MAX_REQUESTS)
- Dynamic adjustment based on actual usage vs. rate limits
- Sequential processing option as performance fallback

## 5. Local CPU-based Summarization Models
- Investigate Whisper + BART-Large-CNN for local processing
- Consider LED-base (Longformer Encoder-Decoder) for long-context summarization
- Implement Extractive summarization (TextRank/Sumy/LexRank) as CPU-friendly fallback

## 6. Chunk Management
- Intelligent chunk grouping to reduce API calls while respecting token limits
- Dynamic chunk sizing based on rate limit feedback
- Save intermediate summary states during recursive summarization

## 7. Monitoring & Metrics
- Track API usage vs. limits
- Monitor rate limit hit frequency
- Performance metrics for different approaches