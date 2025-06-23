"""
MCPサーバークラスを提供します。

このモジュールは、Model Context Protocol (MCP)に準拠したサーバーを実装し、
voicevoxエンジンを利用して音声合成と再生を行う機能を提供します。
"""

import asyncio
import logging
import os
import wave
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, Optional, List, Union # Union を追加
import wave, simpleaudio as sa
import base64 # base64 を追加

import sounddevice as sd
from mcp.server import Server
from mcp import types # types を直接 import

from src.voicevox_client import VoicevoxClient


class MCPServer(Server):
    """
    MCPサーバークラス。
    
    Model Context Protocol (MCP)に準拠したサーバーを実装し、
    voicevoxエンジンを利用して音声合成と再生を行う機能を提供します。
    
    Attributes:
        voicevox_client: VoicevoxClientのインスタンス
        logger: ロギングのためのロガーインスタンス
    """

    def __init__(
        self,
        name: str = "voicevox-mcp-light",
        host: Optional[str] = None,
        port: Optional[str] = None,
        default_speaker: Optional[str] = None, # speaker を default_speaker に変更
    ):
        """
        MCPServerクラスの初期化メソッド。
        
        Args:
            name: サーバー名
            host: voicevoxエンジンのホスト名
            port: voicevoxエンジンのポート番号
            default_speaker: デフォルトの話者ID
        """
        super().__init__(name)
        
        # VoicevoxClientの初期化
        self.voicevox_client = VoicevoxClient(host=host, port=port, default_speaker=default_speaker) # speaker を default_speaker に変更
        
        # ロガーの設定
        self.logger = self._setup_logger()
        
        # ツールの登録
        self._register_tools()
        
        self.logger.info("MCPServer initialized")

    def _setup_logger(self) -> logging.Logger:
        """
        ロガーを設定します。
        
        Returns:
            設定されたロガーインスタンス
        """
        # ログディレクトリの作成
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "log")
        os.makedirs(log_dir, exist_ok=True)
        
        # ロガーの設定
        logger = logging.getLogger("mcp_server")
        logger.setLevel(logging.DEBUG)  # DEBUG レベルに変更
        
        # ファイルハンドラの設定
        log_file = os.path.join(log_dir, f"mcp_server_{datetime.now().strftime('%Y%m%d')}.log")
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)  # DEBUG レベルに変更
        
        # フォーマッタの設定
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        
        # ハンドラの追加
        logger.addHandler(file_handler)
        
        return logger

    def get_capabilities(self, notification_options=None, experimental_capabilities=None):
        """
        サーバーの機能を取得します。
        
        Args:
            notification_options: 通知オプション
            experimental_capabilities: 実験的な機能
            
        Returns:
            サーバーの機能を表す辞書
        """
        from mcp.server.lowlevel import NotificationOptions # types を直接 import するため修正
        
        if notification_options is None:
            notification_options = NotificationOptions()
            
        if experimental_capabilities is None:
            experimental_capabilities = {}
            
        return {
            "tools": {
                "listChanged": False
            },
            "resources": {
                "listChanged": False,
                "subscribe": False
            },
            "notifications": notification_options.to_dict(),
            "experimental": experimental_capabilities
        }
        
    def _register_tools(self) -> None:
        """
        MCPサーバーにツールを登録します。
        """
        # ツール一覧を提供するハンドラを登録
        @self.list_tools()
        async def handle_list_tools():
            """利用可能なツールの一覧を返します。"""
            # types を直接 import するため修正
            return [
                types.Tool(
                    name="synthesizeAndPlay",
                    description="テキストを音声合成して再生します",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "message": {"type": "string", "description": "音声合成するテキスト"},
                            "speaker": {"type": "string", "description": "（オプショナル）話者ID"}
                        },
                        "required": ["message"]
                    }
                ),
                types.Tool(
                    name="speakers",
                    description="利用可能な話者の一覧を取得します",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                ),
                types.Tool(
                    name="audio_query",
                    description="テキストから音声合成用のクエリを生成します",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "クエリを生成するテキスト"},
                            "speaker": {"type": "string", "description": "（オプショナル）話者ID"}
                        },
                        "required": ["text"]
                    }
                ),
                types.Tool(
                    name="synthesizeFromQueryAndPlay",
                    description="音声クエリからWAVデータを生成して再生します",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "object", "description": "音声合成用クエリ"},
                            "speaker": {"type": "string", "description": "（オプショナル）話者ID"}
                        },
                        "required": ["query"]
                    }
                ),
            ]
        
        @self.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[Union[types.TextContent, types.ImageContent, types.EmbeddedResource]]: # 戻り値の型ヒントを修正
            """
            指定されたツールを実行します。
            """
            self.logger.info(f"Tool called: {name} with arguments: {arguments}")
            self.logger.debug(f"Entering handle_call_tool: {name}")  # DEBUGログ追加
            try:
                if name == "synthesizeAndPlay":
                    message = arguments.get("message", "")
                    speaker = arguments.get("speaker") 
                    if not message:
                        self.logger.warning("Empty message received for synthesizeAndPlay")
                        return [types.TextContent(type="text", text="Message is empty")]
                    await self.synthesize_and_play(message, speaker)
                    return [types.TextContent(type="text", text="音声合成と再生が完了しました")]

                elif name == "audio_query":
                    text = arguments.get("text", "")
                    speaker = arguments.get("speaker")
                    if not text:
                        self.logger.warning("Empty text received for audio_query")
                        return [types.TextContent(type="text", text="Text is empty")]
                    query_result = self.voicevox_client.audio_query(text=text, speaker=speaker)
                    # MCPでは通常、JSONシリアライズ可能な形式で返す
                    import json
                    return [types.TextContent(type="text", text=json.dumps(query_result, ensure_ascii=False, indent=2))]

                elif name == "synthesizeFromQueryAndPlay":
                    query = arguments.get("query")
                    speaker = arguments.get("speaker")
                    if not query:
                        self.logger.warning("No query provided for synthesizeFromQueryAndPlay")
                        return [types.TextContent(type="text", text="Query is not provided")]
                    
                    # queryが文字列で渡された場合、辞書に変換
                    if isinstance(query, str):
                        import json
                        try:
                            query = json.loads(query)
                        except json.JSONDecodeError:
                            self.logger.error("Invalid JSON format for query in synthesizeFromQueryAndPlay")
                            return [types.TextContent(type="text", text="Invalid JSON format for query")]

                    # WAVデータ生成
                    wav_bytes = self.voicevox_client.synthesis(query=query, speaker=speaker)
                    
                    # 音声再生
                    await self._play_audio(wav_bytes)
                    
                    return [types.TextContent(type="text", text="音声クエリからの合成と再生が完了しました")]

                elif name == "speakers":
                    speakers_list = self.voicevox_client.get_speakers()
                    # MCPでは通常、JSONシリアライズ可能な形式で返す
                    # スキーマに合わせてobject形式で返す
                    import json
                    result = {"speakers": speakers_list}
                    return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

                else:
                    self.logger.warning(f"Unknown tool: {name}")
                    return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

            except Exception as e:
                self.logger.error(f"Error in tool {name}: {str(e)}", exc_info=True) # exc_info=True を追加してスタックトレースをログに出力
                return [types.TextContent(type="text", text=f"Error processing tool {name}: {str(e)}")]


    async def synthesize_and_play(self, message: str, speaker: Optional[str] = None) -> None: # speaker引数を追加
        """
        テキストを音声合成して再生します。
        
        Args:
            message: 音声合成するテキスト
            speaker: (オプショナル) 話者ID
        """
        self.logger.info(f"Synthesizing message: '{message}' with speaker: {speaker if speaker else 'default'}")
        
        # テキストの前処理
        processed_message = self._preprocess_text(message)
        
        # Audio Queryの取得
        query = self.voicevox_client.audio_query(text=processed_message, speaker=speaker) # speaker引数を渡す
        
        # 音声合成
        wav_bytes = self.voicevox_client.synthesis(query=query, speaker=speaker) # speaker引数を渡す
        
        # 音声再生
        await self._play_audio(wav_bytes)
        
        self.logger.info("Audio playback completed")

    def _preprocess_text(self, text: str) -> str:
        """
        テキストを前処理します。
        
        改行がある場合、各行の末尾に「。」を追加します。
        
        Args:
            text: 前処理するテキスト
            
        Returns:
            前処理されたテキスト
        """
        lines = text.split('\n')
        processed_lines = []
        
        for line in lines:
            line = line.strip()
            if line:
                if not line.endswith('。') and not line.endswith('！') and not line.endswith('?'): # 句読点の種類を増やす
                    line += '。'
                processed_lines.append(line)
        
        return '\n'.join(processed_lines)

    async def _play_audio(self, wav_bytes: bytes) -> None:
        """
        WAVデータを再生します。
        
        Args:
            wav_bytes: 再生するWAVデータのバイト列
        """
        try: # simpleaudio の再生エラーをキャッチ
            with BytesIO(wav_bytes) as wav_io:
                with wave.open(wav_io, 'rb') as wav_read:
                    wave_obj = sa.WaveObject.from_wave_read(wav_read)
                    play_obj = wave_obj.play()   # 非同期再生
                    play_obj.wait_done()
        except Exception as e:
            self.logger.error(f"Error playing audio: {str(e)}", exc_info=True)
            # ここでエラーを再raiseするか、あるいは TextContent でエラーを返すかは設計次第
            # synthesize_and_play を呼び出す call_tool 側でエラーハンドリングしているので、ここではログ出力に留める
            raise # 再度raiseして上位のエラーハンドリングに任せる
