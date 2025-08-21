from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
import firebase_admin
from firebase_admin import credentials, db, initialize_app
from flask import session
from flask import make_response
import os
import dropbox
from flask import send_from_directory
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from dotenv import load_dotenv
import json
import logging
import requests
import traceback
import sys

# Load environment variables from .env file (for local development)
load_dotenv()

print("--- VERCEL DEPLOYMENT TEST: app.py started ---")

app = Flask(__name__)
DROPBOX_ACCESS_TOKEN = "sl.u.AF6mqFNAy-f98DiZ8Dxv39PbFzRqQdhV7jh_mz-NXS1Ul9qRlpK2Y-GxTH4Vf7Kh1Sr6A_vLCSVTpD8h9Z_raWFLgtxfx4EtHd-yCuLTvsbNqJqK1Y0coPgEfKV3ykbTL1X6Zsy_xUNLjZucpdqU6iOLWRrjgxRXkaQs7TVC0m9z0kky9HIyBfYZn5UfIRTpowC1ZyEO0R9PAaRyuXSDreuQyRDhbill2DLPzW64S0Ban95TOd8mkp228p_z6DHXle18TL_WLIIzle4a9VgWMXRV9xk92iyerTKKUT91sC5aDDWPjcKWNdUhxPmhUEn_E2sKVmc7-OcCjkXdEeID4CMozIXoJomYPz3yQbi1J5BKDOnbClAhQsXNmR5HOzorZW-KyvHIPyBYNwvYX44POrU4ohWfsq3uDYhCcwZJXYYnqG_pCiYf5gQyObouyBcFfpGKw8fjNSzE1VjlNrn8flREO_4HnE-nxgJa6VvJBkk_uo0dmfXT46QkYSwDtjlXP3ccvwabi3JBEGnUF-Ux5LvCfVBV8Xu-W4XYgz_Cm6NoXCwch-iXrCeHo-36KlGYyb1q4_iLDU-dwxc0TVU4yJIl3Kz5b3ZdlcgysC4SulFVn_rgDizIF5I-Y3-EmkwXyEj2JKheeKgTxF47P4Xu29m4qanWq4mf3ZYmgwEUe1jasCvrpjMUPurbQOTR_Op3N8igsPtZDbOW6f4zWbAVoweJAT7-fuPY3eLYyZzgvdgiXig2iKF7FtglsfwVXValwTor5V5HvzQMl9yznI7Zjva20acly_6HEV1Zt1mqVHaR0GCiMOReV1OmR_iJ8Tk7nxFkb64wD52U2erOTuPFqwe07OTizHPfP13cK1S_ETpyE6YWTqQGWWVWhe_I3ZDsDzhNekIcXPpaz4emAS-Eo5tU-Ux5YGGwj9r7jt58yKTGv22pBCVWhapsylJ4hL2Ftaq5iIihzf5GaXT3HSGN3qy_wpjTJziPSOH9QX72sKOaXZ5SVpXnBtjptGkP3-FXQDI7OggZjFOONzdQKFbkph3udx9BCkXByWvfpFtvl_gV4__WE0AfN9uQF74TW2BfSKw_bD3DmYF-jHMOiTmyWtukLBZ8-vOx3TgraBoXT_7x4a4pmK8PunD9bofeU2z9OYyV6PjiBoO8NmQiQE-Lz-3iYsLOyOwE1kXtcb9Ess4AQlayujSow4LS8GqQ0sAmRjaFshxtmmW0z9DDjgIfHbAXcYORKRyBKdY4XUBschY35uCSiCArKqrF6qNuj0do_M1PxOEoTMLf_7ItHFmex3e8bX1t24-dQwcObWv1EmMv_WomzeKMQikonkRLrMjksZLDhNBZBMvcmrwPFDGPgZwiYa910kWT-a2-X6LtwVVaaFoCqQ2QDbxScr2O2_g_5s3HzQu_5JqhehxkC9pZPm2C-pQcMLgsOWokiqrc9A_7p7BSCJlWNv23TlNl6M1EpTY"
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your_super_secret_fallback_key_CHANGE_ME')
logging.basicConfig(level=logging.DEBUG)

