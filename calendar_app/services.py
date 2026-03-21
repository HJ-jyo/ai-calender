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
        
        try:
            # 🔥 修正箇所：確実に存在する無料モデル（flash）を自動で探してセットする
            # これにより「存在しないモデル」を探して30秒タイムアウトする現象を完全に防ぎます
            available_models = [
                m.name for m in genai.list_models() 
                if 'generateContent' in m.supported_generation_methods and 'flash' in m.name
            ]
            
            # 見つかったモデルを使う（なければ標準のフォールバック）
            model_name = available_models[0] if available_models else 'models/gemini-1.5-flash-latest'
            print(f"DEBUG: 自動選択されたAIモデル -> {model_name}")
            
            model = genai.GenerativeModel(model_name)
            
            prompt = """
            画像から全ての予定（授業、行事、期間予定）を抽出し、以下のJSON形式のリストで返してください。
            
            【重要ルール】
            1. 連日の予定（例：24〜28日）であっても、必ず **1日単位に切り分けて（バラして）** 出力してください。
               （例：24日、25日、26日... と別々のオブジェクトにする）
            2. 縦軸の時間と横軸の日付（月・日・曜日）を正確に組み合わせてください。
            3. 現在は 2026年3月21日 です。画像内の日付には 2026年 を補完してください。
            
            【出力形式】
            [
                {
                    "title": "予定の名称",
                    "start": "2026-03-24T09:00",
                    "end": "2026-03-24T18:00",
                    "location": "",
                    "description": ""
                }
            ]
            JSON以外の余計なテキストは一切含めないでください。秒数は不要です。
            """

            response = model.generate_content([
                prompt,
                {'mime_type': content_type, 'data': file_data}
            ])

            raw_text = response.text
            print(f"DEBUG AI Response: {raw_text}")

            # --- 相棒の最強オリジナル抽出ロジック（ここからは一切触っていません） ---
            start_index = raw_text.find('[')
            end_index = raw_text.rfind(']') + 1
            if start_index == -1:
                start_index = raw_text.find('{')
                end_index = raw_text.rfind('}') + 1
            
            if start_index == -1:
                raise ValueError(f"AIがJSONを返しませんでした。")

            json_text = raw_text[start_index:end_index]
            events = json.loads(json_text)
            
            if not isinstance(events, list):
                events = [events]

            final_events = []
            for ev in events:
                try:
                    start_dt = datetime.fromisoformat(ev['start'])
                    end_dt = datetime.fromisoformat(ev['end'])
                    
                    if start_dt.date() != end_dt.date():
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
                    print(f"予定パースエラー: {parse_error}, データ: {ev}")
                    final_events.append(ev)

            return final_events

        except Exception as e:
            print("=== GEMINI API ERROR DETAIL ===")
            print(traceback.format_exc())
            raise e