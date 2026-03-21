import google.generativeai as genai
from django.conf import settings
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

        genai.configure(api_key=api_key)
        
        # 安定性と速度に優れた最新モデル
        model_name = 'gemini-1.5-flash'
        
        try:
            model = genai.GenerativeModel(model_name)
            
            # AIへの絶対的な指示書（プロンプト）
            prompt = """
            あなたは優秀なスケジュール解析アシスタントです。
            提供された画像（シフト表、行事予定表、カレンダーなど）から全ての予定を抽出し、以下のJSON配列形式で出力してください。
            
            【絶対ルール】
            1. 「○日〜○日」のような期間予定が含まれている場合でも、必ず **1日単位に分割（バラして）** 出力してください。（例：24日〜26日の予定は、24日、25日、26日の3つの独立したデータにする）
            2. 年の記載がない場合は、現在の年である「2026年」として処理してください。
            3. 時間の記載がない予定（終日予定など）は、開始を "09:00:00"、終了を "10:00:00" に設定してください。
            4. 出力は純粋なJSONデータのみとし、Markdown表記（```json など）や説明文は一切含めないでください。
            
            【JSONデータ構造の例】
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

            # JSON形式での出力をAIに強制する（これが空データを防ぐ最大の鍵）
            response = model.generate_content(
                [prompt, {'mime_type': content_type, 'data': file_data}],
                generation_config={"response_mime_type": "application/json"}
            )

            raw_text = response.text.strip()
            print(f"\n--- [DEBUG: AI Raw Output] ---\n{raw_text}\n------------------------------\n")

            # AIの返答をPythonのリストに変換
            events = json.loads(raw_text)
            
            if not isinstance(events, list):
                events = [events]

            final_events = []
            
            # 【保険ロジック】AIがルールを無視して期間で返してきた場合、Python側で強制的に1日単位にバラす
            for ev in events:
                try:
                    start_dt = datetime.fromisoformat(ev['start'])
                    end_dt = datetime.fromisoformat(ev['end'])
                    
                    if start_dt.date() < end_dt.date():
                        current_date = start_dt.date()
                        while current_date <= end_dt.date():
                            new_start = datetime.combine(current_date, start_dt.time())
                            new_end = datetime.combine(current_date, end_dt.time())
                            
                            final_events.append({
                                "title": ev['title'],
                                "start": new_start.isoformat(),
                                "end": new_end.isoformat(),
                                "location": ev.get('location', ''),
                                "description": ev.get('description', '')
                            })
                            current_date += timedelta(days=1)
                    else:
                        final_events.append(ev)
                except Exception as parse_error:
                    print(f"日付パースエラー（スキップせずそのまま追加します）: {parse_error}")
                    final_events.append(ev)

            return final_events

        except Exception as e:
            print("\n=== GEMINI API ERROR DETAIL ===")
            print(traceback.format_exc())
            print("===============================\n")
            raise e