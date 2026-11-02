import os
import re
import json
import math
import unicodedata
from typing import TypedDict

from dotenv import load_dotenv
from google import genai
from langgraph.graph import StateGraph, START, END

from music_tools import (
    search_music,
    get_similar_tracks,
    get_tracks_by_genre
)


# ==================================================
# CONFIGURATION
# ==================================================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-3.5-flash"

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file")

client = genai.Client(api_key=GEMINI_API_KEY)

MAX_TRACKS_PER_ARTIST = 2


# ==================================================
# STATE
# ==================================================

class MusicState(TypedDict):

    user_input: dict
    plan: dict
    raw_tracks: list
    selected_tracks: list
    playlist_note: str
    errors: list


# ==================================================
# GEMINI FUNCTIONS
# ==================================================

def call_gemini(prompt):

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt
    )

    return response.text.strip()


def parse_json_response(response_text):

    try:
        cleaned = response_text.strip()

        cleaned = re.sub(
            r"^```(?:json)?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE
        )

        cleaned = re.sub(r"\s*```$", "", cleaned)

        return json.loads(cleaned)

    except (json.JSONDecodeError, TypeError):
        raise ValueError("Gemini returned invalid JSON")


# ==================================================
# TRACK NORMALIZATION
# ==================================================

def get_artist_name(track):

    artist = track.get("artist", "Unknown Artist")

    if isinstance(artist, dict):
        artist = artist.get("name", "Unknown Artist")

    if not artist:
        artist = "Unknown Artist"

    return str(artist).strip()


def normalize_track(track, source="unknown"):

    if not isinstance(track, dict):
        return None

    name = (
        track.get("name")
        or track.get("title")
        or track.get("track")
    )

    if not name:
        return None

    artist = get_artist_name(track)

    return {
        "name": str(name).strip(),
        "artist": artist,
        "url": track.get("url", ""),
        "mbid": track.get("mbid", ""),
        "source": source
    }


