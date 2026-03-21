import json
import os
import traceback
from datetime import datetime, timedelta
from dotenv import load_dotenv

# ⚠️ 新しい公式ライブラリ ⚠️
from google import genai
from google.genai import types

load_dotenv()

class GeminiService:
    @staticmethod
    def analyze_schedule(file_data, content_type):
        print("\n" + "="*50)
        print("[DEBUG-PROBE] 🌟 新生Gemini 解析スタート！")
        print(f"[DEBUG-PROBE] MIME={content_type}")
        
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            print("[DEBUG-PROBE] ❌ エラー: GEMINI_API_KEY がありません！")
            raise ValueError("API KEY MISSING")

        try:
            # 新しいクライアントの初期化
            client = genai.Client(api_key=api_key)
            
            # 💡 【重要】確実に無料で使える安定モデル 💡
            model_name = 'gemini-1.5-flash'
            
            prompt = """
            画像から全ての予定を抽出し、以下のJSON配列形式のみで出力してください。
            [{"title": "予定", "start": "2026-03-24T09:00:00", "end": "2026-03-24T18:00:00", "location": "", "description": ""}]
            ※期間予定は1日ずつ分割すること。余計な文字は一切不要。
            """
            
            # 画像データを新しい仕様に合わせる
            document = types.Part.from_bytes(data=file_data, mime_type=content_type)
            
            # JSON出力を強制してパースエラーを防ぐ
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
            )
            
            print(f"[DEBUG-PROBE] 無料モデル({model_name}) にリクエスト送信中...")
            
            # AIへリクエスト送信
            response = client.models.generate_content(
                model=model_name,
                contents=[prompt, document],
                config=config,
            )
            
            print("[DEBUG-PROBE] ✅ Geminiから応答を受信！")
            
            raw_text = response.text
            print(f"\n--- [DEBUG-PROBE: AI 生データ] ---\n{raw_text}\n----------------------------------\n")

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
                    
                    # 期間予定を1日ずつバラすロジック
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