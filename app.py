from flask import Flask, render_template, request, jsonify
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import requests 
import webbrowser
load_dotenv()

SYSTEM_PROMPT = """
You are a highly intelligent, emotionally supportive human companion — not a chatbot.

🎯 Language Rule:
* Speak ONLY in clear, natural, professional English
* NO Tanglish, NO slang, NO mixed language

💛 Tone:
* Warm, calm, friendly, emotionally supportive, human-like (not robotic).

🎯 Your Role:
Understand the user's emotions and respond like a real caring person.

⚡ RULES:
1. Never repeat the same sentence.
2. Never use generic replies like "I'm here for you" or "Tell me more".
3. Always respond based on the user’s message.
4. Keep responses short (2–4 lines).
5. Add a natural follow-up question.
6. Make each reply feel unique and thoughtful.

💬 RESPONSE STRUCTURE:
1. Emotion Recognition → Acknowledge how the user feels.
2. Thoughtful Response → Give a meaningful, human-like reaction.
3. Gentle Support / Insight → Add something helpful or comforting.
4. Natural Follow-up Question → Keep conversation flowing.

🔐 OUTPUT FORMAT:
You MUST always return a JSON object with exactly two keys:
1. "mood" — detected emotion with emoji (e.g. "😔 Sad", "🔥 Angry", "😊 Happy", "😴 Tired", "😰 Stressed", "🤝 Lonely")
2. "reply" — your short 2-4 lines human-like response (use \\n between lines)
"""

app = Flask(__name__)
DATA_FILE = 'moods.json'

def load_moods():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_moods(moods):
    with open(DATA_FILE, 'w') as f:
        json.dump(moods, f, indent=4)

def calculate_streak(moods):
    if not moods:
        return 1
    
    dates = sorted(list(set([datetime.fromisoformat(m['timestamp']).date() for m in moods])), reverse=True)
    if not dates:
        return 1
        
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    
    if dates[0] != today and dates[0] != yesterday:
        return 1
        
    streak = 1
    current_date = dates[0]
    
    for d in dates[1:]:
        if (current_date - d).days == 1:
            streak += 1
            current_date = d
        else:
            break
            
    # If the first entry is today, and we checked backwards
    if dates[0] == today and len(dates) > 1 and (dates[0] - dates[1]).days == 1:
        pass # Streak logic covers it
        
    return streak

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/save_mood', methods=['POST'])
def save_mood():
    data = request.json
    mood = data.get('mood')
    note = data.get('note', '').lower()
    
    if not mood:
        return jsonify({'error': 'Mood is required'}), 400

    moods = load_moods()
    
    # Calculate AI Response
    ai_response = ""
    if "tired" in note:
        ai_response = "Get some rest 😴"
    elif "alone" in note:
        ai_response = "You're not alone 💛"
    elif "stress" in note:
        ai_response = "Take a short break 🧘"
    else:
        if mood == "Sad":
            ai_response = "I understand… that sounds tough. You're stronger than you think 💙"
        elif mood == "Happy":
            ai_response = "That's amazing! Hold onto this positive energy ✨"
        elif mood == "Stressed" or mood == "Anxious":
            ai_response = "Looks like a lot is going on. Take a deep breath—you’ve got this 🧘"
        elif mood == "Calm":
            ai_response = "It's nice to see you're feeling calm. Keep this balance going 🌿"
        elif mood == "Neutral":
            ai_response = "Sometimes neutral is okay too. Take your time 🤍"
        else:
            ai_response = "Take care of yourself today."

    new_entry = {
        'id': datetime.now().strftime("%Y%m%d%H%M%S"),
        'mood': mood,
        'note': data.get('note', ''),
        'ai_response': ai_response,
        'timestamp': datetime.now().isoformat(),
        'date': datetime.now().strftime("%Y-%m-%d"),
        'display_time': datetime.now().strftime("%I:%M %p")
    }
    
    moods.append(new_entry)
    
    # Keep last 30 entries
    if len(moods) > 30:
        moods = moods[-30:]
        
    streak = calculate_streak(moods)
    save_moods(moods)
    
    return jsonify({
        'success': True,
        'ai_response': ai_response,
        'entry': new_entry,
        'streak': streak
    })

@app.route('/get_moods', methods=['GET'])
def get_moods():
    moods = load_moods()
    streak = calculate_streak(moods)
    return jsonify({'moods': moods, 'streak': streak})

@app.route('/weekly_summary', methods=['GET'])
def weekly_summary():
    moods = load_moods()
    if not moods:
        return jsonify({'summary': "Start tracking your mood to get a weekly summary!"})
        
    last_7_days = [m for m in moods if (datetime.now() - datetime.fromisoformat(m['timestamp'])).days <= 7]
    
    if not last_7_days:
         return jsonify({'summary': "No moods tracked this week yet."})
         
    mood_counts = {}
    for m in last_7_days:
        mood = m['mood']
        mood_counts[mood] = mood_counts.get(mood, 0) + 1
        
    most_frequent = max(mood_counts, key=mood_counts.get)
    
    summary = ""
    if most_frequent in ["Stressed", "Anxious", "Sad"]:
        summary = f"You felt {most_frequent.lower()} often this week. Try relaxing activities and take it easy 💙"
    elif most_frequent == "Happy":
        summary = "You've had a mostly happy week! Keep doing what makes you feel good ✨"
    elif most_frequent in ["Calm", "Neutral"]:
        summary = "Your week has been quite balanced. Keep maintaining your steady routine 🌿"
    else:
        summary = f"Your most frequent mood this week was {most_frequent}. Hope next week is even better!"
        
    return jsonify({'summary': summary})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    message = data.get('message', '')
    history = data.get('history', [])
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return jsonify({'error': "API key missing!"}), 500
        
    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [{"role": "user", "content": message}]
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-4o-mini",
                "messages": messages,
                "temperature": 0.9,
                "max_tokens": 150,
                "response_format": { "type": "json_object" }
            },
            timeout=15
        )
        if response.status_code != 200:
            raise Exception(f"API Error: {response.status_code}")

        res_data = response.json()
        ai_response_str = res_data.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        if not ai_response_str:
            raise Exception("Empty response")
            
        try:
            ai_data = json.loads(ai_response_str)
        except json.JSONDecodeError:
            ai_data = {"reply": ai_response_str, "mood": "😊"}
            
        return jsonify({'response': ai_data.get('reply'), 'mood': ai_data.get('mood', '😊')})
    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':

    webbrowser.open("http://127.0.0.1:5000")

    app.run(debug=True, use_reloader=False)