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
        
        # あなたの環境で動くことが証明された最新モデルを指定
        model_name = 'models/gemini-3-flash-preview'
        
        try:
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

            start_index = raw_text.find('[')
            end_index = raw_text.rfind(']') + 1
            if start_index == -1:
                start_index = raw_text.find('{')
                end_index = raw_text.rfind('}') + 1
            
            if start_index == -1:
                raise ValueError(f"AIがJSONを返しませんでした。")

            json_text = raw_text[start_index:end_index]
            events = json.loads(json_text)
            
            # リストでなければリストにする
            if not isinstance(events, list):
                events = [events]

            # 【保険ロジック】AIが期間で返してきた場合、Python側で1日単位にバラす
            final_events = []
            for ev in events:
                try:
                    # ISO 8601形式（YYYY-MM-DDTHH:MM）をパース
                    start_dt = datetime.fromisoformat(ev['start'])
                    end_dt = datetime.fromisoformat(ev['end'])
                    
                    # 開始日と終了日が異なる（期間予定）場合
                    if start_dt.date() != end_dt.date():
                        current_date = start_dt.date()
                        while current_date <= end_dt.date():
                            # 各日の予定を作成
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
                        # 1日の予定ならそのまま追加
                        final_events.append(ev)
                except Exception as parse_error:
                    print(f"予定パースエラー（スキップします）: {parse_error}, データ: {ev}")
                    # パースに失敗した場合はそのまま追加（フロント側でエラー表示させるため）
                    final_events.append(ev)

            return final_events

        except Exception as e:
            print("=== GEMINI API ERROR DETAIL ===")
            print(traceback.format_exc())
            raise e