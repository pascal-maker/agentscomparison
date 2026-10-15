"""Optional Petra voice for public Karen answers in the non-commercial POC."""

from pathlib import Path


SPACE = "huyghebaertthomas/babbeldoos-demo"
MAX_SPEECH_CHARS = 1000
MAX_AUDIO_BYTES = 8 * 1024 * 1024


def synthesize_petra(text: str) -> bytes:
    """Ask the public Babbeldoos demo to read one already-public answer."""
    if not text or len(text) > MAX_SPEECH_CHARS:
        raise ValueError("Petra speech text must contain 1–1000 characters")

    from gradio_client import Client

    client = Client(SPACE, verbose=False)
    result = client.submit(
        text, "Petra (aanbevolen)", None, "Narration", 1.0, -1,
        api_name="/speak",
    ).result(timeout=60)
    audio = result[0]
    path = Path(audio["path"] if isinstance(audio, dict) else audio)
    if not path.is_file() or path.stat().st_size > MAX_AUDIO_BYTES:
        raise ValueError("Babbeldoos returned no usable audio")
    data = path.read_bytes()
    if not data.startswith(b"RIFF") or data[8:12] != b"WAVE":
        raise ValueError("Babbeldoos returned an invalid WAV file")
    return data
