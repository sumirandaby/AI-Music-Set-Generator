import os
import requests
from dotenv import load_dotenv

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

load_dotenv()

API_KEY = os.getenv("LASTFM_API_KEY")
BASE_URL = "https://ws.audioscrobbler.com/2.0/"

REQUEST_TIMEOUT = 15


# --------------------------------------------------
# COMMON API REQUEST FUNCTION
# --------------------------------------------------

def make_api_request(params):
    """
    Send a request to Last.fm API and return JSON data.
    """

    if not API_KEY:
        raise ValueError(
            "LASTFM_API_KEY not found. Check your .env file."
        )

    request_params = {
        **params,
        "api_key": API_KEY,
        "format": "json"
    }

    try:
        response = requests.get(
            BASE_URL,
            params=request_params,
            timeout=REQUEST_TIMEOUT
        )

        response.raise_for_status()

        data = response.json()

        if "error" in data:
            raise ValueError(
                data.get("message", "Last.fm API error")
            )

        return data

    except requests.exceptions.Timeout:
        raise RuntimeError("Last.fm API request timed out.")

    except requests.exceptions.RequestException as error:
        raise RuntimeError(
            f"Last.fm connection error: {error}"
        )


# --------------------------------------------------
# DATA NORMALIZATION
# --------------------------------------------------

def get_artist_name(artist):
    """
    Handle artist names returned as either strings
    or dictionaries by Last.fm.
    """

    if isinstance(artist, dict):
        return artist.get("name", "")

    if isinstance(artist, str):
        return artist

    return ""


def normalize_tags(tags):
    """
    Convert Last.fm tag responses into a consistent
    list of lowercase tag names.
    """

    if isinstance(tags, dict):
        tags = [tags]

    if not isinstance(tags, list):
        return []

    return list(dict.fromkeys(
        tag.get("name", "").strip().lower()
        for tag in tags
        if isinstance(tag, dict) and tag.get("name")
    ))


# --------------------------------------------------
# 1. SEARCH TRACKS
# --------------------------------------------------

def search_music(track_name, artist=None, limit=10):
    """
    Search for tracks by track name and optionally artist.
    """

    params = {
        "method": "track.search",
        "track": track_name,
        "limit": limit
    }

    if artist:
        params["artist"] = artist

    data = make_api_request(params)

    return (
        data.get("results", {})
        .get("trackmatches", {})
        .get("track", [])
    )


# --------------------------------------------------
# 2. GENRE-BASED DISCOVERY
# --------------------------------------------------

def get_tracks_by_genre(genre, limit=20):
    """
    Find popular tracks associated with a Last.fm tag.

    Note: A Last.fm tag represents community-generated
    classification, not verified audio genre.
    """

    params = {
        "method": "tag.getTopTracks",
        "tag": genre,
        "limit": limit
    }

    data = make_api_request(params)

    return (
        data.get("tracks", {})
        .get("track", [])
    )


# --------------------------------------------------
# 3. SIMILAR TRACK DISCOVERY
# --------------------------------------------------

def get_similar_tracks(
    track_name,
    artist,
    limit=20,
    autocorrect=1
):
    """
    Find tracks similar to a given track.

    Last.fm provides a similarity match value.
    The agent can use this value during ranking.
    """

    params = {
        "method": "track.getSimilar",
        "track": track_name,
        "artist": artist,
        "limit": limit,
        "autocorrect": autocorrect
    }

    data = make_api_request(params)

    tracks = (
        data.get("similartracks", {})
        .get("track", [])
    )

    if isinstance(tracks, dict):
        tracks = [tracks]

    return tracks


# --------------------------------------------------
# 4. ARTIST-BASED DISCOVERY
# --------------------------------------------------

def get_tracks_by_artist(artist, limit=20):
    """
    Retrieve popular tracks from a favourite artist.
    """

    params = {
        "method": "artist.getTopTracks",
        "artist": artist,
        "limit": limit
    }

    data = make_api_request(params)

    tracks = (
        data.get("toptracks", {})
        .get("track", [])
    )

    if isinstance(tracks, dict):
        tracks = [tracks]

    return tracks


