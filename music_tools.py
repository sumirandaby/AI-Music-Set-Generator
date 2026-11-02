import os
import requests
from dotenv import load_dotenv

# Load API key from .env
load_dotenv()

API_KEY = os.getenv("LASTFM_API_KEY")
BASE_URL = "https://ws.audioscrobbler.com/2.0/"


def make_api_request(params):
    """Send a request to Last.fm and return JSON data."""

    if not API_KEY:
        raise ValueError(
            "LASTFM_API_KEY not found. Check your .env file."
        )

    params.update({
        "api_key": API_KEY,
        "format": "json"
    })

    response = requests.get(
        BASE_URL,
        params=params,
        timeout=15
    )

    response.raise_for_status()
    data = response.json()

    if "error" in data:
        raise ValueError(
            data.get("message", "Last.fm API error")
        )

    return data


def search_music(track_name, artist=None):
    """Search for music by track name and optionally artist."""

    params = {
        "method": "track.search",
        "track": track_name,
        "limit": 5
    }

    if artist:
        params["artist"] = artist

    data = make_api_request(params)

    return data.get(
        "results", {}
    ).get(
        "trackmatches", {}
    ).get(
        "track", []
    )


def get_similar_tracks(track_name, artist):
    """Find tracks similar to a given track."""

    params = {
        "method": "track.getSimilar",
        "track": track_name,
        "artist": artist,
        "limit": 10
    }

    data = make_api_request(params)

    return data.get(
        "similartracks", {}
    ).get(
        "track", []
    )


def get_tracks_by_genre(genre):
    """Find popular tracks associated with a genre."""

    params = {
        "method": "tag.getTopTracks",
        "tag": genre,
        "limit": 10
    }

    data = make_api_request(params)

    return data.get(
        "tracks", {}
    ).get(
        "track", []
    )


# Test the functions when this file is run directly
if __name__ == "__main__":

    print("\n--- TRACK SEARCH ---")

    results = search_music("Animals", "Martin Garrix")

    for track in results:
        print("Track:", track["name"])
        print("Artist:", track["artist"])
        print("URL:", track["url"])
        print("-" * 40)

    print("\n--- SIMILAR TRACKS ---")

    results = get_similar_tracks("Animals", "Martin Garrix")

    for track in results:
        print("Track:", track["name"])
        print("Artist:", track["artist"]["name"])
        print("Match:", track.get("match"))
        print("URL:", track["url"])
        print("-" * 40)

    print("\n--- GENRE-BASED TRACKS ---")

    results = get_tracks_by_genre("progressive house")

    for track in results:
        print("Track:", track["name"])
        print("Artist:", track["artist"]["name"])
        print("Listeners:", track.get("listeners"))
        print("URL:", track["url"])
        print("-" * 40)
