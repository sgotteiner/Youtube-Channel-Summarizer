# Software Design Document: YouTube Channel Summarizer (Refactored)

**Version:** 2.0  
**Date:** November 14, 2025

## Table of Contents
1. [Introduction](#introduction)
2. [Current Architecture Overview](#current-architecture-overview)
3. [Component Design](#component-design)
4. [Design Patterns](#design-patterns)
5. [Data Flow](#data-flow)
6. [Error Handling](#error-handling)

## Introduction

### Purpose
This document describes the current architecture of the YouTube Channel Summarizer application after significant refactoring to implement proper design patterns and eliminate code duplication. The system now uses a refined microservices architecture enhanced with Template Method and Factory patterns.

### Scope
The application automates the process of fetching, transcribing, and summarizing YouTube videos from specified channels. It has been refactored to use proper design patterns, eliminate code duplication, and improve maintainability.

## Current Architecture Overview

### Architectural Style
The system uses a **refined microservices architecture** enhanced with design patterns:
- Individual services (Discovery, Download, Audio Extraction, Transcription, Summarization)
- RabbitMQ for command queues coordinating workflow
- Kafka for event streaming to analytics and logging services
- PostgreSQL for structured metadata storage
- MongoDB for unstructured content (transcriptions, summaries)

### Pattern Enhancement
The architecture has been enhanced with:
- **Template Method Pattern**: Standardizes service operations while eliminating code duplication
- **Factory Pattern**: Ensures consistent manager creation across services
- **Single Responsibility Principle**: Each component has a single, well-defined purpose

## Component Design

### Service Layer (src/services/)
Each service now extends `ServiceTemplate[T]` where T is the service-specific return type:

- **DiscoveryService**: Discovers new videos from YouTube channels
- **DownloadService**: Downloads video files from URLs
- **AudioExtractionService**: Extracts audio from video files
- **TranscriptionService**: Converts audio to text
- **SummarizationService**: Generates summaries from text using AI

All services follow the same pattern but only implement their business logic.

### Pipeline Tools Layer (src/pipeline/)
Specialized tools for domain-specific operations:

- **VideoMetadataFetcher**: Retrieves video metadata from YouTube
- **VideoDownloader**: Downloads video files with proper error handling
- **AudioExtractor**: Extracts audio streams from video files
- **AudioTranscriber**: Converts audio to text with chunking for long files
- **AgentSummarizer**: Calls OpenAI for text summarization

Each tool handles its own domain concerns.

### Manager Layer (src/utils/)
Manages infrastructure concerns:

- **DatabaseManager**: Handles PostgreSQL operations with proper error handling
- **QueueManager**: Manages RabbitMQ operations
- **EventManager**: Handles event publishing to both RabbitMQ and Kafka

### Pattern Layer (src/patterns/)
Implements the core architectural patterns:

- **ServiceTemplatePattern**: Implements Template Method pattern for services
- **ManagerFactory**: Implements Factory pattern for manager creation

## Design Patterns

### Template Method Pattern (`ServiceTemplate`)
**Problem**: Code duplication across services with similar workflows
**Solution**: Abstract class defines the common workflow but defers specific steps to subclasses

Benefits:
- Services reduced from ~200 lines to ~50 lines
- Consistent behavior across all services
- Easy to add new services following the same pattern
- Standardized error handling and logging

### Factory Pattern (`ManagerFactory`)
**Problem**: Inconsistent manager creation with duplicate configuration
**Solution**: Factory class creates all managers with consistent configuration

Benefits:
- Consistent manager behavior across services
- Centralized configuration management
- Easy to update manager setup

### Separation of Concerns
**Problem**: Mixed business logic, infrastructure logic, and orchestration
**Solution**: Clear boundaries between service orchestration, domain operations, and infrastructure

## Data Flow

### Service Execution Flow
1. Service receives message from RabbitMQ queue
2. Service updates video status in PostgreSQL to reflect processing state
3. Service calls its specific pipeline tool (with automatic video_id-based logging)
4. Pipeline tool performs domain-specific operation (all operations are I/O-bound, not CPU-intensive)
5. On success:
   - Service updates video status to completion status in PostgreSQL
   - Service sends message to next queue in pipeline
   - Service publishes event to Kafka/RabbitMQ
6. On failure:
   - Service updates video status to FAILED in PostgreSQL

### File Path Management
Each service updates the `working_file_path` field in the database with the output from its operation:
- Discovery: Doesn't set working_file_path (initial step)
- Download: Sets to video file path
- Audio Extraction: Sets to audio file path
- Transcription: Sets to transcription file path
- Summarization: Final step, no further file processing

## Error Handling

### Service-Level Resilience
- Services inherit common error handling from ServiceTemplate
- All exceptions caught and video status updated to FAILED
- No single service failure affects others in the pipeline

### Pipeline Continuity
- Messages remain in queue if service fails, ensuring no data loss
- Each service updates database status independently
- Failure at one stage doesn't halt processing of other videos

### Retry Mechanisms
- RabbitMQ handles message redelivery for failed service instances
- Pipeline tools handle their own internal robustness internally