def normalize_text(value):

    value = unicodedata.normalize("NFKD", str(value))

    value = "".join(
        char for char in value
        if not unicodedata.combining(char)
    )

    value = value.lower()
    value = re.sub(r"[^\w\s]", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


# ==================================================
# DUPLICATE VERSION DETECTION
# ==================================================

VERSION_KEYWORDS = [
    "remix",
    "remixed",
    "radio edit",
    "extended mix",
    "extended version",
    "club mix",
    "club version",
    "dj edit",
    "dj mix",
    "rework",
    "bootleg",
    "mashup",
    "sped up",
    "slowed",
    "nightcore",
    "instrumental",
    "acoustic version",
    "live version",
    "live edit",
    "remaster",
    "remastered",
    "original mix",
    "vip mix"
]


def is_versioned_track(title):

    title = str(title).lower()

    return any(
        keyword in title
        for keyword in VERSION_KEYWORDS
    )


def normalize_track_title(title):

    """
    Converts different versions of a song into a common
    base title for duplicate detection.
    """

    title = str(title).lower().strip()

    # Remove version information inside brackets.
    def remove_version_brackets(match):

        content = match.group(1).lower()

        if any(
            keyword in content
            for keyword in VERSION_KEYWORDS
        ):
            return ""

        return match.group(0)

    title = re.sub(
        r"[\(\[]([^\)\]]*)[\)\]]",
        remove_version_brackets,
        title
    )

    # Remove version descriptions at the end.
    for keyword in VERSION_KEYWORDS:

        pattern = (
            r"\s*[-–—:]\s*"
            + re.escape(keyword)
            + r"\s*$"
        )

        title = re.sub(
            pattern,
            "",
            title,
            flags=re.IGNORECASE
        )

        pattern = (
            r"\s+"
            + re.escape(keyword)
            + r"\s*$"
        )

        title = re.sub(
            pattern,
            "",
            title,
            flags=re.IGNORECASE
        )

    return normalize_text(title)


def normalize_artist(artist):

    artist = normalize_text(artist)

    # Use the main artist for collaborations.
    artist = re.split(
        r"\b(feat|featuring|ft|with|vs)\b|&",
        artist
    )[0].strip()

    return artist or "unknown artist"


# ==================================================
# TOOL EXECUTION
# ==================================================

def execute_tool(tool_name, **kwargs):

    """
    Executes the selected music discovery tool.
    """

    try:

        if tool_name == "get_tracks_by_genre":

            return get_tracks_by_genre(
                kwargs["genre"]
            )

        elif tool_name == "get_similar_tracks":

            return get_similar_tracks(
                kwargs["track_name"],
                kwargs["artist"]
            )

        elif tool_name == "search_music":

            return search_music(
                kwargs["track_name"],
                kwargs.get("artist")
            )

        else:

            print("Unknown tool:", tool_name)
            return []

    except Exception as error:

        print(
            f"Tool execution failed ({tool_name}):",
            error
        )

        return []


# ==================================================
# PLANNER NODE
# ==================================================

def planner_node(state):

    print("\n========== PLANNER NODE ==========")

    user_input = state["user_input"]

    prompt = f"""
You are an AI music set planning agent.

The user wants a DJ playlist with these preferences:

Genre: {user_input['genre']}
Mood: {user_input['mood']}
Duration: {user_input['duration']} minutes
Event: {user_input['event']}
Favorite track: {user_input.get('favorite_track', '')}
Favorite artist: {user_input.get('favorite_artist', '')}

Decide which music discovery tools should be used.

Available tools:

1. get_tracks_by_genre
   Finds popular tracks belonging to a genre.

2. get_similar_tracks
   Finds tracks similar to a given track.

3. search_music
   Searches for a specific track or artist.

Return ONLY valid JSON in this format:

{{
    "use_similar_tracks": true,
    "similar_seed_count": 2,
    "use_favorite_search": true,
    "reason": "Short explanation"
}}

Rules:
- Use similar tracks when a favorite track is provided.
- Use favorite search when a favorite artist or track is provided.
- similar_seed_count must be between 0 and 3.
- Do not invent tracks.
"""

    try:

        response = call_gemini(prompt)
        plan = parse_json_response(response)

        plan["similar_seed_count"] = max(
            0,
            min(
                3,
                int(plan.get("similar_seed_count", 2))
            )
        )

        plan["use_similar_tracks"] = bool(
            plan.get("use_similar_tracks", True)
        )

        plan["use_favorite_search"] = bool(
            plan.get("use_favorite_search", True)
        )

        print("Planner decision:", plan)

    except Exception as error:

        print("Planner fallback:", error)

        plan = {
            "use_similar_tracks": bool(
                user_input.get("favorite_track")
            ),
            "similar_seed_count": 2,
            "use_favorite_search": bool(
                user_input.get("favorite_track")
                or user_input.get("favorite_artist")
            ),
            "reason": "Fallback planning strategy"
        }

        state["errors"].append(
            f"Planner error: {error}"
        )

    return {
        **state,
        "plan": plan
    }


# ==================================================
# DISCOVERY NODE
# ==================================================

def discovery_node(state):

    print("\n========== DISCOVERY NODE ==========")

    user_input = state["user_input"]
    plan = state["plan"]

    discovered_tracks = []

    # ----------------------------------------------
    # 1. Genre-based discovery
    # ----------------------------------------------

    print("\nSearching tracks by genre...")

    genre_results = execute_tool(
        "get_tracks_by_genre",
        genre=user_input["genre"]
    )

    if isinstance(genre_results, list):

        for track in genre_results:

            normalized = normalize_track(
                track,
                source="genre"
            )

            if normalized:
                discovered_tracks.append(normalized)

    print(
        "Genre tracks found:",
        len(discovered_tracks)
    )

    # ----------------------------------------------
    # 2. Similar-track discovery
    # ----------------------------------------------

    favorite_track = user_input.get(
        "favorite_track",
        ""
    )

    if (
        plan.get("use_similar_tracks")
        and favorite_track
    ):

        print("\nSearching similar tracks...")

        seed_count = plan.get(
            "similar_seed_count",
            2
        )

        seeds = discovered_tracks[:seed_count]

        # Include the user's favorite track as a seed.
        seeds.insert(
            0,
            {
                "name": favorite_track,
                "artist": user_input.get(
                    "favorite_artist",
                    ""
                )
            }
        )

        for seed in seeds[:3]:

            similar_results = execute_tool(
                "get_similar_tracks",
                track_name=seed.get("name", favorite_track),
                artist=seed.get(
                    "artist",
                    user_input.get("favorite_artist", "")
                )
            )

            if isinstance(similar_results, list):

                for track in similar_results:

                    normalized = normalize_track(
                        track,
                        source="similar"
                    )

                    if normalized:
                        discovered_tracks.append(normalized)

    # ----------------------------------------------
    # 3. Favorite track / artist discovery
    # ----------------------------------------------

    if plan.get("use_favorite_search"):

        favorite_artist = user_input.get(
            "favorite_artist",
            ""
        )

        if favorite_track:

            print("\nSearching favorite track...")

            results = execute_tool(
                "search_music",
                track_name=favorite_track,
                artist=favorite_artist or None
            )

            if isinstance(results, list):

                for track in results:

                    normalized = normalize_track(
                        track,
                        source="favorite"
                    )

                    if normalized:
                        discovered_tracks.append(normalized)

        elif favorite_artist:

            print("\nSearching favorite artist...")

            results = execute_tool(
                "search_music",
                track_name=favorite_artist
            )

            if isinstance(results, list):

                for track in results:

                    normalized = normalize_track(
                        track,
                        source="favorite"
                    )

                    if normalized:
                        discovered_tracks.append(normalized)

    print(
        "\nTotal discovered tracks:",
        len(discovered_tracks)
    )

    return {
        **state,
        "raw_tracks": discovered_tracks
    }


# ==================================================
# RECOVERY NODE
# ==================================================

def recovery_node(state):

    print("\n========== RECOVERY NODE ==========")

    print(
        "No tracks found. Retrying genre discovery..."
    )

    genre = state["user_input"]["genre"]

    try:

        results = execute_tool(
            "get_tracks_by_genre",
            genre=genre
        )

        recovered_tracks = []

        if isinstance(results, list):

            for track in results:

                normalized = normalize_track(
                    track,
                    source="recovery"
                )

                if normalized:
                    recovered_tracks.append(normalized)

        print(
            "Recovered tracks:",
            len(recovered_tracks)
        )

        return {
            **state,
            "raw_tracks": recovered_tracks
        }

    except Exception as error:

        state["errors"].append(
            f"Recovery error: {error}"
        )

        return {
            **state,
            "raw_tracks": []
        }


# ==================================================
# ROUTING AFTER DISCOVERY
# ==================================================

def route_after_discovery(state):

    if not state["raw_tracks"]:
        return "recovery"

    return "ranking"


# ==================================================
# TRACK SCORING
# ==================================================

def calculate_track_score(track, user_input):

    score = 0

    name = track.get("name", "").lower()
    artist = track.get("artist", "").lower()

    source = track.get("source", "")

    genre = user_input["genre"].lower()
    mood = user_input["mood"].lower()
    event = user_input["event"].lower()

    favorite_track = user_input.get(
        "favorite_track",
        ""
    ).lower()

    favorite_artist = user_input.get(
        "favorite_artist",
        ""
    ).lower()

    # ----------------------------------------------
    # Genre relevance
    # ----------------------------------------------

    if source == "genre":
        score += 3

    elif source == "similar":
        score += 2

    elif source == "favorite":
        score += 1

    # ----------------------------------------------
    # Mood relevance
    # ----------------------------------------------

    mood_keywords = {

        "energetic": [
            "party", "dance", "fire", "power",
            "high", "club", "beat", "rock"
        ],

        "chill": [
            "slow", "relax", "dream", "calm",
            "peace", "soft"
        ],

        "emotional": [
            "love", "heart", "sad", "feel",
            "memory", "pain"
        ],

        "dark": [
            "dark", "night", "shadow", "deep"
        ],

        "uplifting": [
            "rise", "hope", "freedom", "light",
            "dream", "sky"
        ],

        "romantic": [
            "love", "heart", "romance", "beloved"
        ],

        "melancholic": [
            "alone", "sad", "tears", "memory"
        ],

        "dreamy": [
            "dream", "star", "moon", "sky"
        ],

        "aggressive": [
            "rage", "fight", "power", "fire"
        ]
    }

    keywords = mood_keywords.get(mood, [])

    if any(keyword in name for keyword in keywords):
        score += 3

    # ----------------------------------------------
    # Event relevance
    # ----------------------------------------------

    event_keywords = {

        "music festival": [
            "festival", "party", "dance", "fire"
        ],

        "club night": [
            "club", "dance", "party", "night"
        ],

        "house party": [
            "party", "dance", "tonight"
        ],

        "road trip": [
            "road", "drive", "freedom", "journey"
        ],

        "workout": [
            "power", "strong", "fire", "energy"
        ],

        "wedding": [
            "love", "dance", "wedding", "celebration"
        ],

        "college fest": [
            "party", "dance", "celebration", "fire"
        ],

        "pool party": [
            "summer", "party", "dance", "beach"
        ]
    }

    keywords = event_keywords.get(event, [])

    if any(keyword in name for keyword in keywords):
        score += 2

    # ----------------------------------------------
    # Favorite artist relevance
    # ----------------------------------------------

    if favorite_artist and favorite_artist in artist:
        score += 1

    # ----------------------------------------------
    # Favorite track relevance
    # ----------------------------------------------

    if favorite_track and favorite_track in name:
        score += 1

    return min(score, 10)


# ==================================================
# DUPLICATE FILTERING
# ==================================================

def remove_duplicate_versions(tracks):

    """
    Prefer non-remix/original versions.

    If an original version exists, remix versions
    of that song are removed.

    If only remixes are available, retain the
    highest-scoring version.

    Different artists with the same unversioned
    song title are not automatically grouped together.
    """

    grouped_tracks = {}

    for track in tracks:

        title = track.get("name", "").strip()
        artist = track.get("artist", "").strip()

        title_key = normalize_track_title(title)

        if not title_key:
            continue

        track["original_title_key"] = title_key

        grouped_tracks.setdefault(
            title_key,
            []
        ).append(track)

    filtered_tracks = []
    removed_count = 0

    for title_key, versions in grouped_tracks.items():

        original_versions = [
            track
            for track in versions
            if not is_versioned_track(track["name"])
        ]

        if original_versions:

            # Keep distinct original songs by different artists.
            seen_artists = set()

            for track in original_versions:

                artist_key = normalize_artist(
                    track["artist"]
                )

                if artist_key in seen_artists:

                    removed_count += 1
                    continue

                seen_artists.add(artist_key)
                filtered_tracks.append(track)

            # Remove all remix/version candidates
            # when an original version is available.
            removed_count += (
                len(versions) - len(original_versions)
            )

        else:

            # No original available. Keep only the
            # highest-scoring version of this title.
            versions.sort(
                key=lambda track: track.get("score", 0),
                reverse=True
            )

            filtered_tracks.append(versions[0])

            removed_count += len(versions) - 1

    print(
        "Duplicate versions removed:",
        removed_count
    )

    return filtered_tracks


# ==================================================
# RANKING AND DIVERSITY NODE
# ==================================================

def ranking_node(state):

    print("\n========== TRACK RANKING ==========")

    tracks = state["raw_tracks"]
    user_input = state["user_input"]

    if not tracks:

        return {
            **state,
            "selected_tracks": []
        }

    # ----------------------------------------------
    # 1. Calculate scores
    # ----------------------------------------------

    for track in tracks:

        track["score"] = calculate_track_score(
            track,
            user_input
        )

    # ----------------------------------------------
    # 2. Remove duplicate versions
    # ----------------------------------------------

    diverse_tracks = remove_duplicate_versions(
        tracks
    )

    print(
        "Tracks after duplicate filtering:",
        len(diverse_tracks)
    )

    # ----------------------------------------------
    # 3. Rank by score
    # ----------------------------------------------

    diverse_tracks.sort(
        key=lambda track: track.get("score", 0),
        reverse=True
    )

    # ----------------------------------------------
    # 4. Select tracks with artist diversity
    # ----------------------------------------------

    duration = float(user_input["duration"])

    required_tracks = math.ceil(duration / 4)

    artist_counts = {}
    selected_tracks = []

    artist_skipped = 0

    for track in diverse_tracks:

        artist_key = normalize_artist(
            track.get("artist", "")
        )

        current_count = artist_counts.get(
            artist_key,
            0
        )

        if current_count >= MAX_TRACKS_PER_ARTIST:

            artist_skipped += 1

            print(
                "Artist limit reached. Skipping:",
                track["name"],
                "-",
                track["artist"]
            )

            continue

        selected_tracks.append(track)

        artist_counts[artist_key] = current_count + 1

        if len(selected_tracks) >= required_tracks:
            break

    # ----------------------------------------------
    # 5. Selection summary
    # ----------------------------------------------

    print("\n========== DIVERSITY SUMMARY ==========")

    print("Requested duration:", duration, "minutes")
    print("Estimated tracks required:", required_tracks)

    print("Tracks selected:", len(selected_tracks))

    print(
        "Maximum tracks per artist:",
        MAX_TRACKS_PER_ARTIST
    )

    print(
        "Tracks skipped due to artist limit:",
        artist_skipped
    )

    if len(selected_tracks) < required_tracks:

        print(
            "Warning: Not enough unique tracks were "
            "available to fill the requested playlist."
        )

    print("\nSelected playlist:")

    for index, track in enumerate(
        selected_tracks,
        start=1
    ):

        print(
            f"{index}. {track['name']} — "
            f"{track['artist']} "
            f"(Score: {track['score']}/10)"
        )

    return {
        **state,
        "selected_tracks": selected_tracks
    }


# ==================================================
# CURATOR NODE
# ==================================================

def curator_node(state):

    print("\n========== CURATOR NODE ==========")

    tracks = state["selected_tracks"]
    user_input = state["user_input"]

    if not tracks:

        return {
            **state,
            "playlist_note": (
                "No suitable tracks were found. "
                "Try changing your genre or preferences."
            )
        }

    track_list = "\n".join(
        [
            f"{index}. {track['name']} — {track['artist']}"
            for index, track in enumerate(
                tracks,
                start=1
            )
        ]
    )

    prompt = f"""
You are an experienced DJ and music curator.

Create a short explanation for this DJ music set.

Genre: {user_input['genre']}
Mood: {user_input['mood']}
Event: {user_input['event']}
Duration: {user_input['duration']} minutes

Selected tracks:

{track_list}

Instructions:

1. Explain why this playlist fits the user's preferences.
2. Suggest a natural listening flow from opening to closing.
3. Do not add or invent tracks.
4. Do not invent BPM, musical key, energy values or audio features.
5. Keep the explanation concise.
"""

    try:

        playlist_note = call_gemini(prompt)

        print("Playlist curation completed.")

    except Exception as error:

        print("Curator fallback:", error)

        state["errors"].append(
            f"Curator error: {error}"
        )

        playlist_note = (
            "Your playlist has been generated using "
            "genre relevance, mood relevance, and "
            "artist diversity. Tracks are selected "
            "from Last.fm discovery results."
        )

    return {
        **state,
        "playlist_note": playlist_note
    }


# ==================================================
# BUILD LANGGRAPH WORKFLOW
# ==================================================

def build_music_graph():

    workflow = StateGraph(MusicState)

    workflow.add_node(
        "planner",
        planner_node
    )

    workflow.add_node(
        "discovery",
        discovery_node
    )

    workflow.add_node(
        "recovery",
        recovery_node
    )

    workflow.add_node(
        "ranking",
        ranking_node
    )

    workflow.add_node(
        "curator",
        curator_node
    )

    workflow.add_edge(
        START,
        "planner"
    )

    workflow.add_edge(
        "planner",
        "discovery"
    )

    workflow.add_conditional_edges(
        "discovery",
        route_after_discovery,
        {
            "recovery": "recovery",
            "ranking": "ranking"
        }
    )

    workflow.add_edge(
        "recovery",
        "ranking"
    )

    workflow.add_edge(
        "ranking",
        "curator"
    )

    workflow.add_edge(
        "curator",
        END
    )

    return workflow.compile()


# ==================================================
# MAIN FUNCTION
# ==================================================

def generate_music_set(user_input):

    print("\n====================================")
    print(" AI-POWERED MUSIC SET GENERATION ")
    print("====================================")

    required_fields = [
        "genre",
        "mood",
        "duration",
        "event"
    ]

    for field in required_fields:

        if field not in user_input:
            raise ValueError(
                f"Missing required input: {field}"
            )

    if not str(user_input["genre"]).strip():
        raise ValueError("Genre cannot be empty")

    if not str(user_input["mood"]).strip():
        raise ValueError("Mood cannot be empty")

    if not str(user_input["event"]).strip():
        raise ValueError("Event cannot be empty")

    if float(user_input["duration"]) <= 0:
        raise ValueError("Duration must be greater than zero")

    initial_state = {
        "user_input": user_input,
        "plan": {},
        "raw_tracks": [],
        "selected_tracks": [],
        "playlist_note": "",
        "errors": []
    }

    music_graph = build_music_graph()

    result = music_graph.invoke(initial_state)

    print("\n========== WORKFLOW COMPLETED ==========")

    print(
        "Total discovered tracks:",
        len(result["raw_tracks"])
    )

    print(
        "Final selected tracks:",
        len(result["selected_tracks"])
    )

    if result["errors"]:

        print("\nWorkflow errors:")

        for error in result["errors"]:
            print("-", error)

    return result["selected_tracks"]


# ==================================================
# DIRECT TEST
# ==================================================

if __name__ == "__main__":

    test_input = {

        "genre": "Bollywood",

        "mood": "Energetic",

        "duration": 60,

        "event": "Wedding",

        "favorite_track": "Kala Chashma",

        "favorite_artist": "Badshah"
    }

    playlist = generate_music_set(test_input)

    print("\n========== FINAL PLAYLIST ==========")

    for index, track in enumerate(
        playlist,
        start=1
    ):

        print(
            f"{index}. {track['name']} — "
            f"{track['artist']} "
            f"(Score: {track['score']}/10)"
        )
