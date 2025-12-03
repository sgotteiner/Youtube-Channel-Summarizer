# Application Logic Flow

This diagram illustrates the step-by-step logical decisions made by the application. It follows the journey of a single video from discovery to completion, focusing on the `if/else` checks that determine its path.

```mermaid
graph TD
    A[Start] --> B{Load Config};
    B --> C[Discover Videos];

    subgraph Video Discovery
        C --> D{For each video from channel};
        D --> E{Summary already exists?};
        E -- Yes --> D;
        E -- No --> F[Fetch full video metadata];
        F --> G{Is video duration > MAX_VIDEO_LENGTH?};
        G -- No --> J[Video is valid];
        G -- Yes --> H{APPLY_MAX_LENGTH_FOR_CAPTIONLESS_ONLY is True?};
        H -- No --> I[Video is invalid, skip];
        H -- Yes --> H2{Video has captions?};
        H2 -- Yes --> J;
        H2 -- No --> I;
        I --> D;
        J --> K{Add to processing queue};
        K --> L{Queue full based on NUM_VIDEOS_TO_PROCESS?};
        L -- No --> D;
        L -- Yes --> M[Stop discovery];
    end

    M --> N[Process Videos];

    subgraph Service Pipeline
        N --> O[Discovery Service processes video];
        O --> O2[Discovery Service sends video with has_captions flag to Download Service];
        O2 --> P[Download Service receives video];
        P --> Q{Does video have captions available?};
        Q -- Yes --> R[Download Service attempts to download captions];
        R --> S{Caption download successful?};
        S -- Yes --> S2[Process captions to transcription];
        S -- No --> T[Download Service fallback: download audio];
        Q -- No --> T;
        T --> T2[Download audio directly];
        S2 --> U{Update next stage to Summarization};
        T2 --> V{Update next stage to Transcription};
        U --> W[Send to Summarization Service];
        V --> X[Send to Transcription Service];
    end

    subgraph Transcription Service (if needed)
        X --> Y[Download Service has downloaded audio];
        Y --> Z[Transcription Service receives audio];
        Z --> Z1[Transcription Service converts audio to text];
        Z1 --> Z2[Transcription Service saves transcription];
        Z2 --> Z3[Transcription Service sends to Summarization Service];
    end

    subgraph Summarization Service
        W --> AA[Summarization Service receives transcription (from captions)];
        Z3 --> BB[Summarization Service receives transcription (from audio)];
        AA --> CC{IS_OPENAI_RUNTIME is True?};
        BB --> CC;
        CC -- No --> DD[Use raw transcription as summary];
        CC -- Yes --> EE[Check transcription token count];
        EE --> FF{Is token count > CHUNK_TARGET_SIZE?};
        FF -- Yes --> GG[Summarize in chunks recursively];
        FF -- No --> HH[Summarize directly];
        GG --> II[Final Summary];
        HH --> II;
        DD --> II;
    end

    subgraph Fallback Mechanism
        HH --> HH2{OpenAI API successful?};
        GG --> GG2{All chunks summarized?};
        HH2 -- No --> HH3[Save original transcription as summary];
        GG2 -- No --> GG3[Save partially summarized content as summary];
        HH3 --> II;
        GG3 --> II;
    end

    subgraph Cleanup
        II --> JJ[Save final summary];
        JJ --> KK{IS_SAVE_ONLY_SUMMARIES is True?};
        KK -- Yes --> LL[Delete intermediate files: video, audio, transcription];
        KK -- No --> MM[End];
        LL --> MM;
    end
```
