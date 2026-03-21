import json
import os
import traceback
from datetime import datetime, timedelta
from dotenv import load_dotenv

from google import genai
from google.genai import types

load_dotenv()

class GeminiService:
    @staticmethod
    def analyze_schedule(file_data, content_type):
        print("\n" + "="*50)
        print("[DEBUG-PROBE] 🌟 自動回避型Gemini 解析スタート！")
        print(f"[DEBUG-PROBE] MIME={content_type}")
        
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            print("[DEBUG-PROBE] ❌ エラー: GEMINI_API_KEY がありません！")
            raise ValueError("API KEY MISSING")

        client = genai.Client(api_key=api_key)
        
        # 💡 無料で使えるモデルの「予備リスト」
        # 1つ目がダメなら2つ目、2つ目がダメなら3つ目へと自動で切り替えます
        target_models = [
            'gemini-1.5-flash-8b',       # 最も軽く、無料枠が広いモデル
            'gemini-1.5-flash-latest',   # 1.5の最新安定版
            'gemini-2.0-flash-lite-preview-02-05' # 最新の軽量版
        ]
        
        prompt = """
        画像から全ての予定を抽出し、以下のJSON配列形式のみで出力してください。
        [{"title": "予定", "start": "2026-03-24T09:00:00", "end": "2026-03-24T18:00:00", "location": "", "description": ""}]
        ※期間予定は1日ずつ分割すること。余計な文字は一切不要。
        """
        
        document = types.Part.from_bytes(data=file_data, mime_type=content_type)
        config = types.GenerateContentConfig(response_mime_type="application/json")
        
        response = None
        
        # 🔥 自動フォールバック（回避）システム 🔥
        for model_name in target_models:
            try:
                print(f"[DEBUG-PROBE] {model_name} で解析を試みます...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=[prompt, document],
                    config=config,
                )
                print(f"[DEBUG-PROBE] ✅ {model_name} で解析に成功しました！")
                break # 成功したらループを抜けて次の処理へ
            except Exception as e:
                print(f"[DEBUG-PROBE] ⚠️ {model_name} はエラーで弾かれました（自動で次のモデルを試します）: {e}")
                continue # 失敗したら次のモデルへ
        
        if not response:
            print("[DEBUG-PROBE] ❌ 全てのモデルが制限にかかりました。少し時間をおいてください。")
            return []
            
        raw_text = response.text
        print(f"\n--- [DEBUG-PROBE: AI 生データ] ---\n{raw_text}\n----------------------------------\n")

        clean_text = raw_text.strip()
        clean_text = clean_text.replace("```json", "").replace("```", "").strip()
        
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
                
                # 期間予定の分割ロジック
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