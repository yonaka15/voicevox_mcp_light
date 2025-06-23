"""
voicevox docker版 へのアクセスを提供します

ex.
    from src.voicevox_client import VoicevoxClient
    import io, wave, simpleaudio as sa

    vvc = VoicevoxClient(default_speaker="8")   # speaker id を`8`を利用する
    query = vvc.audio_query(text=message)   # メッセージデータのみを設定し発音内容に変換
    wav_bytes = vvc.synthesis(query=query)  # wav音声データのバイナリデータを取得
    with io.BytesIO(wav_bytes) as wav_io:
        with wave.open(wav_io, 'rb') as wav_read:
            wave_obj = sa.WaveObject.from_wave_read(wav_read)   # 波形データ変換
            play_obj = wave_obj.play()   # 非同期再生
            # play_obj.wait_done()  # 再生中を待つ場合には有効化
"""

import requests
from typing import Optional, Any, Dict, List # Any, Dict, List を追加

HOST = "127.0.0.1"
PORT = "50021"
DEFAULT_SPEAKER = "3" # Changed from "1" to an available speaker ID (Zundamon Normal)

class VoicevoxClient:

    def __init__(self, host: str = HOST, port: str = PORT, default_speaker: str = DEFAULT_SPEAKER):
        self.host: str = host if host else HOST
        self.port: str = port if port else PORT
        self.default_speaker: str = default_speaker if default_speaker else DEFAULT_SPEAKER

    def audio_query(self, text: str, speaker: Optional[str] = None) -> Dict[str, Any]:
        params = {
            "text": text,
            "speaker": speaker if speaker is not None else self.default_speaker,
        }
        response = requests.post(
            f"http://{self.host}:{self.port}/audio_query",
            params=params
        )
        response.raise_for_status()
        return response.json()

    def synthesis(self, query: Dict[str, Any], speaker: Optional[str] = None) -> bytes:
        params = {
            "speaker": speaker if speaker is not None else self.default_speaker,
        }
        response = requests.post(
            f"http://{self.host}:{self.port}/synthesis",
            params=params,
            json=query
        )
        response.raise_for_status()
        return response.content

    def get_speakers(self) -> List[Dict[str, Any]]:
        """利用可能な話者とそのスタイルを取得します"""
        response = requests.get(
            f"http://{self.host}:{self.port}/speakers"
        )
        response.raise_for_status() # エラーチェック
        return response.json()