# --------------------------------------------------
# 5. TRACK TAG RETRIEVAL
# --------------------------------------------------

def get_track_tags(track_name, artist):
    """
    Retrieve community-generated tags for a track.

    Example:
    progressive house, electronic, dance, energetic
    """

    params = {
        "method": "track.getTopTags",
        "track": track_name,
        "artist": artist,
        "autocorrect": 1
    }

    data = make_api_request(params)

    tags = (
        data.get("toptags", {})
        .get("tag", [])
    )

    return normalize_tags(tags)


# --------------------------------------------------
# 6. ARTIST TAG RETRIEVAL
# --------------------------------------------------

def get_artist_tags(artist):
    """
    Retrieve tags associated with an artist.

    These tags can help identify the artist's
    general musical style.
    """

    params = {
        "method": "artist.getTopTags",
        "artist": artist,
        "autocorrect": 1
    }

    data = make_api_request(params)

    tags = (
        data.get("toptags", {})
        .get("tag", [])
    )

    return normalize_tags(tags)


# --------------------------------------------------
# 7. TRACK METADATA
# --------------------------------------------------

def get_track_info(track_name, artist):
    """
    Retrieve detailed information about a track.

    Returns:
    - Track name
    - Artist
    - Album
    - Duration
    - Play count
    - Listeners
    - Tags
    - Last.fm URL
    """

    params = {
        "method": "track.getInfo",
        "track": track_name,
        "artist": artist,
        "autocorrect": 1
    }

    data = make_api_request(params)

    track = data.get("track", {})

    if not track:
        return {}

    album = track.get("album", {})

    if isinstance(album, dict):
        album_name = album.get("title", "")
    else:
        album_name = ""

    tags = (
        track.get("toptags", {})
        .get("tag", [])
    )

    return {
        "name": track.get("name", track_name),
        "artist": get_artist_name(
            track.get("artist", artist)
        ),
        "album": album_name,
        "duration": track.get("duration", 0),
        "listeners": track.get("listeners", 0),
        "playcount": track.get("playcount", 0),
        "tags": normalize_tags(tags),
        "url": track.get("url", "")
    }


# --------------------------------------------------
# 8. MULTIPLE PAGE GENRE DISCOVERY
# --------------------------------------------------

def get_tracks_by_genre_paginated(
    genre,
    pages=2,
    limit=50
):
    """
    Retrieve tracks across multiple pages of a genre tag.

    Useful when the initial popular tracks are not
    sufficient for building a recommendation set.
    """

    all_tracks = []

    for page in range(1, pages + 1):

        params = {
            "method": "tag.getTopTracks",
            "tag": genre,
            "limit": limit,
            "page": page
        }

        data = make_api_request(params)

        tracks = (
            data.get("tracks", {})
            .get("track", [])
        )

        if isinstance(tracks, dict):
            tracks = [tracks]

        if not tracks:
            break

        all_tracks.extend(tracks)

    return all_tracks


# --------------------------------------------------
# TESTING
# --------------------------------------------------

if __name__ == "__main__":

    print("\n--- ARTIST DISCOVERY ---")

    try:
        tracks = get_tracks_by_artist("Martin Garrix")

        for track in tracks[:5]:
            print(
                track.get("name"),
                "-",
                get_artist_name(track.get("artist"))
            )

        print("\n--- SIMILAR TRACKS ---")

        similar = get_similar_tracks(
            "Animals",
            "Martin Garrix"
        )

        for track in similar[:5]:
            print(
                track.get("name"),
                "-",
                get_artist_name(track.get("artist")),
                "- Similarity:",
                track.get("match")
            )

        print("\n--- TRACK TAGS ---")

        tags = get_track_tags(
            "Animals",
            "Martin Garrix"
        )

        print(tags if tags else "No track tags available.")

        print("\n--- ARTIST TAGS ---")

        artist_tags = get_artist_tags("Martin Garrix")

        print(
            artist_tags
            if artist_tags
            else "No artist tags available."
        )

        print("\n--- TRACK INFORMATION ---")

        info = get_track_info(
            "Animals",
            "Martin Garrix"
        )

        print(info)

    except Exception as error:
        print("Test failed:", error)
