from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import json
import os
from datetime import datetime
from utils.card_generator import batch_generate_cards
from supabase import create_client, Client

app = Flask(__name__)
app.secret_key = "dev-secret-change-me"

# --- Supabase Configuration ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set as environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# --- Data Helpers (Now using Supabase) ---
def get_user_by_username(username):
    """Fetches a single user from Supabase by their username."""
    response = supabase.table('users').select("*").eq('username', username).single().execute()
    return response.data

def get_all_users():
    """Fetches all users from Supabase and returns them as a dictionary."""
    response = supabase.table('users').select("*").execute()
    return {u['username']: u for u in response.data}

def get_all_cards():
    """Fetches all cards from Supabase."""
    response = supabase.table('cards').select("*").order('scanned_at', desc=True).execute()
    return response.data

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
    user = get_user_by_username(username)
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
    
    # Fetch data from Supabase
    all_users = get_all_users()
    all_cards = get_all_cards()
    
    return render_template("admin_dashboard.html", users=all_users, cards=all_cards, skills=SKILLS)

@app.route("/admin/generate", methods=["POST"])
def admin_generate():
    if session.get("role") != "admin":
        return redirect(url_for("index"))
    skill = request.form.get("skill")
    count = int(request.form.get("count", 5))
    
    # Generate new cards
    new_cards = batch_generate_cards(skill, count)
    
    # Insert new cards into Supabase
    try:
        supabase.table('cards').insert(new_cards).execute()
        flash(f"Successfully generated and saved {len(new_cards)} cards.", "success")
    except Exception as e:
        flash(f"Error saving cards to database: {e}", "error")
        # Still render the page but show an error
        return redirect(url_for('admin_dashboard'))

    generated = []
    for card in new_cards:
        scan_url = url_for("student_skill", skill_name=card["skill_name"], serial=card["id"], _external=True)
        view_url = url_for("student_skill", skill_name=card["skill_name"], _external=True)
        generated.append({"serial": card["id"], "scan_url": scan_url, "view_url": view_url})

    # Fetch fresh data to display on the dashboard after generating
    all_users = get_all_users()
    all_cards = get_all_cards()
    return render_template("admin_dashboard.html", users=all_users, generated=generated, chosen_skill=skill, cards=all_cards, skills=SKILLS)

# Student dashboard: show scanned skills, points, QR code reader placeholder
@app.route("/student")
def student_dashboard():
    if session.get("role") != "student":
        return redirect(url_for("index"))
    user = session.get("user")
    user_data = get_user_by_username(user) # Fetch from Supabase
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
    # TODO: Update user in Supabase
    
    # Calculate badges (based on points)
    badges_count = points // 50  # New badge every 50 points
    if badges_count > user_data.get("badges_earned", 0):
        user_data["badges_earned"] = badges_count
        user_data["badges"] = [f"Badge {i+1}" for i in range(badges_count)]
        # TODO: Update user in Supabase
    
    # Build scanned info: map serial -> card details (skill code and title)
    all_cards = get_all_cards()
    cards_map = {c['id']: c for c in all_cards}
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
    # TODO: Update user in Supabase

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
    user_data = get_user_by_username(user)
    if not user or user_data.get("role") != "student":
        return redirect(url_for("index"))
        
    # Get user's scanned skills
    scanned_skills = user_data.get("scanned_skills", [])
    
    # Check if user has access to this skill
    all_cards = get_all_cards()
    cards_map = {c['id']: c for c in all_cards}
    
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
        card_response = supabase.table('cards').select('*').eq('id', serial).single().execute()
        card = card_response.data
        if card and not card.get('holder'):
            # Update card in Supabase
            supabase.table('cards').update({
                'holder_id': user_data['id'], 
                'scanned_at': datetime.utcnow().isoformat()
            }).eq('id', serial).execute()

            # Update user in Supabase
            new_points = user_data.get('points', 0) + 10
            # TODO: Append serial to a 'scanned_serials' array field in the user table
            supabase.table('users').update({'points': new_points}).eq('username', user).execute()

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
    
    card_response = supabase.table('cards').select('*').eq('id', serial).single().execute()
    if not card_response.data:
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
    user_data = get_user_by_username(user)
    existing_serials = user_data.get('scanned_skills', []) # This needs to be a field in your Supabase user table
    for es in existing_serials:
        if es == serial:
            # same serial already in list (shouldn't happen because holder was None), continue
            continue
        other_card_res = supabase.table('cards').select('skill_name').eq('id', es).single().execute()
        other_card = other_card_res.data
        if other_card and other_card.get('skill_name') == card.get('skill_name'):
            # user already has this skill via a different card
            return jsonify({'status': 'duplicate_skill', 'message': 'You already have this skill from another card.', 'skill': card.get('skill_name'), 'serial': serial, 'existing_serial': es})
    # Claim the card for the current user (atomic-ish)
    user = session.get('user')
    user_data = get_user_by_username(user)
    
    # Update card in Supabase
    supabase.table('cards').update({
        'holder_id': user_data['id'], 
        'scanned_at': datetime.utcnow().isoformat()
    }).eq('id', serial).execute()

    # Update user in Supabase
    new_points = user_data.get('points', 0) + 10
    # TODO: Append serial to a 'scanned_serials' array field in the user table
    supabase.table('users').update({'points': new_points}).eq('username', user).execute()

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
        user_data = get_user_by_username(user)
        supabase.table('users').update({'points': user_data.get('points', 0) + 20}).eq('username', user).execute()
    
    return jsonify({
        'score': score,
        'total': total,
        'percentage': percentage,
        'passed': passed,
        'points_earned': 20 if passed else 0
    })

if __name__ == "__main__":
    app.run(debug=True)
