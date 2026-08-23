import unittest

from app.voice.stt import OpenAISpeechToText
from app.voice.tts import OpenAITextToSpeech


class _FakeTranscription:
    def __init__(self, text):
        self.text = text


class _FakeTranscriptions:
    def __init__(self, text):
        self.text = text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeTranscription(self.text)


class _FakeAudioSTT:
    def __init__(self, text):
        self.transcriptions = _FakeTranscriptions(text)


class _FakeSTTClient:
    def __init__(self, text="Plant maize after the rains begin."):
        self.audio = _FakeAudioSTT(text)


class _FakeSpeech:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self


class _FakeAudioTTS:
    def __init__(self, content):
        self.speech = _FakeSpeech(content)


class _FakeTTSClient:
    def __init__(self, content=b"fake-mp3-bytes"):
        self.audio = _FakeAudioTTS(content)


class SpeechToTextTests(unittest.TestCase):
    def test_transcribe_returns_stripped_text(self):
        client = _FakeSTTClient(text="  Plant maize after the rains begin.  ")
        service = OpenAISpeechToText(client=client, model="whisper-1")
        result = service.transcribe(b"fake-audio-bytes", filename="clip.wav")
        self.assertEqual(result, "Plant maize after the rains begin.")
        self.assertEqual(client.audio.transcriptions.calls[0]["model"], "whisper-1")

    def test_transcribe_rejects_empty_audio(self):
        service = OpenAISpeechToText(client=_FakeSTTClient())
        with self.assertRaises(ValueError):
            service.transcribe(b"")

    def test_transcribe_rejects_blank_transcription(self):
        service = OpenAISpeechToText(client=_FakeSTTClient(text="   "))
        with self.assertRaises(ValueError):
            service.transcribe(b"fake-audio-bytes")


class TextToSpeechTests(unittest.TestCase):
    def test_synthesize_returns_audio_bytes(self):
        client = _FakeTTSClient(content=b"mp3-bytes")
        service = OpenAITextToSpeech(client=client, model="gpt-4o-mini-tts", voice="alloy")
        audio = service.synthesize("Plant maize after the rains begin.")
        self.assertEqual(audio, b"mp3-bytes")
        call = client.audio.speech.calls[0]
        self.assertEqual(call["model"], "gpt-4o-mini-tts")
        self.assertEqual(call["voice"], "alloy")
        self.assertEqual(call["input"], "Plant maize after the rains begin.")

    def test_synthesize_rejects_empty_text(self):
        service = OpenAITextToSpeech(client=_FakeTTSClient())
        with self.assertRaises(ValueError):
            service.synthesize("   ")


if __name__ == "__main__":
    unittest.main()
