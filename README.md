## An AI-powered multi-agent system that generates personalized music sets based on user preferences such as genre, mood, event, and duration.


## Project Overview

Creating a music playlist for a particular occasion can be time-consuming. This system automates music discovery and curation using an AI-driven workflow.

Users provide their preferences, and the system discovers relevant tracks, ranks them, filters duplicate versions, and generates a curated music set.

## Features

- **Personalized Music Discovery:** Recommendations based on genre, mood, event, and duration.
- **AI-Based Planning:** Gemini plans the music discovery process.
- **Multi-Agent Workflow:** LangGraph manages the workflow and execution stages.
- **Track Discovery:** Uses Last.fm API to retrieve music metadata and similar tracks.
- **Track Ranking:** Ranks candidate tracks using a heuristic relevance score.
- **Duplicate Filtering:** Filters duplicate track versions.
- **Artist Diversity:** Limits repeated tracks from the same artist.
- **CSV Export:** Download the generated music set as a CSV file.
- **Interactive Interface:** Simple and user-friendly Streamlit application.

## Tech Stack

| Technology | Purpose |
|---|---|
| Python | Core programming language |
| Google Gemini API | AI planning and curation |
| LangGraph | Workflow orchestration and state management |
| Last.fm API | Music discovery and metadata |
| Streamlit | User interface |
| Pandas | Data handling |

## System Architecture

1. **User Input:** Collects genre, mood, event, duration, and optional favourite track or artist.
2. **AI Planner:** Gemini determines the discovery strategy.
3. **Music Discovery:** Python tools retrieve candidate tracks using Last.fm.
4. **Recovery:** The workflow attempts an alternative discovery route if no candidates are found.
5. **Ranking and Filtering:** Tracks are scored, duplicate versions are filtered, and artist repetition is limited.
6. **AI Curation:** Gemini generates an explanation of the final music set.
7. **Output:** Displays the curated tracks and provides CSV export.

## Project Structure

```text
AI-Music-Set-Generator/
│
├── app.py              # Streamlit application
├── agent.py            # AI agent and LangGraph workflow
├── music_tools.py      # Last.fm API integration
├── .env                # API keys (not uploaded)
├── .env.example        # Environment variable template
├── .gitignore          # Git ignored files
├── requirements.txt    # Project dependencies
└── README.md           # Project documentation
```

## Installation and Setup

### 1. Clone the repository

```bash
git clone https://github.com/sumirandaby/AI-Music-Set-Generator.git
```

### 2. Navigate to the project directory

```bash
cd AI-Music-Set-Generator
```

### 3. Create a virtual environment

```bash
python -m venv venv
```

Activate it:

**Windows PowerShell:**
```powershell
.\venv\Scripts\Activate.ps1
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure API keys

Create a `.env` file in the project root directory and add your API keys:

```env
LASTFM_API_KEY=your_lastfm_api_key
GEMINI_API_KEY=your_gemini_api_key
```

Use `.env.example` as a reference.

### 6. Run the application

```bash
python -m streamlit run app.py
```

The application will open in your browser.

## Current Scope and Limitations

- Last.fm is used for music discovery and metadata, not full-track playback.
- Spotify search links, if displayed, help users find tracks on Spotify.
- Track relevance scores are heuristic and do not represent actual audio analysis.
- BPM, musical key, and energy are not verified by the current system.
- Opening, build-up, peak, and closing sections are presentation groupings rather than audio-validated sequencing.
