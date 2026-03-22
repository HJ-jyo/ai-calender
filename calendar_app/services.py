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
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY が .env ファイルに見つかりません。")

        # ライブラリの初期化
        genai.configure(api_key=api_key)
        
        # 余計な検索ロジックを排除し、標準的なモデルを直接指定
        model_name = 'gemini-1.5-flash'
        
        try:
            model = genai.GenerativeModel(model_name)
            
            # 相棒が求めていた柔軟で強力なプロンプト
            prompt = """
            提供された画像（シフト表、行事予定表、カレンダーなど）から全ての予定を抽出し、以下のJSON形式のリストで出力してください。
            
            【重要ルール】
            1. 「○日〜○日」のような期間予定が含まれている場合でも、必ず **1日単位に分割（バラして）** 出力してください。
               （例：24日〜26日の予定は、24日、25日、26日の3つの独立したデータにする）
            2. 時間の記載がない予定（終日予定など）は、開始を "09:00:00"、終了を "10:00:00" に設定してください。
            3. 年の記載がない場合は、現在の年である「2026年」として処理してください。
            4. 出力は純粋なJSONデータのみとし、Markdown表記（```json など）や説明文は一切含めないでください。
            
            【出力形式】
            [
                {
                    "title": "予定の名称",
                    "start": "2026-03-24T09:00:00",
                    "end": "2026-03-24T18:00:00",
                    "location": "場所（不明な場合は空文字）",
                    "description": "備考や詳細（不明な場合は空文字）"
                }
            ]
            """

            # シンプルにAIへリクエスト（自動切り替えや強制オプションなどのギミックなし）
            response = model.generate_content([
                prompt,
                {'mime_type': content_type, 'data': file_data}
            ])

            raw_text = response.text.strip()
            print(f"DEBUG AI Response: {raw_text}")

            # JSON部分だけを安全に抽出するロジック
            if raw_text.startswith('```json'):
                raw_text = raw_text[7:]
            if raw_text.startswith('```'):
                raw_text = raw_text[3:]
            if raw_text.endswith('```'):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()

            events = json.loads(raw_text)
            
            if not isinstance(events, list):
                events = [events]

            # 期間予定を1日ずつに分解する保険ロジック
            final_events = []
            for ev in events:
                try:
                    start_dt = datetime.fromisoformat(ev['start'])
                    end_dt = datetime.fromisoformat(ev['end'])
                    
                    if start_dt.date() < end_dt.date():
                        curr = start_dt.date()
                        while curr <= end_dt.date():
                            new_start = datetime.combine(curr, start_dt.time())
                            new_end = datetime.combine(curr, end_dt.time())
                            
                            final_events.append({
                                "title": ev['title'],
                                "start": new_start.isoformat(),
                                "end": new_end.isoformat(),
                                "location": ev.get('location', ''),
                                "description": ev.get('description', '')
                            })
                            curr += timedelta(days=1)
                    else:
                        final_events.append(ev)
                except Exception as parse_error:
                    print(f"日付パースエラー: {parse_error}")
                    final_events.append(ev)

            return final_events

        except Exception as e:
            print("=== GEMINI API ERROR DETAIL ===")
            print(traceback.format_exc())
            raise e