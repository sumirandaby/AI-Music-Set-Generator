import streamlit as st
import csv
import io
from urllib.parse import quote
from agent import generate_music_set


# 1. PAGE CONFIGURATION

st.set_page_config(
    page_title="AI Music Set Generator",
    page_icon="🎧",
    layout="wide"
)


# Preserve playlist across Streamlit reruns
if "generated_tracks" not in st.session_state:
    st.session_state.generated_tracks = None


# 2. APPLICATION HEADER
st.title("🎧 AI-Powered Music Set Generator")

st.caption(
    "Create personalized DJ music sets using "
    "Gemini AI, LangGraph and Last.fm."
)

st.divider()


# 3. USER INPUTS
st.header("Configure Your Music Set")
col1, col2 = st.columns(2)


# -------------------- COLUMN 1 --------------------

with col1:

    selected_genre = st.selectbox(
        "Music Genre",
        [
            "Future House",
            "Progressive House",
            "Big Room House",
            "Deep House",
            "Tech House",
            "Melodic House",
            "Techno",
            "Trance",
            "Progressive Trance",
            "Psytrance",
            "EDM",
            "Dubstep",
            "Drum and Bass",
            "Pop",
            "Hip-Hop",
            "Other"
        ]
    )

    if selected_genre == "Other":
        genre = st.text_input(
            "Enter Your Music Genre",
            placeholder="e.g. Afro House"
        )
    else:
        genre = selected_genre

    selected_mood = st.selectbox(
        "Mood",
        [
            "Energetic",
            "Chill",
            "Emotional",
            "Dark",
            "Uplifting",
            "Romantic",
            "Melancholic",
            "Dreamy",
            "Aggressive",
            "Other"
        ]
    )

    if selected_mood == "Other":
        mood = st.text_input(
            "Enter Your Mood",
            placeholder="e.g. Nostalgic"
        )
    else:
        mood = selected_mood

    duration = st.number_input(
        "Set Duration (minutes)",
        min_value=10,
        max_value=300,
        value=60,
        step=5
    )


# -------------------- COLUMN 2 --------------------

with col2:

    selected_event = st.selectbox(
        "Event",
        [
            "Music Festival",
            "Club Night",
            "House Party",
            "Road Trip",
            "Workout",
            "Personal Listening",
            "Wedding",
            "College Fest",
            "Pool Party",
            "Other"
        ]
    )

    if selected_event == "Other":
        event = st.text_input(
            "Enter Your Event",
            placeholder="e.g. Sunset Beach Party"
        )
    else:
        event = selected_event

    favorite_track = st.text_input(
        "Favorite Track (optional)",
        placeholder="e.g. Animals"
    )

    favorite_artist = st.text_input(
        "Favorite Artist (optional)",
        placeholder="e.g. Martin Garrix"
    )


st.divider()


# 4. GENERATE MUSIC SET
if st.button(
    "🎵 Generate Music Set",
    type="primary",
    use_container_width=True
):

    if not genre.strip():
        st.warning("Please enter a music genre.")

    elif not mood.strip():
        st.warning("Please enter a mood.")

    elif not event.strip():
        st.warning("Please enter an event.")

    else:

        user_input = {
            "genre": genre.strip(),
            "mood": mood.strip(),
            "duration": duration,
            "event": event.strip(),
            "favorite_track": favorite_track.strip(),
            "favorite_artist": favorite_artist.strip()
        }

        try:

            with st.spinner(
                "AI agents are planning and generating your music set..."
            ):

                tracks = generate_music_set(user_input)

            st.session_state.generated_tracks = tracks

        except Exception as error:

            st.session_state.generated_tracks = None

            st.error(f"Something went wrong: {error}")

            st.info(
                "Check your API configuration and terminal logs."
            )


# 5. DISPLAY GENERATED PLAYLIST
tracks = st.session_state.generated_tracks

if tracks is not None:

    if not tracks:

        st.warning(
            "No tracks found. Try different music preferences."
        )

    else:

        st.success(
            f"Your music set is ready! "
            f"{len(tracks)} tracks selected."
        )

        st.header("🎧 Your Generated Playlist")

        # Divide playlist into four sections

        total = len(tracks)

        opening_end = max(1, round(total * 0.20))
        buildup_end = max(opening_end, round(total * 0.50))
        peak_end = max(buildup_end, round(total * 0.85))

        sections = [
            ("🌅 Opening", tracks[:opening_end]),
            ("📈 Build-up", tracks[opening_end:buildup_end]),
            ("🔥 Peak Time", tracks[buildup_end:peak_end]),
            ("🌙 Closing", tracks[peak_end:])
        ]

        track_number = 1

        for section_name, section_tracks in sections:

            if not section_tracks:
                continue

            st.subheader(section_name)

            for track in section_tracks:

                name = track.get("name", "Unknown Track")
                artist = track.get("artist", "Unknown Artist")
                score = track.get("score")

                # Generate Spotify search link
                search_query = quote(f"{name} {artist}")
                spotify_url = (
                    f"https://open.spotify.com/search/{search_query}"
                )

                with st.container(border=True):

                    col1, col2 = st.columns([5, 1])

                    with col1:

                        st.markdown(
                            f"**{track_number}. {name}**"
                        )

                        st.write(f"🎤 {artist}")

                        st.markdown(
                            f"[🎧 Listen on Spotify]({spotify_url})"
                        )

                    with col2:

                        if score is not None:
                            st.metric("Score", score)

                track_number += 1


        # ------------------------------------------
        # Download playlist as CSV
        # ------------------------------------------

        csv_buffer = io.StringIO()

        writer = csv.DictWriter(
            csv_buffer,
            fieldnames=[
                "Track",
                "Artist",
                "Score",
                "Spotify URL"
            ]
        )

        writer.writeheader()

        for track in tracks:

            name = track.get("name", "")
            artist = track.get("artist", "")

            search_query = quote(f"{name} {artist}")
            spotify_url = (
                f"https://open.spotify.com/search/{search_query}"
            )

            writer.writerow({
                "Track": name,
                "Artist": artist,
                "Score": track.get("score", ""),
                "Spotify URL": spotify_url
            })

        st.divider()

        st.download_button(
            label="⬇️ Download Playlist (CSV)",
            data=csv_buffer.getvalue(),
            file_name="my_music_set.csv",
            mime="text/csv",
            use_container_width=True
        )

# 6. FOOTER
st.divider()

st.caption(
    "Powered by Gemini AI • LangGraph • Last.fm • Streamlit"
)
