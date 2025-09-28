from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import json
import os
from datetime import datetime
from utils.card_generator import batch_generate_cards

app = Flask(__name__)
app.secret_key = "dev-secret-change-me"


# Card storage helpers
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
CARDS_PATH = os.path.join(DATA_DIR, 'cards.json')

def load_cards():
    try:
        with open(CARDS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"cards": []}

def save_cards(cards_data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CARDS_PATH, 'w', encoding='utf-8') as f:
        json.dump(cards_data, f, indent=2, ensure_ascii=False)


# Users storage helpers
USERS_PATH = os.path.join(DATA_DIR, 'users.json')

def load_users():
    try:
        with open(USERS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # return dict keyed by username for fast lookup
            return {u['username']: u for u in data.get('users', [])}
    except FileNotFoundError:
        return {}

def save_users(users_dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    # convert dict keyed by username back to list
    users_list = []
    for uname, u in users_dict.items():
        entry = u.copy()
        entry['username'] = uname
        users_list.append(entry)
    with open(USERS_PATH, 'w', encoding='utf-8') as f:
        json.dump({'users': users_list}, f, indent=2, ensure_ascii=False)

# Load users at startup
USERS = load_users()


# If USERS is empty (first run), create default users
if not USERS:
    USERS = {
        "admin": {"password": "adminpass", "role": "admin", "scanned_skills": []},
        "student_1": {
            "password": "student1pass", 
            "role": "student", 
            "scanned_skills": [], 
            "points": 0,
            "badges": [],
            "streak": 0,
            "last_activity": None,
            "badges_earned": 0,
            "skill_progress": {}
        },
        "student_2": {
            "password": "student2pass", 
            "role": "student", 
            "scanned_skills": [], 
            "points": 0,
            "badges": [],
            "streak": 0,
            "last_activity": None,
            "badges_earned": 0
        },
    }
    save_users(USERS)

# All available skills
SKILLS = [
    {"code": "communication", "title": "Communication", "icon": "🗣️", "desc": "Express ideas clearly and listen actively."},
    {"code": "collaboration", "title": "Collaboration", "icon": "🤝", "desc": "Work effectively in teams to reach goals."},
    {"code": "critical-thinking", "title": "Critical Thinking", "icon": "🧠", "desc": "Analyze, evaluate, and make reasoned decisions."},
    {"code": "creativity", "title": "Creativity", "icon": "🎨", "desc": "Generate original ideas and solutions."},
    {"code": "problem-solving", "title": "Problem Solving", "icon": "🧩", "desc": "Identify issues and design effective fixes."},
    {"code": "adaptability", "title": "Adaptability", "icon": "🔄", "desc": "Adapt and thrive in changing environments."},
    {"code": "digital-literacy", "title": "Digital Literacy", "icon": "💻", "desc": "Navigate and use digital tools effectively."},
    {"code": "initiative", "title": "Initiative", "icon": "🚀", "desc": "Take proactive steps and show self-direction."},
    {"code": "leadership", "title": "Leadership", "icon": "👥", "desc": "Guide and inspire teams to achieve goals."},
    {"code": "media-literacy", "title": "Media Literacy", "icon": "📱", "desc": "Analyze and create media content critically."}
]

@app.route("/")
def index():
    return render_template("login.html", skills=SKILLS)


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username")
    password = request.form.get("password")
    user = USERS.get(username)
    if user and user["password"] == password:
        session["user"] = username
        session["role"] = user["role"]
        flash("Login successful!", "success")
        if user["role"] == "admin":
            return redirect(url_for("admin_dashboard"))
        else:
            return redirect(url_for("student_dashboard"))
    else:
        flash("Invalid credentials.", "error")
        return redirect(url_for("index"))


# Admin dashboard: view users and generate QR codes
@app.route("/admin")
def admin_dashboard():
    if session.get("role") != "admin":
        return redirect(url_for("index"))
    cards_data = load_cards()
    return render_template("admin_dashboard.html", users=USERS, cards=cards_data.get('cards', []), skills=SKILLS)

@app.route("/admin/generate", methods=["POST"])
def admin_generate():
    if session.get("role") != "admin":
        return redirect(url_for("index"))
    skill = request.form.get("skill")
    count = int(request.form.get("count", 5))
    # Generate new cards
    new_cards = batch_generate_cards(skill, count)
    # Load existing cards, add new ones and save
    cards_data = load_cards()
    cards_data.setdefault('cards', [])
    cards_data['cards'].extend(new_cards)
    save_cards(cards_data)
    generated = []
    for card in new_cards:
        # scan_url is the URL encoded in the QR (legacy full link with serial)
        scan_url = url_for("student_skill", skill_name=card["skill_name"], serial=card["id"], _external=True)
        # view_url is the user-facing skill page without serial
        view_url = url_for("student_skill", skill_name=card["skill_name"], _external=True)
        generated.append({"serial": card["id"], "scan_url": scan_url, "view_url": view_url})
    return render_template("admin_dashboard.html", users=USERS, generated=generated, chosen_skill=skill, cards=cards_data.get('cards', []), skills=SKILLS)

# Student dashboard: show scanned skills, points, QR code reader placeholder
@app.route("/student")
def student_dashboard():
    if session.get("role") != "student":
        return redirect(url_for("index"))
    user = session.get("user")
    user_data = USERS[user]
    scanned = user_data.get("scanned_skills", [])
    points = user_data.get("points", 0)
    
    # Get skill progress data
    skill_progress = user_data.get("skill_progress", {})
    for skill in SKILLS:
        if skill["code"] in skill_progress:
            # Ensure all progress fields exist
            if "scanned" not in skill_progress[skill["code"]]:
                skill_progress[skill["code"]]["scanned"] = skill["code"] in scanned
            if "read" not in skill_progress[skill["code"]]:
                skill_progress[skill["code"]]["read"] = False
            if "quiz_taken" not in skill_progress[skill["code"]]:
                skill_progress[skill["code"]]["quiz_taken"] = False
        else:
            # Initialize progress for this skill
            skill_progress[skill["code"]] = {
                "scanned": skill["code"] in scanned,
                "read": False,
                "quiz_taken": False
            }
    today = datetime.now().date()
    last_activity = user_data.get("last_activity")
    if last_activity:
        last_activity = datetime.strptime(last_activity, "%Y-%m-%d").date()
        if (today - last_activity).days == 1:
            # Consecutive day
            user_data["streak"] = user_data.get("streak", 0) + 1
        elif (today - last_activity).days > 1:
            # Streak broken
            user_data["streak"] = 1
    else:
        user_data["streak"] = 1
    
    user_data["last_activity"] = today.strftime("%Y-%m-%d")
    save_users(USERS)
    
    # Calculate badges (based on points)
    badges_count = points // 50  # New badge every 50 points
    if badges_count > user_data.get("badges_earned", 0):
        user_data["badges_earned"] = badges_count
        user_data["badges"] = [f"Badge {i+1}" for i in range(badges_count)]
        save_users(USERS)
    
    # Build scanned info: map serial -> card details (skill code and title)
    cards_data = load_cards()
    cards_map = {c['id']: c for c in cards_data.get('cards', [])}
    scanned_info = []
    for s in scanned:
        c = cards_map.get(s)
        if c:
            # find title from SKILLS list
            title = next((x['title'] for x in SKILLS if x['code'] == c.get('skill_name')), c.get('skill_name'))
            scanned_info.append({'serial': s, 'skill_code': c.get('skill_name'), 'title': title, 'scanned_at': c.get('scanned_at')})
        else:
            scanned_info.append({'serial': s, 'skill_code': None, 'title': s, 'scanned_at': None})
    # Update skill progress with any newly scanned skills
    for s in scanned:
        card = cards_map.get(s)
        if card:
            skill_name = card.get('skill_name')
            if skill_name and skill_name in skill_progress:
                skill_progress[skill_name]['scanned'] = True
    user_data['skill_progress'] = skill_progress
    save_users(USERS)

    return render_template("student_dashboard.html",
        user=user,
        scanned_skills=scanned_info,
        points=points,
        skills=SKILLS,
        badges=len(user_data.get("badges", [])),
        user_badges=user_data.get("badges", []),
        skill_progress=skill_progress,
        streak=user_data.get("streak", 0)
    )


# When a user scans a QR code, add the skill to their profile and show the skill page
@app.route("/skills/<skill_name>")
@app.route("/skills/<skill_name>/<serial>")
def student_skill(skill_name, serial=None):
    """Show the skill page. Access is restricted based on scanned skills.
    Users must have scanned a valid QR code to access the skill content.
    """
    user = session.get("user")
    if not user or USERS[user]["role"] != "student":
        return redirect(url_for("index"))
        
    # Get user's scanned skills
    user_data = USERS[user]
    scanned_skills = user_data.get("scanned_skills", [])
    
    # Check if user has access to this skill
    cards_data = load_cards()
    cards_map = {c['id']: c for c in cards_data.get('cards', [])}
    
    has_access = False
    for scanned_serial in scanned_skills:
        card = cards_map.get(scanned_serial)
        if card and card.get('skill_name') == skill_name:
            has_access = True
            break
    
    # Get skill title for the error page
    skill_title = next((s['title'] for s in SKILLS if s['code'] == skill_name), skill_name)
    
    if not has_access:
        return render_template('access_denied.html', skill_title=skill_title)

    # If a serial was provided, try to claim it
    if serial:
        # Already scanned?
        if serial in scanned_skills:
            # If it's the same skill, grant access
            card = cards_map.get(serial)
            if card and card.get('skill_name') == skill_name:
                has_access = True
            else:
                flash("You have already scanned this QR code.", "error")
                return redirect(url_for("student_dashboard"))

        # Find card and mark it claimed for this user
        cards_data = load_cards()
        card = next((c for c in cards_data.get('cards', []) if c.get('id') == serial), None)
        if card and not card.get('holder'):
            card['holder'] = user
            card['scanned_at'] = datetime.utcnow().isoformat()
            # persist cards
            save_cards(cards_data)

            # update user
            USERS[user].setdefault('scanned_skills', [])
            USERS[user]['scanned_skills'].append(serial)
            USERS[user].setdefault('points', 0)
            USERS[user]['points'] += 10
            save_users(USERS)
            flash("Skill scanned and points awarded!", "success")
        else:
            # card missing or already held
            flash("This card is invalid or already claimed.", "error")
            return redirect(url_for("student_dashboard"))

    # Render the skill page (serial may be None)
    return render_template(f'skills/{skill_name}.html', skill_name=skill_name, serial=serial, user=user)


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("index"))


@app.route('/api/validate_card')
def api_validate_card():
    # Requires logged in student
    if session.get('role') != 'student':
        return jsonify({'status': 'error', 'message': 'Authentication required'}), 403
    skill = request.args.get('skill')
    serial = request.args.get('serial')
    if not serial:
        return jsonify({'status': 'invalid', 'message': 'Missing serial'}), 400
    cards_data = load_cards()
    card = next((c for c in cards_data.get('cards', []) if c.get('id') == serial), None)
    if not card:
        return jsonify({'status': 'invalid', 'message': 'QR code is not valid.'})
    # If the card already has a holder, it's claimed
    if card.get('holder'):
        # if held by current user, treat as already scanned
        if card.get('holder') == session.get('user'):
            return jsonify({'status': 'already_scanned', 'message': 'You already scanned this card.', 'skill': card.get('skill_name'), 'serial': serial})
        return jsonify({'status': 'claimed', 'message': f'This card was already claimed by {card.get("holder")}.', 'skill': card.get('skill_name'), 'serial': serial})
    # Optionally check that skill matches
    if skill and card.get('skill_name') != skill:
        return jsonify({'status': 'invalid', 'message': 'Skill does not match QR code.'})
    # Check if the user already has the same skill via another serial
    user = session.get('user')
    existing_serials = USERS[user].get('scanned_skills', [])
    for es in existing_serials:
        if es == serial:
            # same serial already in list (shouldn't happen because holder was None), continue
            continue
        other_card = next((c2 for c2 in cards_data.get('cards', []) if c2.get('id') == es), None)
        if other_card and other_card.get('skill_name') == card.get('skill_name'):
            # user already has this skill via a different card
            return jsonify({'status': 'duplicate_skill', 'message': 'You already have this skill from another card.', 'skill': card.get('skill_name'), 'serial': serial, 'existing_serial': es})
    # Claim the card for the current user (atomic-ish)
    user = session.get('user')
    card['holder'] = user
    card['scanned_at'] = datetime.utcnow().isoformat()
    # persist cards
    save_cards(cards_data)

    # update user in-memory and persist
    USERS[user].setdefault('scanned_skills', [])
    USERS[user]['scanned_skills'].append(serial)
    USERS[user].setdefault('points', 0)
    USERS[user]['points'] += 10
    save_users(USERS)

    # Return the non-serial skill URL so client can redirect
    redirect_url = url_for('student_skill', skill_name=card.get('skill_name'))
    return jsonify({'status': 'ok', 'message': 'QR code claimed. Redirecting...', 'skill': card.get('skill_name'), 'serial': serial, 'redirect': redirect_url})


# Route to serve skill HTML pages from 'skills' folder
@app.route('/skills/<skill_name>.html')
def skill_html(skill_name):
    return render_template(f'skills/{skill_name}.html')

@app.route('/quiz/<skill_name>')
def quiz(skill_name):
    if not session.get('user'):
        flash('Please log in to take the quiz.', 'error')
        return redirect(url_for('index'))
    
    # Load quiz questions from JSON file
    questions_path = os.path.join(DATA_DIR, 'questions.json')
    try:
        with open(questions_path, 'r', encoding='utf-8') as f:
            quizzes = json.load(f)
    except FileNotFoundError:
        flash('Quiz questions not found.', 'error')
        return redirect(url_for('student_dashboard'))
    
    if skill_name not in quizzes:
        flash('Quiz not found for this skill.', 'error')
        return redirect(url_for('student_dashboard'))
        
    skill_quiz = quizzes[skill_name]
    return render_template('quiz.html', 
                         skill_name=skill_name,
                         skill_title=skill_quiz['name'],
                         description=skill_quiz['description'],
                         questions=skill_quiz['questions'],
                         user=session.get('user'))

@app.route('/submit_quiz/<skill_name>', methods=['POST'])
def submit_quiz(skill_name):
    if not session.get('user'):
        return jsonify({'error': 'Please log in to submit the quiz.'}), 403
        
    answers = request.json.get('answers', {})
    # Load quiz questions for validation
    questions_path = os.path.join(DATA_DIR, 'questions.json')
    try:
        with open(questions_path, 'r', encoding='utf-8') as f:
            quizzes = json.load(f)
    except FileNotFoundError:
        return jsonify({'error': 'Quiz questions not found'}), 404
    
    if skill_name not in quizzes:
        return jsonify({'error': 'Quiz not found'}), 404
        
    skill_quiz = quizzes.get(skill_name)
    if not skill_quiz:
        return jsonify({'error': 'Quiz not found'}), 404
        
    questions = skill_quiz['questions']
    score = 0
    total = len(questions)
    
    for q_idx, question in enumerate(questions):
        if str(q_idx) in answers and answers[str(q_idx)] == question['correct']:
            score += 1
            
    percentage = (score / total) * 100
    passed = percentage >= 70  # Pass threshold is 70%
    
    # Update user's points if passed
    if passed:
        user = session.get('user')
        USERS[user]['points'] = USERS[user].get('points', 0) + 20
        save_users(USERS)
    
    return jsonify({
        'score': score,
        'total': total,
        'percentage': percentage,
        'passed': passed,
        'points_earned': 20 if passed else 0
    })

if __name__ == "__main__":
    app.run(debug=True)
