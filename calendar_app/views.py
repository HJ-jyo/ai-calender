import os
import json
import traceback
from django.shortcuts import render, redirect
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from .services import GeminiService

# 本番環境のリダイレクト先
REDIRECT_URI = 'https://smart-calender.duckdns.org/oauth2callback/'
SCOPES = ['https://www.googleapis.com/auth/calendar']

def index(request):
    creds_data = request.session.get('google_credentials')
    is_authenticated = bool(creds_data and 'token' in creds_data)
    
    print(f"\n--- [DEBUG: INDEX] ---")
    print(f"Session ID: {request.session.session_key}")
    print(f"Authenticated: {is_authenticated}")
    print("----------------------\n")
    
    return render(request, 'calendar_app/index.html', {
        'is_authenticated': is_authenticated
    })

def privacy(request):
    return render(request, 'calendar_app/privacy.html')

def authorize(request):
    client_config_path = os.path.join(settings.BASE_DIR, 'client_secret.json')
    flow = Flow.from_client_secrets_file(
        client_config_path,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI # 修正済み
    )
    authorization_url, state = flow.authorization_url(access_type='offline', prompt='consent')
    
    request.session['oauth_state'] = state
    request.session['oauth_code_verifier'] = flow.code_verifier 
    request.session.save()
    return redirect(authorization_url)

def oauth2callback(request):
    state = request.session.get('oauth_state')
    code_verifier = request.session.get('oauth_code_verifier')
    client_config_path = os.path.join(settings.BASE_DIR, 'client_secret.json')
    
    try:
        flow = Flow.from_client_secrets_file(
            client_config_path, 
            scopes=SCOPES, 
            state=state,
            redirect_uri=REDIRECT_URI # 修正済み
        )
        flow.fetch_token(
            authorization_response=request.build_absolute_uri(),
            code_verifier=code_verifier
        )
        
        credentials = flow.credentials
        request.session['google_credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        request.session.modified = True
        request.session.save()
        
        print(f"SUCCESS: Auth completed for session {request.session.session_key}")
        return redirect('/')
    except Exception as e:
        print(f"CRITICAL AUTH ERROR: {e}")
        return redirect('/')

def logout_view(request):
    request.session.flush()
    return redirect('/')

@csrf_exempt
def upload_file(request):
    if request.method == 'POST' and request.FILES.getlist('files'):
        all_events = []
        for f in request.FILES.getlist('files'):
            try:
                res = GeminiService.analyze_schedule(f.read(), f.content_type)
                if res:
                    if isinstance(res, list): all_events.extend(res)
                    else: all_events.append(res)
            except: continue
        return JsonResponse({'status': 'success', 'events': all_events})
    return JsonResponse({'status': 'error'})

@csrf_exempt
def register_events(request):
    creds_data = request.session.get('google_credentials')
    if not creds_data:
        return JsonResponse({'status': 'error', 'message': '認証が必要です'})
    try:
        data = json.loads(request.body)
        creds = Credentials(**creds_data)
        service = build('calendar', 'v3', credentials=creds)
        
        for ev in data.get('events', []):
            start_dt = ev['start_time'].replace('Z', '')
            end_dt = ev['end_time'].replace('Z', '')

            service.events().insert(calendarId='primary', body={
                'summary': ev['summary'],
                'start': {'dateTime': start_dt, 'timeZone': 'Asia/Tokyo'},
                'end': {'dateTime': end_dt, 'timeZone': 'Asia/Tokyo'},
            }).execute()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        print(f"Sync Error: {traceback.format_exc()}")
        return JsonResponse({'status': 'error', 'message': str(e)})