# Use /tmp for ephemeral storage on Vercel
app.config['UPLOAD_FOLDER'] = os.path.join('/tmp', 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

database_url = os.getenv('FIREBASE_DATABASE_URL')

try:
    service_account_info = {
        "type": os.getenv('FIREBASE_TYPE'),
        "project_id": os.getenv('FIREBASE_PROJECT_ID'),
        "private_key_id": os.getenv('FIREBASE_PRIVATE_KEY_ID'),
        "private_key": os.getenv('FIREBASE_PRIVATE_KEY').replace('\\n', '\n') if os.getenv('FIREBASE_PRIVATE_KEY') else None,
        "client_email": os.getenv('FIREBASE_CLIENT_EMAIL'),
        "client_id": os.getenv('FIREBASE_CLIENT_ID'),
        "auth_uri": os.getenv('FIREBASE_AUTH_URI'),
        "token_uri": os.getenv('FIREBASE_TOKEN_URI'),
        "auth_provider_x509_cert_url": os.getenv('FIREBASE_AUTH_PROVIDER_X509_CERT_URL'),
        "client_x509_cert_url": os.getenv('FIREBASE_CLIENT_X509_CERT_URL'),
        "universe_domain": os.getenv('FIREBASE_UNIVERSE_DOMAIN')
    }
    
    service_account_info = {k: v for k, v in service_account_info.items() if v is not None}

    cred = credentials.Certificate(service_account_info)
    initialize_app(cred, {
        'databaseURL': database_url
    })
    logging.info("Firebase initialized successfully from environment variables.")

except Exception as e:
    logging.error(f"Error initializing Firebase from environment variables: {e}")
    logging.error(traceback.format_exc())
    sys.exit(1)

# New routes to handle favicon requests properly
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/favicon.png')
def favicon_png():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.png', mimetype='image/png')

@app.route('/')
def login():
    if 'username' in session:
        return redirect(url_for('dashboard', username=session['username']))
    response = make_response(render_template('login.html'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/login_handler', methods=['POST'])
def login_handler():
    username = request.form['username']
    password = request.form['password']
    try:
        user_data = db.reference(f'users/{username}').get()

        if user_data:
            logging.debug(f"Retrieved user_data for {username}: {user_data}")
            if user_data.get('password') == password:
                session['username'] = username
                logging.info(f"User {username} logged in successfully.")
                return redirect(url_for('dashboard', username=username))
            else:
                logging.warning(f"Failed login attempt for {username}: Incorrect password.")
                flash('Invalid username or password')
                return redirect(url_for('login'))
        else:
            logging.warning(f"Failed login attempt: Username '{username}' not found.")
            flash('Invalid username or password')
            return redirect(url_for('login'))

    except Exception as e:
        logging.error(f"An unexpected error occurred in login_handler for user {username}: {e}")
        sys.stderr.write(traceback.format_exc() + '\n')
        flash('An unexpected error occurred during login. Please try again.')
        return redirect(url_for('login'))

@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/register_handler', methods=['POST'])
def register_handler():
    user_data = {
        'first_name': request.form['first_name'],
        'middle_name': request.form.get('middle_name', ''),
        'last_name': request.form['last_name'],
        'age': request.form['age'],
        'email': request.form['email'],
        'password': request.form['password']
    }
    username = request.form['username']
    ref = db.reference(f'users/{username}')
    if ref.get():
        return 'Username exists. <a href="/register">Try again</a>'
    ref.set(user_data)
    return render_template('registration_success.html')

@app.route('/dashboard/<username>')
def dashboard(username):
    if 'username' not in session or session['username'] != username:
        return redirect(url_for('login'))

    user_groups = db.reference(f'users/{username}/groups').get() or {}
    user_data = db.reference(f'users/{username}').get() or {}
    response = make_response(render_template(
        'dashboard.html',
        username=username,
        groups=user_groups,
        first_name=user_data.get('first_name', ''),
        middle_name=user_data.get('middle_name', ''),
        last_name=user_data.get('last_name', ''),
        age=user_data.get('age', ''),
        email=user_data.get('email', '')
    ))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    flash('Logged out successfully.')
    return redirect(url_for('login'))

@app.route('/create_group_handler/<username>', methods=['POST'])
def create_group_handler(username):
    group_name = request.form['group_name']
    group_id = request.form['group_id']

    group_ref = db.reference(f'groups/{group_id}')

    if group_ref.get():
        flash('Group ID already exists. Please try a different one.')
        return redirect(url_for('dashboard', username=username))

    group_ref.set({
        'group_name': group_name,
        'admin': username,
        'members': {
            username: {
                'role': 'admin', # Explicitly set primary role
                'roles': {'admin': True} # This is for custom roles, 'admin' can be a default custom role
            }
        },
        'custom_roles': {} # Renamed 'roles' to 'custom_roles' for clarity in Firebase structure
    })

    db.reference(f'users/{username}/groups/{group_id}').set({
        'group_name': group_name,
        'role': 'admin',
        'roles': {'admin': True} # Also store custom roles in user's group data
    })

    flash(f'Group \"{group_name}\" created successfully! You are the admin.')
    return redirect(url_for('dashboard', username=username))


@app.route('/join_group_handler/<username>', methods=['POST'])
def join_group_handler(username):
    group_id = request.form['group_id']
    group_ref = db.reference(f'groups/{group_id}')
    group_data = group_ref.get()

    if not group_data:
        flash('Group not found. Please check the Group ID.')
        return redirect(url_for('dashboard', username=username))

    members_ref = db.reference(f'groups/{group_id}/members')
    pending_ref = db.reference(f'groups/{group_id}/pending_requests')

    if members_ref.child(username).get():
        flash('You are already a member of this group.')
        return redirect(url_for('dashboard', username=username))

    if pending_ref.child(username).get():
        flash('You already have a pending request to join this group.')
        return redirect(url_for('dashboard', username=username))

    pending_ref.child(username).set({
        'username': username,
        'status': 'pending'
    })

    flash(f'Join request sent to "{group_data["group_name"]}". Please wait for admin approval.')
    return redirect(url_for('dashboard', username=username))

@app.route('/group_redirect/<username>/<group_id>')
def group_redirect(username, group_id):
    """
    Redirects users to the appropriate group page based on their role.
    This function has been updated to explicitly prevent caching of the redirect response.
    """
    logging.debug(f"Attempting to redirect user {username} for group {group_id}")
    user_group = db.reference(f'users/{username}/groups/{group_id}').get()

    if not user_group:
        flash('You are not part of this group.')
        return redirect(url_for('dashboard', username=username))

    if user_group.get('role') == 'admin':
        response = make_response(redirect(url_for('mainadmin', username=username, group_id=group_id)))
        # Add headers to prevent caching
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    else:
        return redirect(url_for('main', username=username, group_id=group_id))

@app.route('/mainadmin/<username>/<group_id>')
def mainadmin(username, group_id):
    logging.debug(f"Accessing mainadmin for user: {username}, group: {group_id}")
    group_ref = db.reference(f'groups/{group_id}')

    # --- Fetch Members Data ---
    members_data_raw = group_ref.child('members').get() or {}
    logging.debug(f"Raw members data from Firebase: {members_data_raw}")

    members = []
    if not isinstance(members_data_raw, dict):
        logging.error(f"members_data_raw is not a dictionary! Type: {type(members_data_raw)}, Value: {members_data_raw}")
        members_data_raw = {}

    for member_username, member_info in members_data_raw.items():
        logging.debug(f"Processing member: {member_username}, Info: {member_info}")
        primary_role = 'member'
        custom_roles = {}

        if isinstance(member_info, dict):
            primary_role = member_info.get('role', 'member')
            custom_roles = member_info.get('roles', {})
        elif isinstance(member_info, str):
            primary_role = member_info
            custom_roles = {member_info: True}
            logging.warning(f"Detected old member data structure for {member_username}. Converting: {member_info}")
        else:
            logging.error(f"Unexpected member data type for {member_username}: {type(member_info)} - {member_info}. Skipping.")
            continue

        members.append({
            'username': member_username,
            'primary_role': primary_role,
            'custom_roles': list(custom_roles.keys())
        })
    logging.debug(f"Processed members list for template: {members}")

    # --- Fetch Pending Requests ---
    pending_ref = group_ref.child('pending_requests')
    pending_requests_data = pending_ref.get() or {}
    pending_requests = list(pending_requests_data.keys())
    logging.debug(f"Pending requests: {pending_requests}")

    # --- Fetch Tasks Data ---
    tasks_ref = group_ref.child('tasks')
    tasks_data = tasks_ref.get() or {}
    logging.info(f"\n--- DEBUGGING TASKS IN mainadmin for user: {username}, group: {group_id} ---")
    logging.info(f"DEBUG: Raw tasks_data fetched from Firebase: {json.dumps(tasks_data, indent=2)}")

    tasks_this_week = []
    tasks_next_week = []
    completed_tasks = []
    
    # Calculate start of current week (Monday) and next week
    today = datetime.now()
    start_of_this_week = today - timedelta(days=today.weekday())
    start_of_this_week = start_of_this_week.replace(hour=0, minute=0, second=0, microsecond=0)
    
    start_of_next_week = start_of_this_week + timedelta(weeks=1)
    
    # Debugging the current time and week boundaries
    logging.info(f"DEBUG: Current Time (Server): {today.isoformat()}")
    logging.info(f"DEBUG: Start of This Week (Server): {start_of_this_week.isoformat()}")
    logging.info(f"DEBUG: Start of Next Week (Server): {start_of_next_week.isoformat()}")

    
    # Define week boundaries for categorization in mainadmin
    week_boundaries = {
        'this_week': (start_of_this_week, start_of_this_week + timedelta(weeks=1)),
        'next_week': (start_of_next_week, start_of_next_week + timedelta(weeks=1)),
    }
    # Add more week categories if needed, e.g., 'week_2', 'week_3' etc.
    for i in range(2, 5): # For week_2, week_3, week_4
        week_start = start_of_this_week + timedelta(weeks=i)
        week_boundaries[f'week_{i}'] = (week_start, week_start + timedelta(weeks=1))


    # Fetch all projects for the group
    projects_ref = group_ref.child('projects')
    projects_data = projects_ref.get() or {}
    project_lookup = {}
    for proj_id, proj in projects_data.items():
        project_lookup[proj_id] = {
            'project_name': proj.get('project_name', ''),
            'project_description': proj.get('description', '')
        }

    for task_id, task in tasks_data.items():
        if not isinstance(task, dict):
            logging.warning(f"Skipping malformed task data for task_id: {task_id}. Data was not a dictionary: {task}")
            continue

        # Attach project info if available
        project_name = ''
        project_description = ''
        if 'project_id' in task and task['project_id'] in project_lookup:
            project_name = project_lookup[task['project_id']]['project_name']
            project_description = project_lookup[task['project_id']]['project_description']

        # Robust week category detection
        week_category = task.get('week_category', '')
        if not week_category and 'week' in task:
            week_category = task['week']

        # Fallback: categorize by deadline date if no week info
        if not week_category:
            deadline_str = task.get('deadline_date') or task.get('deadline')
            if deadline_str:
                try:
                    deadline = datetime.fromisoformat(deadline_str)
                    today = datetime.now()
                    days_diff = (deadline.date() - today.date()).days
                    if days_diff < 0:
                        week_category = 'overdue'
                    elif days_diff <= 7:
                        week_category = 'this_week'
                    elif days_diff <= 14:
                        week_category = 'next_week'
                    else:
                        week_category = 'following_weeks'
                except Exception:
                    week_category = 'unknown'

        task_info = {
            'task_id': task_id,
            'task_name': task.get('task_name', 'No Name'),
            'description': task.get('description', ''),
            'assigned_to': task.get('assigned_to', 'N/A'),
            'priority': task.get('priority', 'Low'),
            'progress_reports': task.get('progress_reports', {}),
            'assigned_type': task.get('assigned_type', 'user'),
            'deadline': task.get('deadline', ''),
            'week_category': week_category,
            'project_name': project_name,
            'project_description': project_description
        }
        logging.info(f"DEBUG: Processing task_id: {task_id}, task_info: {json.dumps(task_info)}")

        if task.get('completed', False):
            completed_tasks.append(task_info)
            logging.info(f"DEBUG: Task {task_id} added to completed_tasks (completed: True).")
        else:
            # Check week category
            if week_category == 'this_week':
                tasks_this_week.append(task_info)
                logging.info(f"DEBUG: Task {task_id} added to tasks_this_week (week_category: this_week).")
            elif week_category == 'next_week':
                tasks_next_week.append(task_info)
                logging.info(f"DEBUG: Task {task_id} added to tasks_next_week (week_category: next_week).")
            elif week_category.startswith('week_'):
                # You can add more week buckets if needed
                pass
            elif week_category == 'overdue':
                # Optionally add to a separate overdue list
                pass
            elif week_category == 'following_weeks':
                # Optionally add to a following weeks list
                pass
            else:
                logging.info(f"DEBUG: Task {task_id} not categorized into this_week/next_week (week_category: {week_category}).")

    logging.info(f"DEBUG: Final tasks_this_week list: {json.dumps(tasks_this_week, indent=2)}")
    logging.info(f"DEBUG: Final tasks_next_week list: {json.dumps(tasks_next_week, indent=2)}")
    logging.info(f"DEBUG: Final completed_tasks list: {json.dumps(completed_tasks, indent=2)}")
    logging.info("------------------------------------------------------------------\n")
            
    # Sort tasks within categories (e.g., by priority)
    priority_order = {'high': 1, 'medium': 2, 'low': 3}
    tasks_this_week.sort(key=lambda x: priority_order.get(x.get('priority', 'Low').lower(), 4))
    tasks_next_week.sort(key=lambda x: priority_order.get(x.get('priority', 'Low').lower(), 4))
    completed_tasks.sort(key=lambda x: x.get('task_name', '')) # Example sort


    logging.debug(f"Tasks This Week: {tasks_this_week}")
    logging.debug(f"Tasks Next Week: {tasks_next_week}")
    logging.debug(f"Completed tasks: {completed_tasks}")


    # --- Get ALL Available Custom Roles for the Group ---
    custom_roles_ref = db.reference(f'groups/{group_id}/custom_roles')
    all_available_custom_roles_data = custom_roles_ref.get() or {}
    available_custom_roles_list = list(all_available_custom_roles_data.keys())
    logging.debug(f"Available custom roles list: {available_custom_roles_list}")

    # --- Get Chat Messages ---
    chat_ref = db.reference(f'groups/{group_id}/chat')
    chat_data = chat_ref.get() or {}
    logging.debug(f"Chat data: {chat_data}")

    messages = []
    sorted_chat_items = sorted(
        (item for item in chat_data.values() if isinstance(item, dict) and item.get('timestamp')),
        key=lambda x: x['timestamp']
    )

    for msg in sorted_chat_items:
        try:
            timestamp_dt = datetime.fromisoformat(msg['timestamp'])
            formatted_timestamp = timestamp_dt.strftime('%b %d, %I:%M %p')
        except ValueError:
            formatted_timestamp = msg['timestamp']
            logging.warning(f"Malformed timestamp in chat message for group {group_id}: {msg.get('timestamp')}")

        messages.append({
            'sender': msg.get('sender', 'Unknown'),
            'message': msg.get('text', ''),
            'timestamp': formatted_timestamp
        })
    logging.debug(f"Processed chat messages: {messages}")

    return render_template(
        'mainadmin.html',
        username=username,
        group_id=group_id,
        members=members,
        pending_requests=pending_requests,
        tasks_this_week=tasks_this_week, # Pass this data
        tasks_next_week=tasks_next_week, # Pass this data
        completed_tasks=completed_tasks,
        messages=messages,
        available_custom_roles=available_custom_roles_list # Use the new name here
    )

@app.route('/main/<username>/<group_id>')
def main(username, group_id):
    """
    Renders the main collaboration space for regular group members.
    Fetches tasks and other relevant group data from Firebase.
    """
    # Verify the user is logged in and part of the group
    if 'username' not in session or session['username'] != username:
        flash('Please log in to view this page.')
        return redirect(url_for('login'))

    user_group = db.reference(f'users/{username}/groups/{group_id}').get()
    if not user_group:
        flash('You are not a member of this group.')
        return redirect(url_for('dashboard', username=username))

    logging.debug(f"Accessing main for user: {username}, group: {group_id}")
    group_ref = db.reference(f'groups/{group_id}')

    # Fetch tasks for the main view
    tasks_ref = group_ref.child('tasks')
    tasks_data = tasks_ref.get() or {}
    logging.info(f"\n--- DEBUGGING TASKS IN mainadmin for user: {username}, group: {group_id} ---")
    logging.info(f"DEBUG: Raw tasks_data fetched from Firebase: {json.dumps(tasks_data, indent=2)}")

    tasks_this_week = []
    tasks_next_week = []
    completed_tasks = []
    
    # Calculate start of current week (Monday) and next week
    today = datetime.now()
    start_of_this_week = today - timedelta(days=today.weekday())
    start_of_this_week = start_of_this_week.replace(hour=0, minute=0, second=0, microsecond=0)
    
    start_of_next_week = start_of_this_week + timedelta(weeks=1)
    
    # Debugging the current time and week boundaries
    logging.info(f"DEBUG: Current Time (Server): {today.isoformat()}")
    logging.info(f"DEBUG: Start of This Week (Server): {start_of_this_week.isoformat()}")
    logging.info(f"DEBUG: Start of Next Week (Server): {start_of_next_week.isoformat()}")

    
    # Define week boundaries for categorization in mainadmin
    week_boundaries = {
        'this_week': (start_of_this_week, start_of_this_week + timedelta(weeks=1)),
        'next_week': (start_of_next_week, start_of_next_week + timedelta(weeks=1)),
    }
    # Add more week categories if needed, e.g., 'week_2', 'week_3' etc.
    for i in range(2, 5): # For week_2, week_3, week_4
        week_start = start_of_this_week + timedelta(weeks=i)
        week_boundaries[f'week_{i}'] = (week_start, week_start + timedelta(weeks=1))


    # Fetch all projects for the group
    projects_ref = group_ref.child('projects')
    projects_data = projects_ref.get() or {}
    project_lookup = {}
    for proj_id, proj in projects_data.items():
        project_lookup[proj_id] = {
            'project_name': proj.get('project_name', ''),
            'project_description': proj.get('description', '')
        }

    for task_id, task in tasks_data.items():
        if not isinstance(task, dict):
            logging.warning(f"Skipping malformed task data for task_id: {task_id}. Data was not a dictionary: {task}")
            continue

        # Attach project info if available
        project_name = ''
        project_description = ''
        if 'project_id' in task and task['project_id'] in project_lookup:
            project_name = project_lookup[task['project_id']]['project_name']
            project_description = project_lookup[task['project_id']]['project_description']

        task_info = {
            'task_id': task_id,
            'task_name': task.get('task_name', 'No Name'),
            'description': task.get('description', ''),
            'assigned_to': task.get('assigned_to', 'N/A'),
            'priority': task.get('priority', 'Low'),
            'progress_reports': task.get('progress_reports', {}),
            'assigned_type': task.get('assigned_type', 'user'),
            'deadline': task.get('deadline', ''),
            'week_category': task.get('week_category', ''),
            'project_name': project_name,
            'project_description': project_description
        }
        logging.info(f"DEBUG: Processing task_id: {task_id}, task_info: {json.dumps(task_info)}")
        
        if task.get('completed', False):
            completed_tasks.append(task_info)
            logging.info(f"DEBUG: Task {task_id} added to completed_tasks (completed: True).")
        else:
            # Check week category
            if task_info['week_category'] == 'this_week':
                tasks_this_week.append(task_info)
                logging.info(f"DEBUG: Task {task_id} added to tasks_this_week (week_category: this_week).")
            elif task_info['week_category'] == 'next_week':
                tasks_next_week.append(task_info)
                logging.info(f"DEBUG: Task {task_id} added to tasks_next_week (week_category: next_week).")
            else:
                logging.info(f"DEBUG: Task {task_id} not categorized into this_week/next_week (week_category: {task_info['week_category']}).")

    logging.info(f"DEBUG: Final tasks_this_week list: {json.dumps(tasks_this_week, indent=2)}")
    logging.info(f"DEBUG: Final tasks_next_week list: {json.dumps(tasks_next_week, indent=2)}")
    logging.info(f"DEBUG: Final completed_tasks list: {json.dumps(completed_tasks, indent=2)}")
    logging.info("------------------------------------------------------------------\n")
            
    # Sort tasks within categories (e.g., by priority)
    priority_order = {'high': 1, 'medium': 2, 'low': 3}
    tasks_this_week.sort(key=lambda x: priority_order.get(x.get('priority', 'Low').lower(), 4))
    tasks_next_week.sort(key=lambda x: priority_order.get(x.get('priority', 'Low').lower(), 4))
    completed_tasks.sort(key=lambda x: x.get('task_name', '')) # Example sort


    logging.debug(f"Tasks This Week: {tasks_this_week}")
    logging.debug(f"Tasks Next Week: {tasks_next_week}")
    logging.debug(f"Completed tasks: {completed_tasks}")

    return render_template('main.html',
                           username=username,
                           group_id=group_id,
                           tasks_this_week=tasks_this_week, # Pass this data
                           tasks_next_week=tasks_next_week, # Pass this data
                           completed_tasks=completed_tasks,)

@app.route('/get_group_members_with_roles/<group_id>', methods=['GET'])
def get_group_members_with_roles(group_id):
    try:
        # Fetch group members
        members_ref = db.reference(f'groups/{group_id}/members')
        members_data = members_ref.get() or {}

        members_list = []
        for username, member_info in members_data.items():
            # Ensure roles exist and are handled correctly
            primary_role = member_info.get('primary_role', 'member') # Default to 'member'
            custom_roles_dict = member_info.get('roles', {}) # 'roles' is where custom roles are stored
            
            # Convert custom_roles_dict to a list of role names
            custom_roles = [role_name for role_name, is_assigned in custom_roles_dict.items() if is_assigned]

            members_list.append({
                'username': username,
                'primary_role': primary_role,
                'custom_roles': custom_roles
            })

        # Fetch available custom roles for the group
        custom_roles_ref = db.reference(f'groups/{group_id}/custom_roles')
        available_custom_roles_dict = custom_roles_ref.get() or {}
        available_custom_roles = [role_name for role_name, is_active in available_custom_roles_dict.items() if is_active]


        return jsonify({
            'success': True,
            'members': members_list,
            'available_custom_roles': available_custom_roles
        }), 200

    except Exception as e:
        logging.error(f"Error fetching group members and roles for group {group_id}: {e}")
        traceback.print_exc() # Print full traceback to console for debugging
        return jsonify({'success': False, 'message': f'Error fetching group members and roles: {str(e)}'}), 500


@app.route('/create_role/<group_id>', methods=['POST'])
def create_role(group_id):
    try:
        data = request.get_json()
        if not data or 'role_name' not in data:
            return jsonify({'success': False, 'message': 'Role name is required.'}), 400
            
        role_name = data['role_name'].strip()
        if not role_name:
            return jsonify({'success': False, 'message': 'Role name cannot be empty.'}), 400

        ref = db.reference(f'groups/{group_id}/custom_roles') 
        
        # Check if role already exists
        if ref.child(role_name).get():
            return jsonify({'success': False, 'message': f'Role "{role_name}" already exists.'}), 409 # 409 Conflict
        
        ref.child(role_name).set(True)  # Store role as key with a boolean value

        return jsonify({
            'success': True,
            'message': f'Role "{role_name}" created successfully!'
        }), 201 # 201 Created

    except Exception as e:
        logging.error(f"Error creating role for group {group_id}: {e}")
        traceback.print_exc() # Print full traceback to console
        return jsonify({'success': False, 'message': f'Error creating role: {str(e)}'}), 500

@app.route('/delete_role/<group_id>', methods=['POST'])
def delete_role(group_id):
    try:
        data = request.get_json()
        if not data or 'role_name' not in data:
            return jsonify({'success': False, 'message': 'Role name is required.'}), 400
        
        role_name = data['role_name'].strip()
        if not role_name:
            return jsonify({'success': False, 'message': 'Role name cannot be empty.'}), 400

        # Check if the role exists
        role_ref = db.reference(f'groups/{group_id}/custom_roles/{role_name}')
        if not role_ref.get():
            return jsonify({'success': False, 'message': f'Role "{role_name}" does not exist.'}), 404

        # Remove the role from the group's custom_roles
        role_ref.delete()

        # Iterate through all members and remove this role if they have it
        members_ref = db.reference(f'groups/{group_id}/members')
        members_data = members_ref.get() or {}
        
        for username, member_info in members_data.items():
            if 'roles' in member_info and role_name in member_info['roles']:
                db.reference(f'groups/{group_id}/members/{username}/roles/{role_name}').delete()
            
            # Also update the user's personal group entry
            user_group_roles_ref = db.reference(f'users/{username}/groups/{group_id}/roles')
            user_roles_data = user_group_roles_ref.get() or {}
            if role_name in user_roles_data:
                user_group_roles_ref.child(role_name).delete()


        return jsonify({
            'success': True,
            'message': f'Role "{role_name}" removed successfully from group and all members.'
        }), 200

    except Exception as e:
        logging.error(f"Error deleting role for group {group_id}: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error deleting role: {str(e)}'}), 500

# NEW: Endpoint for creating a project with multiple tasks
@app.route('/create_project_with_tasks/<group_id>', methods=['POST'])
def create_project_with_tasks(group_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided.'}), 400

        project_name = data.get('project_name')
        project_description = data.get('project_description', '')
        tasks = data.get('tasks', [])

        if not project_name:
            return jsonify({'success': False, 'message': 'Project name is required.'}), 400
        if not tasks:
            return jsonify({'success': False, 'message': 'At least one task is required for the project.'}), 400

        project_ref = db.reference(f'groups/{group_id}/projects').push() # Create a new project entry
        project_id = project_ref.key

        project_ref.set({
            'project_name': project_name,
            'description': project_description,
            'created_at': datetime.now().isoformat(),
            'tasks_count': len(tasks)
        })

        tasks_ref = db.reference(f'groups/{group_id}/tasks')
        for task_data in tasks:
            task_name = task_data.get('task_name')
            description = task_data.get('description', '')
            assigned_to_type = task_data.get('assigned_to_type', 'user')
            assigned_to = task_data.get('assigned_to')
            priority = task_data.get('priority', 'Low')
            week_category = task_data.get('week_category', 'upcoming') # Default to 'upcoming'
            
            # Determine deadline based on week_category for consistent storage
            deadline_date = None
            today = datetime.now()
            if week_category == 'this_week':
                # Monday of current week + 6 days (to make it Sunday of current week)
                deadline_date = today - timedelta(days=today.weekday()) + timedelta(days=6)
            elif week_category == 'next_week':
                # Monday of next week + 6 days
                deadline_date = today - timedelta(days=today.weekday()) + timedelta(weeks=1, days=6)
            elif week_category.startswith('week_'):
                try:
                    week_num = int(week_category.replace('week_', ''))
                    # Monday of that specific week + 6 days
                    deadline_date = today - timedelta(days=today.weekday()) + timedelta(weeks=week_num -1, days=6)
                except ValueError:
                    deadline_date = None # Fallback if week_category is malformed
            
            # Parse start and deadline dates
            start_date_str = task_data.get('start_date')
            deadline_date_str = task_data.get('deadline_date')
            
            try:
                start_date = datetime.fromisoformat(start_date_str) if start_date_str else None
                deadline_date = datetime.fromisoformat(deadline_date_str) if deadline_date_str else None
            except ValueError as e:
                logging.error(f"Invalid date format in task data: {e}")
                return jsonify({'success': False, 'message': f'Invalid date format: {e}'}), 400

            task_entry = {
                'project_id': project_id, # Link task to project
                'task_name': task_name,
                'description': description,
                'assigned_to_type': assigned_to_type,
                'assigned_to': assigned_to,
                'priority': priority,
                'completed': False,
                'progress_reports': {},
                'start_date': start_date.isoformat() if start_date else '',
                'deadline_date': deadline_date.isoformat() if deadline_date else '',
                'week_category': get_week_category(start_date_str, deadline_date_str)
            }
            
            new_task_ref = tasks_ref.push(task_entry)
            new_task_id = new_task_ref.key

            # Notification logic for each task
            if assigned_to_type == 'everyone':
                members_data = db.reference(f'groups/{group_id}/members').get() or {}
                for member_username in members_data.keys():
                    db.reference(f'users/{member_username}/notifications').push().set({
                        'message': f'New task "{task_name}" from project "{project_name}" assigned to everyone in group {group_id}.',
                        'group_id': group_id,
                        'task_id': new_task_id,
                        'timestamp': datetime.now().isoformat(),
                        'read': False
                    })
            elif assigned_to_type == 'user':
                db.reference(f'users/{assigned_to}/notifications').push().set({
                    'message': f'New task "{task_name}" from project "{project_name}" assigned to you in group {group_id}.',
                    'group_id': group_id,
                    'task_id': new_task_id,
                    'timestamp': datetime.now().isoformat(),
                    'read': False
                })
            elif assigned_to_type == 'role':
                # Find all users with this role and notify them
                members_data = db.reference(f'groups/{group_id}/members').get() or {}
                for member_username, member_info in members_data.items():
                    user_custom_roles = member_info.get('roles', {})
                    if assigned_to in user_custom_roles: # Check if the user has the assigned role
                        db.reference(f'users/{member_username}/notifications').push().set({
                            'message': f'New task "{task_name}" from project "{project_name}" assigned to your role "{assigned_to}" in group {group_id}.',
                            'group_id': group_id,
                            'task_id': new_task_id,
                            'timestamp': datetime.now().isoformat(),
                            'read': False
                        })

        return jsonify({'success': True, 'message': f'Project "{project_name}" and its tasks created successfully!'}), 201

    except Exception as e:
        logging.error(f"Error creating project with tasks for group {group_id}: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error creating project: {str(e)}'}), 500

@app.route('/get_all_tasks/<group_id>', methods=['GET'])
def get_all_tasks(group_id):
    try:
        group_ref = db.reference(f'groups/{group_id}')
        tasks_ref = group_ref.child('tasks')
        tasks_data = tasks_ref.get() or {}
        projects_ref = group_ref.child('projects')
        projects_data = projects_ref.get() or {}
        project_lookup = {proj_id: {
            'project_name': proj.get('project_name', ''),
            'project_description': proj.get('description', '')
        } for proj_id, proj in projects_data.items()}

        tasks_this_week = []
        tasks_next_week = []
        completed_tasks = []
        tasks_no_deadline = []

        for task_id, task in tasks_data.items():
            if not isinstance(task, dict):
                continue
            project_name = ''
            project_description = ''
            if 'project_id' in task and task['project_id'] in project_lookup:
                project_name = project_lookup[task['project_id']]['project_name']
                project_description = project_lookup[task['project_id']]['project_description']

            week_category = task.get('week_category', '')
            if not week_category and 'week' in task:
                week_category = task['week']
            if not week_category:
                deadline_str = task.get('deadline_date') or task.get('deadline')
                if deadline_str:
                    try:
                        deadline = datetime.fromisoformat(deadline_str)
                        today = datetime.now()
                        days_diff = (deadline.date() - today.date()).days
                        if days_diff < 0:
                            week_category = 'overdue'
                        elif days_diff <= 7:
                            week_category = 'this_week'
                        elif days_diff <= 14:
                            week_category = 'next_week'
                        else:
                            week_category = 'following_weeks'
                    except Exception:
                        week_category = 'unknown'
                else:
                    week_category = 'no_deadline'

            task_info = {
                'task_id': task_id,
                'task_name': task.get('task_name', 'No Name'),
                'description': task.get('description', ''),
                'assigned_to': task.get('assigned_to', 'N/A'),
                'priority': task.get('priority', 'Low'),
                'progress_reports': task.get('progress_reports', {}),
                'assigned_type': task.get('assigned_type', 'user'),
                'week_category': week_category,
                'project_name': project_name,
                'project_description': project_description
            }

            if task.get('completed', False):
                completed_tasks.append(task_info)
            else:
                if week_category == 'this_week':
                    tasks_this_week.append(task_info)
                elif week_category == 'next_week':
                    tasks_next_week.append(task_info)
                elif week_category == 'no_deadline':
                    tasks_no_deadline.append(task_info)
                # Add more categories as needed

        priority_order = {'high': 1, 'medium': 2, 'low': 3}
        tasks_this_week.sort(key=lambda x: priority_order.get(x.get('priority', 'Low').lower(), 4))
        tasks_next_week.sort(key=lambda x: priority_order.get(x.get('priority', 'Low').lower(), 4))
        completed_tasks.sort(key=lambda x: x.get('task_name', ''))
        tasks_no_deadline.sort(key=lambda x: x.get('task_name', ''))

        return jsonify({
            'success': True,
            'tasks_this_week': tasks_this_week,
            'tasks_next_week': tasks_next_week,
            'completed_tasks': completed_tasks,
            'tasks_no_deadline': tasks_no_deadline
        })
    except Exception as e:
        logging.error(f"Error fetching all tasks for group {group_id}: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error fetching tasks: {str(e)}'}), 500

@app.route('/assign_existing_task/<group_id>', methods=['POST'])
def assign_existing_task(group_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided.'}), 400

        task_id = data.get('task_id')
        assigned_to_type = data.get('assigned_to_type')
        assigned_to = data.get('assigned_to')

        if not task_id or not assigned_to_type or not assigned_to:
            return jsonify({'success': False, 'message': 'Task ID, assignment type, and assignee are required.'}), 400

        task_ref = db.reference(f'groups/{group_id}/tasks/{task_id}')
        current_task_data = task_ref.get()

        if not current_task_data:
            return jsonify({'success': False, 'message': 'Task not found.'}), 404
        
        # Ensure current_task_data is a dictionary, default to empty dict if not
        if not isinstance(current_task_data, dict):
            logging.warning(f"Task data for {task_id} in group {group_id} is not a dictionary. Value: {current_task_data}. Defaulting to empty dict.")
            current_task_data = {}

        # Update assignment details
        task_ref.update({
            'assigned_to_type': assigned_to_type,
            'assigned_to': assigned_to,
            'completed': False # Re-open task if it was completed and re-assigned
        })

        task_name = current_task_data.get('task_name', 'Unnamed Task')
        if assigned_to_type == 'everyone':
            members_data = db.reference(f'groups/{group_id}/members').get() or {}
            for member_username in members_data.keys():
                db.reference(f'users/{member_username}/notifications').push().set({
                    'message': f'Task "{task_name}" has been reassigned to everyone in group {group_id}.',
                    'group_id': group_id,
                    'task_id': task_id,
                    'timestamp': datetime.now().isoformat(),
                    'read': False
                })
        elif assigned_to_type == 'user':
            db.reference(f'users/{assigned_to}/notifications').push().set({
                'message': f'Task "{task_name}" has been reassigned to you in group {group_id}.',
                'group_id': group_id,
                'task_id': task_id,
                'timestamp': datetime.now().isoformat(),
                'read': False
            })
        elif assigned_to_type == 'role':
            members_data = db.reference(f'groups/{group_id}/members').get() or {}
            for member_username, member_info in members_data.items():
                user_custom_roles = member_info.get('roles', {})
                if assigned_to in user_custom_roles:
                    db.reference(f'users/{member_username}/notifications').push().set({
                        'message': f'Task "{task_name}" has been reassigned to your role "{assigned_to}" in group {group_id}.',
                        'group_id': group_id,
                        'task_id': task_id,
                        'timestamp': datetime.now().isoformat(),
                        'read': False
                    })

        return jsonify({'success': True, 'message': f'Task "{task_name}" reassigned successfully!'})

    except Exception as e:
        logging.error(f"Error assigning existing task for group {group_id}: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error assigning existing task: {str(e)}'}), 500

@app.route('/get_messages/<group_id>') # Corrected route path to match fetch
def get_messages(group_id):
    chat_ref = db.reference(f'groups/{group_id}/chat')
    chat_data = chat_ref.get() or {}

    messages = []

    sorted_chat_data = sorted(chat_data.items()) # Sort by Firebase push key

    for message_id, message_data in sorted_chat_data:
        if isinstance(message_data, dict):
            messages.append({
                'sender': message_data.get('sender', 'Unknown'),
                'message': message_data.get('text', ''),
                'timestamp': message_data.get('timestamp', '')
            })
    return jsonify({'messages': messages})

@app.route('/send_message/<group_id>', methods=['POST'])
def send_message(group_id):
    # Check if the request body is JSON
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Request must be JSON'}), 400

    data = request.get_json()
    username = data.get('sender') # Changed from 'username' to 'sender' to match JS
    message = data.get('text')    # Changed from 'message' to 'text' to match JS

    if not username or not message:
        return jsonify({'success': False, 'message': 'Sender and text are required'}), 400

    chat_ref = db.reference(f'groups/{group_id}/chat').push()
    chat_ref.set({
        'sender': username,
        'text': message,
        'timestamp': datetime.now().isoformat()
    })
    return jsonify({'success': True, 'message': 'Message sent successfully'})

@app.route('/get_pending_requests/<string:group_id>')
def get_pending_requests(group_id):
    """
    Endpoint to get all pending join requests for a group.
    """
    try:
        pending_requests_ref = db.reference(f'groups/{group_id}/pending_requests')
        pending_requests_data = pending_requests_ref.get() or {}
        
        # Format the data into a list of objects with a consistent structure
        pending_requests_list = [
            {'username': username, **info}
            for username, info in pending_requests_data.items()
        ]
        
        return jsonify({'success': True, 'pending_requests': pending_requests_list})
    
    except Exception as e:
        logging.error(f"Error getting pending requests for group {group_id}: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Error getting pending requests.'}), 500


@app.route('/approve_request/<string:group_id>', methods=['POST'])
def approve_request(group_id):
    """
    Endpoint for an admin to approve a pending join request.
    
    It expects a JSON payload with 'username' of the user to be approved.
    """
    try:
        data = request.get_json()
        username = data.get('username')
        
        if not username:
            return jsonify({'success': False, 'message': 'Missing username.'}), 400

        group_ref = db.reference(f'groups/{group_id}')
        
        # Get the pending user's data
        pending_user_ref = group_ref.child('pending_requests').child(username)
        pending_user_data = pending_user_ref.get()
        
        if not pending_user_data:
            return jsonify({'success': False, 'message': 'User not found in pending requests.'}), 404

        # Move the user from pending_requests to members
        members_ref = group_ref.child('members').child(username)
        members_ref.set(pending_user_data)
        
        # Add the group to the user's list of groups
        user_group_ref = db.reference(f'users/{username}/groups/{group_id}')
        user_group_ref.set({
            'group_id': group_id,
            'group_name': pending_user_data.get('group_name'), # Assuming group_name is in pending data
            'role': 'member'
        })
        
        # Remove the user from the pending_requests
        pending_user_ref.delete()
        
        logging.info(f"Approved join request for user '{username}' in group '{group_id}'")
        
        return jsonify({'success': True, 'message': 'User approved successfully.'})
        
    except Exception as e:
        logging.error(f"Error approving request for user {username} in group {group_id}: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Error approving request.'}), 500

@app.route('/deny_request/<string:group_id>', methods=['POST'])
def deny_request(group_id):
    """
    Endpoint for an admin to deny a pending join request.
    
    It expects a JSON payload with 'username' of the user to be denied.
    """
    try:
        data = request.get_json()
        username = data.get('username')
        
        if not username:
            return jsonify({'success': False, 'message': 'Missing username.'}), 400

        # Remove the user from the pending_requests
        pending_user_ref = db.reference(f'groups/{group_id}/pending_requests/{username}')
        if pending_user_ref.get() is None:
            return jsonify({'success': False, 'message': 'User not found in pending requests.'}), 404

        pending_user_ref.delete()
        
        logging.info(f"Denied join request for user '{username}' in group '{group_id}'")
        
        return jsonify({'success': True, 'message': 'User request denied.'})
        
    except Exception as e:
        logging.error(f"Error denying request for user {username} in group {group_id}: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Error denying request.'}), 500


@app.route('/get_notifications/<username>')
def get_notifications(username):
    notifications_ref = db.reference(f'users/{username}/notifications')
    notifications_data = notifications_ref.get() or {}
    
    # Convert Firebase dict to a list of notifications, adding the notification key
    notifications = [
        {**notif_data, 'id': notif_id}
        for notif_id, notif_data in notifications_data.items() if isinstance(notif_data, dict)
    ]
    
    # Sort by timestamp, newest first
    notifications.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

    return jsonify(notifications)

@app.route('/mark_notification_read/<username>/<notification_id>', methods=['POST'])
def mark_notification_read(username, notification_id):
    try:
        notification_ref = db.reference(f'users/{username}/notifications/{notification_id}')
        notification_ref.update({'read': True})
        return jsonify({'success': True})
    except Exception as e:
        logging.error(f"Error marking notification {notification_id} as read for user {username}: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/mark_task_completed/<group_id>/<task_id>', methods=['POST'])
def mark_task_completed(group_id, task_id):
    try:
        task_ref = db.reference(f'groups/{group_id}/tasks/{task_id}')
        task_ref.update({'completed': True})

        # Get task details for notification
        task_data = task_ref.get()
        task_name = task_data.get('task_name', 'Unnamed Task')
        assigned_to = task_data.get('assigned_to', '')
        
        # Notify the assigned user if it's a user, not a role or everyone
        if task_data.get('assigned_to_type') == 'user' and assigned_to:
            db.reference(f'users/{assigned_to}/notifications').push().set({
                'message': f'Task "{task_name}" has been marked as completed by an admin.',
                'group_id': group_id,
                'task_id': task_id,
                'timestamp': datetime.now().isoformat(),
                'read': False
            })

        return jsonify({'success': True, 'message': f'Task {task_id} marked as completed.'})
    except Exception as e:
        logging.error(f"Error marking task {task_id} as completed: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'An internal server error occurred.'}), 500

@app.route('/delete_task/<group_id>/<task_id>', methods=['POST'])
def delete_task(group_id, task_id):
    try:
        task_ref = db.reference(f'groups/{group_id}/tasks/{task_id}')
        if not task_ref.get():
            return jsonify({'success': False, 'message': 'Task not found.'}), 404
        
        task_ref.delete()
        return jsonify({'success': True, 'message': f'Task {task_id} deleted successfully.'})
    except Exception as e:
        logging.error(f"Error deleting task {task_id}: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'An internal server error occurred.'}), 500

@app.route('/update_roles/<group_id>', methods=['POST'])
def update_roles(group_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No updates data provided.'}), 400

        # The 'data' variable now directly contains the updates dictionary for all users
        # For example: {'username1': {'primary_role': 'admin', ...}, 'username2': {...}}

        if not isinstance(data, dict):
            return jsonify({'success': False, 'message': 'Invalid data format. Expected a dictionary of user updates.'}), 400

        # Iterate through each user's updates in the received data
        for username, updates in data.items():
            member_ref = db.reference(f'groups/{group_id}/members/{username}')
            user_group_ref = db.reference(f'users/{username}/groups/{group_id}')

            current_member_info = member_ref.get() or {}
            current_user_group_info = user_group_ref.get() or {}

            # Update primary role if provided
            if 'primary_role' in updates:
                new_primary_role = updates['primary_role']
                member_ref.update({'primary_role': new_primary_role})
                user_group_ref.update({'primary_role': new_primary_role})
                logging.info(f"Updated primary role for {username} in group {group_id} to {new_primary_role}")

            # Update custom roles
            custom_roles_to_assign = updates.get('custom_roles_to_assign', [])
            custom_roles_to_unassign = updates.get('custom_roles_to_unassign', [])

            # Assign roles
            for role_name in custom_roles_to_assign:
                # Check if the role exists as an available custom role
                available_role_ref = db.reference(f'groups/{group_id}/custom_roles/{role_name}')
                if available_role_ref.get(): # Check if it's a valid custom role
                    member_ref.child(f'roles/{role_name}').set(True)
                    user_group_ref.child(f'roles/{role_name}').set(True)
                    logging.info(f"Assigned custom role '{role_name}' to {username} in group {group_id}")
                else:
                    logging.warning(f"Attempted to assign non-existent custom role '{role_name}' to {username}")

            # Unassign roles
            for role_name in custom_roles_to_unassign:
                member_ref.child(f'roles/{role_name}').delete()
                user_group_ref.child(f'roles/{role_name}').delete()
                logging.info(f"Unassigned custom role '{role_name}' from {username} in group {group_id}")

        return jsonify({
            'success': True,
            'message': 'Roles updated successfully for all specified members.'
        }), 200

    except Exception as e:
        logging.error(f"Error updating roles for group {group_id}: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Failed to update roles: {str(e)}'}), 500

@app.route('/update_task_details/<group_id>/<task_id>', methods=['POST'])
def update_task_details(group_id, task_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided.'}), 400

        # If we're updating dates, validate them and recalculate week category
        start_date = data.get('start_date')
        deadline_date = data.get('deadline_date')

        if start_date or deadline_date:
            # Get current task data to merge with new dates
            task_ref = db.reference(f'groups/{group_id}/tasks/{task_id}')
            current_task = task_ref.get()
            if not current_task:
                return jsonify({'success': False, 'message': 'Task not found.'}), 404

            # Use existing dates if not being updated
            start_date = start_date or current_task.get('start_date', '')
            deadline_date = deadline_date or current_task.get('deadline_date', '')

            try:
                # Validate date formats
                if start_date:
                    datetime.fromisoformat(start_date)
                if deadline_date:
                    datetime.fromisoformat(deadline_date)
            except ValueError as e:
                return jsonify({'success': False, 'message': f'Invalid date format: {e}'}), 400

            # Calculate new week category based on dates
            data['week_category'] = get_week_category(start_date, deadline_date)

        task_ref = db.reference(f'groups/{group_id}/tasks/{task_id}')
        task_ref.update(data)
        
        return jsonify({
            'success': True, 
            'message': 'Task details updated successfully.',
            'week_category': data.get('week_category')
        })
    except Exception as e:
        logging.error(f"Error updating task {task_id}: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'An internal server error occurred.'}), 500


@app.route('/get_member_roles/<group_id>/<member_username>', methods=['GET'])
def get_member_roles(group_id, member_username):
    try:
        member_roles_ref = db.reference(f'groups/{group_id}/members/{member_username}/roles')
        member_roles = member_roles_ref.get() or {}
        return jsonify({'success': True, 'roles': list(member_roles.keys())})
    except Exception as e:
        logging.error(f"Error fetching roles for {member_username} in group {group_id}: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'An internal server error occurred.'}), 500

@app.route('/upload_file_handler/<group_id>', methods=['POST'])
def upload_file_handler(group_id):
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No selected file'}), 400

    if file:
        filename = secure_filename(file.filename)
        # For this temporary deployment, we save to /tmp
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        try:
            file.save(file_path)
            
            file_info = {
                'filename': filename,
                'uploader': request.form.get('username', 'Unknown'),
                'timestamp': datetime.now().isoformat(),
                'type': file.content_type
            }
            # Save file info to Firebase
            db.reference(f'groups/{group_id}/uploaded_files').push().set(file_info)
            return jsonify({'success': True, 'message': 'File uploaded successfully!', 'filename': filename})
        except Exception as e:
            logging.error(f"Error saving file: {e}")
            return jsonify({'success': False, 'message': f'Error saving file: {str(e)}'}), 500

@app.route('/get_uploaded_files/<group_id>')
def get_uploaded_files(group_id):
    files_ref = db.reference(f'groups/{group_id}/uploaded_files')
    files_data = files_ref.get() or {}
    
    files_list = []
    for file_id, file_info in files_data.items():
        if isinstance(file_info, dict):
            files_list.append(file_info)
    
    # Sort files by timestamp, newest first
    files_list.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    return jsonify(files_list)


@app.route('/download/<filename>')
def download_file(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    else:
        return 'File not found.', 404

def get_week_category(start_date_str, deadline_str):
    # Use deadline_str for categorization, fallback to start_date_str if needed
    date_str = deadline_str or start_date_str
    if not date_str:
        return 'no_deadline'
    try:
        date_obj = datetime.fromisoformat(date_str)
        today = datetime.now()
        time_difference = (date_obj.date() - today.date()).days
        if time_difference < 0:
            return 'overdue'
        elif time_difference <= 7:
            return 'this_week'
        elif time_difference <= 14:
            return 'next_week'
        else:
            return 'following_weeks'
    except Exception:
        return 'invalid_date'

# --- Backend Routes ---

# This is the route you were missing, causing the 404 error
@app.route('/get_tasks/<group_id>', methods=['GET'])
def get_tasks(group_id):
    try:
        logging.info(f"Fetching all tasks for group {group_id}")
        tasks_ref = db.reference(f'groups/{group_id}/tasks')
        all_tasks = tasks_ref.get()

        if not all_tasks:
            logging.info(f"No tasks found for group {group_id}.")
            return jsonify({
                "tasks_this_week": [],
                "tasks_next_week": [],
                "tasks_following_weeks": [],
                "completed_tasks": []
            }), 200

        tasks_this_week = []
        tasks_next_week = []
        tasks_following_weeks = []
        completed_tasks = []

        # Calculate week boundaries for debugging
        today = datetime.now()
        start_of_this_week = today - timedelta(days=today.weekday())
        start_of_this_week = start_of_this_week.replace(hour=0, minute=0, second=0, microsecond=0)
        
        logging.debug(f"Processing tasks with reference date: today={today.isoformat()}, start_of_this_week={start_of_this_week.isoformat()}")

        for task_id, task_data in all_tasks.items():
            # Add task_id to the task data for front-end use
            task_data['task_id'] = task_id

            # Ensure file_url is present if file_path exists
            if 'file_path' in task_data:
                task_data['file_url'] = f"/static/uploads/{task_data['file_name']}" if 'file_name' in task_data else task_data['file_path']

            # Handle completed tasks
            if task_data.get('status') == 'completed' or task_data.get('completed', False):
                completed_tasks.append(task_data)
                continue

            # Get start and deadline dates
            start_date = task_data.get('start_date')
            deadline_date = task_data.get('deadline_date')

            logging.debug(f"Task {task_id} dates: start_date={start_date}, deadline_date={deadline_date}")

            # Categorize tasks by week
            week_category = get_week_category(start_date, deadline_date)
            logging.debug(f"Task {task_id} categorized as: {week_category}")

            if week_category == 'this_week' or week_category == 'overdue':
                tasks_this_week.append(task_data)
            elif week_category == 'next_week':
                tasks_next_week.append(task_data)
            elif week_category == 'following_weeks':
                tasks_following_weeks.append(task_data)

        # Sort tasks by deadline within each category
        for task_list in [tasks_this_week, tasks_next_week, tasks_following_weeks]:
            task_list.sort(key=lambda x: (
                datetime.fromisoformat(x['deadline_date']) if x.get('deadline_date') else datetime.max,
                datetime.fromisoformat(x['start_date']) if x.get('start_date') else datetime.max
            ))
        
        return jsonify({
            "tasks_this_week": tasks_this_week,
            "tasks_next_week": tasks_next_week,
            "tasks_following_weeks": tasks_following_weeks,
            "completed_tasks": completed_tasks
        }), 200

    except Exception as e:
        logging.error(f"Error fetching tasks for group {group_id}: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({'error': 'An internal server error occurred.'}), 500

# The following routes were provided in your original request,
# I'm including them here with necessary imports added.

@app.route('/submit_task_for_approval/<group_id>/<task_id>', methods=['POST'])
def submit_task_for_approval(group_id, task_id):
    try:
        logging.info(f"Received request to submit task {task_id} for approval in group {group_id}.")
        task_ref = db.reference(f'groups/{group_id}/tasks/{task_id}')
        task_data = task_ref.get()
        if not task_data:
            logging.warning(f"Task with ID {task_id} not found in group {group_id}.")
            return jsonify({'success': False, 'message': 'Task not found.'}), 404

        # Check if the task is already pending approval or completed to prevent duplicate submissions
        if task_data.get('status') in ['pending_approval', 'completed']:
            logging.warning(f"Task {task_id} in group {group_id} is already in status '{task_data.get('status')}'.")
            return jsonify({'success': False, 'message': 'Task is already pending approval or completed.'}), 409

        task_ref.update({
            'status': 'pending_approval',
            'submitted_timestamp': datetime.now().isoformat()
        })
        
        logging.info(f"Task {task_id} in group {group_id} has been successfully updated to 'pending_approval'.")
        return jsonify({'success': True, 'message': 'Task submitted for approval.'}), 200

    except Exception as e:
        logging.error(f"Error submitting task {task_id} for group {group_id}: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({'success': False, 'message': f'An error occurred: {str(e)}'}), 500

@app.route('/submit_progress/<username>/<group_id>/<task_id>', methods=['POST'])
def submit_progress(username, group_id, task_id):
    progress_text = request.form.get('progress')
    file = request.files.get('file')
    mark_completed = request.form.get('mark_completed') == 'true'

    if not progress_text and not file and not mark_completed:
        return 'No progress, file, or completion status provided', 400

    task_ref = db.reference(f'groups/{group_id}/tasks/{task_id}')
    progress_ref = task_ref.child('progress_reports').push()
    progress_data = {
        'reported_by': username,
        'timestamp': datetime.now().isoformat(),
        'progress': progress_text
    }

    if file:
        try:
            filename = secure_filename(file.filename)
            file_bytes = file.read()
            dropbox_path = f"/{filename}"
            upload_result = dbx.files_upload(file_bytes, dropbox_path, mute=True)
            logging.info(f"Dropbox upload result: {upload_result}")

            # Create a shared link
            shared_link_metadata = dbx.sharing_create_shared_link_with_settings(dropbox_path)
            logging.info(f"Dropbox shared link metadata: {shared_link_metadata}")

            # Use direct download link
            file_url = shared_link_metadata.url.replace('?dl=0', '?dl=1')
            progress_data['file_name'] = filename
            progress_data['file_url'] = file_url
        except Exception as e:
            logging.error(f"Error uploading file to Dropbox: {e}")
            logging.error(traceback.format_exc())
            return f"Dropbox upload failed: {e}", 500

    progress_ref.set(progress_data)
    
    if mark_completed:
        task_ref.update({'completed': True})

    admin_ref = db.reference(f'groups/{group_id}/admin')
    admin_username = admin_ref.get()
    if admin_username:
        task_name = task_ref.child('task_name').get()
        message = f'User "{username}" submitted a progress report for task "{task_name}".'
        if mark_completed:
            message = f'User "{username}" marked task "{task_name}" as completed.'
        
        db.reference(f'users/{admin_username}/notifications').push().set({
            'message': message,
            'group_id': group_id,
            'task_id': task_id,
            'timestamp': datetime.now().isoformat(),
            'read': False
        })
    
    return 'Progress report submitted successfully!', 200


@app.errorhandler(Exception)
def handle_exception(e):
    print("UNCAUGHT EXCEPTION:", e, file=sys.stderr)
    traceback.print_exc()
    return "Internal Server Error", 500
