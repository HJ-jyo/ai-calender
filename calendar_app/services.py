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
        print(f"[DEBUG-PROBE] MIME={content_type}")
        
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            print("[DEBUG-PROBE] ❌ エラー: GEMINI_API_KEY がありません！")
            raise ValueError("API KEY MISSING")

        # 警告が出る旧SDK(google.generativeai)でも動くように設定
        genai.configure(api_key=api_key)
        
        # 【重要】2026年3月現在の最新・無料・高速安定モデル
        model_name = 'gemini-2.0-flash'
        
        try:
            model = genai.GenerativeModel(model_name)
            
            prompt = """
            画像から全ての予定を抽出し、以下のJSON配列形式のみで出力してください。
            [{"title": "予定", "start": "2026-03-24T09:00:00", "end": "2026-03-24T18:00:00", "location": "", "description": ""}]
            ※期間予定は1日ずつ分割すること。余計な文字は一切不要。
            """
            
            # JSON出力を強制するコンフィグを追加（これがないと挨拶などが混ざる場合があります）
            response = model.generate_content(
                [prompt, {'mime_type': content_type, 'data': file_data}],
                generation_config={"response_mime_type": "application/json"}
            )
            print(f"[DEBUG-PROBE] ✅ Gemini({model_name})から応答を受信！")
            
            try:
                raw_text = response.text
                print(f"\n--- [DEBUG-PROBE: AI 生データ (RAW TEXT)] ---\n{raw_text}\n--------------------------------------------\n")
            except ValueError as ve:
                print(f"[DEBUG-PROBE] ❌ AIテキスト取得エラー: {ve}")
                return []

            clean_text = raw_text.strip()
            clean_text = clean_text.replace("```json", "")
            clean_text = clean_text.replace("```", "")
            clean_text = clean_text.strip()
            
            try:
                events = json.loads(clean_text)
                print(f"[DEBUG-PROBE] ✅ JSONパース成功！ {len(events)} 件検出。")
            except json.JSONDecodeError as e:
                print(f"[DEBUG-PROBE] ❌ JSONパース失敗！: {e}")
                return []

            if not isinstance(events, list):
                events = [events]

            final_events = []
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
                    print(f"[DEBUG-PROBE] 日付パースエラー: {parse_error}")
                    final_events.append(ev)

            print(f"[DEBUG-PROBE] 解析完了。{len(final_events)} 件を返します。")
            print("="*50 + "\n")
            return final_events

        except Exception as e:
            print("\n" + "="*50)
            print("[DEBUG-PROBE] ❌ 致命的なエラー発生！")
            print(traceback.format_exc())
            print("="*50 + "\n")
            return []