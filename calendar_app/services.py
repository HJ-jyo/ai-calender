import google.generativeai as genai
import json
import os
import traceback
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

class GeminiService:
    @staticmethod
    def analyze_schedule(file_data, content_type):
        print("\n" + "="*50)
        print("[DEBUG-PROBE] Gemini 解析スタート！")
        print(f"[DEBUG-PROBE] 受け取ったファイル: MIME={content_type}, サイズ={len(file_data)} bytes")
        
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            print("[DEBUG-PROBE] ❌ エラー: GEMINI_API_KEY がありません！")
            raise ValueError("API KEY MISSING")

        genai.configure(api_key=api_key)
        model_name = 'gemini-1.5-flash'
        
        try:
            model = genai.GenerativeModel(model_name)
            
            prompt = """
            画像から全ての予定を抽出し、以下のJSON配列形式のみで出力してください。
            [{"title": "予定", "start": "2026-03-24T09:00:00", "end": "2026-03-24T18:00:00", "location": "", "description": ""}]
            ※期間予定は1日ずつ分割すること。余計な文字（```jsonなど）は一切不要。
            """
            
            print(f"[DEBUG-PROBE] モデル({model_name}) にリクエストを送信中...")
            response = model.generate_content([prompt, {'mime_type': content_type, 'data': file_data}])
            
            print("[DEBUG-PROBE] ✅ Geminiから応答を受信！")
            
            # 安全フィルター（セーフティ）に引っかかったか確認
            if response.prompt_feedback:
                print(f"[DEBUG-PROBE] ⚠️ セーフティフィードバック: {response.prompt_feedback}")
            
            try:
                raw_text = response.text
                print(f"\n--- [DEBUG-PROBE: AI 生データ (RAW TEXT) ここから] ---\n{raw_text}\n--- [DEBUG-PROBE: ここまで] ---\n")
            except ValueError as ve:
                print(f"[DEBUG-PROBE] ❌ エラー: AIのテキストを取得不可（ブロックされた可能性）。詳細: {ve}")
                if response.candidate:
                    print(f"[DEBUG-PROBE] Candidate info: {response.candidate}")
                return []

            # どんなに汚いマークダウンで返してきても強制的に剥がすパーサー
            clean_text = raw_text.strip()
            if clean_text.startswith('
http://googleusercontent.com/immersive_entry_chip/0
http://googleusercontent.com/immersive_entry_chip/1
http://googleusercontent.com/immersive_entry_chip/2

3. その状態で、スマホかPCから**アプリにアクセスし、画像を1枚アップロード**してください。

4. ターミナルに `[DEBUG-PROBE]` や `[DEBUG-VIEW]` から始まる文字がダーッと流れるはずです。
