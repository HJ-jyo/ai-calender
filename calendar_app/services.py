import google.generativeai as genai
import json
import os
import traceback
import io
from PIL import Image
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
        
        # --- 🚀 画像圧縮（メモリパンク防止＆通信爆速化） ---
        try:
            img = Image.open(io.BytesIO(file_data))
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            output_io = io.BytesIO()
            img.save(output_io, format='JPEG', quality=85)
            optimized_data = output_io.getvalue()
            optimized_type = 'image/jpeg'
            print("DEBUG: 画像の圧縮に成功しました。")
        except Exception as e:
            print(f"DEBUG: 画像圧縮をスキップしました: {e}")
            optimized_data = file_data
            optimized_type = content_type

        # 💡 本番用の超高速モデル（安定・最速）
        model_name = 'models/gemini-2.5-flash'
        
        try:
            model = genai.GenerativeModel(model_name)
            
            # 🌟 文章形式や曖昧な表現にも対応した、最強の柔軟プロンプト 🌟
            prompt = """
            提供された画像（シフト表、カレンダー、時間割だけでなく、「文章形式のメモ」や「箇条書きの予定」などあらゆる形式）を解析し、全ての「予定」を抽出して以下のJSON形式のリストで返してください。
            
            【⚠️除外ルール（超重要）】
            1. 「休み」「休日」「休館日」「閉館」「なし」「空白」など、予定が「無い」ことを示す項目は絶対に抽出しないでください。
            2. 全く同じ時間帯に、全く同じ名前の予定を複数回出力しないでください（重複禁止）。
            
            【⏰ 時間と日付の柔軟な抽出ルール（最重要）】
            3. 表のマス目だけでなく、周辺のテキストや文脈からも時間を推測してください（例: 「14:00〜 会議」「3限目」など）。
            4. 曖昧な時間表現は、文脈や一般的な常識に基づいて推測して具体的な時間（HH:MM）に変換してください。
               - 例：「午前」= 09:00〜12:00、「午後」= 13:00〜18:00、「終日」= 09:00〜18:00
            5. 開始時間しか書かれていない場合は、文脈から推測するか、デフォルトで「1時間後」を終了時間としてください。
            6. 時間が一切書かれていない「日付のみの行事」は、09:00:00〜18:00:00として処理してください。
            
            【📅 データ作成ルール】
            7. 連日の予定（例：24〜28日）であっても、必ず **1日単位に切り分けて（バラして）** 出力してください。
            8. 現在は 2026年3月21日 です。画像内の日付に年が書かれていない場合は 2026年 を補完してください。
            
            【出力形式】
            [
                {
                    "title": "予定の名称",
                    "start": "2026-03-24T09:00:00",
                    "end": "2026-03-24T18:00:00",
                    "location": "場所（わからなければ空白）",
                    "description": "関連する詳細やメモ（わからなければ空白）"
                }
            ]
            ※余計な説明文やマークダウン（```jsonなど）は一切含めず、純粋なJSON配列のみを出力してください。
            """

            print(f"DEBUG: {model_name} へリクエストを送信中...")
            response = model.generate_content([
                prompt,
                {'mime_type': optimized_type, 'data': optimized_data}
            ])

            raw_text = response.text
            print(f"DEBUG AI Response (冒頭のみ): {raw_text[:200]}...")

            # --- JSON抽出ロジック ---
            start_index = raw_text.find('[')
            end_index = raw_text.rfind(']') + 1
            if start_index == -1:
                start_index = raw_text.find('{')
                end_index = raw_text.rfind('}') + 1
            
            if start_index == -1:
                raise ValueError(f"AIがJSONを返しませんでした。生データ: {raw_text}")

            json_text = raw_text[start_index:end_index]
            events = json.loads(json_text)
            
            if not isinstance(events, list):
                events = [events]

            final_events = []
            for ev in events:
                try:
                    start_dt = datetime.fromisoformat(ev['start'])
                    end_dt = datetime.fromisoformat(ev['end'])
                    
                    # 日付をまたぐ予定を1日ずつに分割
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

            # --- 🛡️ 重複絶対殺すマン（Python側での最終フィルター） ---
            unique_events = []
            seen = set()
            for ev in final_events:
                # タイトル、開始時間、終了時間が完全に同じなら2回目以降は無視
                identifier = f"{ev.get('title')}_{ev.get('start')}_{ev.get('end')}"
                if identifier not in seen:
                    seen.add(identifier)
                    unique_events.append(ev)

            return unique_events

        except Exception as e:
            # エラー時は詳細をターミナルへ出力
            print("\n=== GEMINI API ERROR DETAIL ===")
            print(traceback.format_exc())
            print("===============================\n")
            raise e