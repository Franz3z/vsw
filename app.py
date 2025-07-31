from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import firebase_admin
from firebase_admin import credentials, db, initialize_app
from flask import session
from flask import make_response
import os
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

app = Flask(__name__)
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

    response = make_response(render_template('dashboard.html', username=username, groups=user_groups))
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
            username: 'admin'
        },
        'roles': {}  # Initialize roles dictionary
    })

    db.reference(f'users/{username}/groups/{group_id}').set({
        'group_name': group_name,
        'role': 'admin'
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
    user_group = db.reference(f'users/{username}/groups/{group_id}').get()

    if not user_group:
        flash('You are not part of this group.')
        return redirect(url_for('dashboard', username=username))

    if user_group.get('role') == 'admin':
        return redirect(url_for('mainadmin', username=username, group_id=group_id))
    else:
        return redirect(url_for('main', username=username, group_id=group_id))

@app.route('/mainadmin/<username>/<group_id>')
def mainadmin(username, group_id):
    group_ref = db.reference(f'groups/{group_id}')

    members_ref = group_ref.child('members')
    members_data = members_ref.get() or {}
    members = [{'username': m} for m in members_data.keys() if m != username]

    pending_ref = group_ref.child('pending_requests')
    pending_requests_data = pending_ref.get() or {}
    pending_requests = list(pending_requests_data.keys())

    tasks_ref = group_ref.child('tasks')
    tasks_data = tasks_ref.get() or {}

    pending_tasks = []
    completed_tasks = []

    for task_id, task in tasks_data.items():
        task_info = {
            'task_id': task_id,
            'task_name': task.get('task_name', ''),
            'description': task.get('description', ''),
            'assigned_to': task.get('assigned_to', ''),
            'priority': task.get('priority', ''),
            'progress_reports': task.get('progress_reports', {}),
            'assigned_type': task.get('assigned_type', 'user'),  # Add assigned_type
            'deadline': task.get('deadline', '')
        }
        if task_info['progress_reports']:
            completed_tasks.append(task_info)
        else:
            pending_tasks.append(task_info)

    # Get custom roles
    roles_ref = db.reference(f'groups/{group_id}/roles')
    roles_data = roles_ref.get() or {}

    # Get member roles (replaced with actual implementation)
    chat_ref = db.reference(f'groups/{group_id}/chat')
    chat_data = chat_ref.get() or {}

    messages = []
    for _, msg in sorted(chat_data.items(), key=lambda x: x[1].get('timestamp', '')):
        if isinstance(msg, dict):
            messages.append({
                'sender': msg.get('sender'),
                'message': msg.get('text'), 
                'timestamp': datetime.fromisoformat(msg['timestamp']).strftime('%b %d, %I:%M %p')
            })
        else:
            logging.warning(f"Skipping malformed message in mainadmin for group {group_id}: {msg}")

    return render_template(
        'mainadmin.html',
        username=username,
        group_id=group_id,
        members=members,
        pending_requests=pending_requests,
        pending_tasks=pending_tasks,
        completed_tasks=completed_tasks,
        messages=messages,
        group_roles=roles_data
    )

@app.route('/create_role/<group_id>', methods=['POST'])
def create_role(group_id):
    role_name = request.json['role_name']
    ref = db.reference(f'groups/{group_id}/roles')
    ref.child(role_name).set(True)  # Store role as key
    
    return jsonify({
        'success': True,
        'message': f'Role "{role_name}" created successfully!'
    })

@app.route('/assign_role/<group_id>', methods=['POST'])
def assign_role(group_id):
    username = request.json['username']
    role_name = request.json['role_name']
    
    ref = db.reference(f'groups/{group_id}/members/{username}/roles')
    current_roles = ref.get() or {}
    current_roles[role_name] = True
    
    try:
        ref.set(current_roles)
        # Also update the user's group role reference
        user_group_ref = db.reference(f'users/{username}/groups/{group_id}/roles')
        user_group_ref.set(current_roles)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/assign_task/<group_id>', methods=['POST'])
def assign_task(group_id):
    task_name = request.form['task_name']
    task_description = request.form['task_description']
    assigned_to = request.form['assigned_to']
    priority = request.form['priority']
    deadline = request.form.get('deadline', '')
    assigned_type = request.form.get('assigned_type', 'user')  # Default to user

    task_data = {
        'task_name': task_name,
        'description': task_description,
        'assigned_to': assigned_to,
        'priority': priority,
        'deadline': deadline,
        'completed': False,
        'progress_reports': {},
        'assigned_type': assigned_type  # Added field
    }

    db.reference(f'groups/{group_id}/tasks').push(task_data)
    
    # Create notification for role assignments
    if assigned_type == 'role':
        role_ref = db.reference(f'groups/{group_id}/members')
        members = role_ref.get() or {}
        for member, data in members.items():
            if data.get('roles', {}).get(assigned_to):
                # Send notification to relevant member
                notifications_ref = db.reference(f'users/{member}/notifications').push()
                notifications_ref.set({
                    'message': f'New task assigned to your role: {task_name}',
                    'group_id': group_id,
                    'timestamp': datetime.now().isoformat(),
                    'read': False
                })

    return jsonify({
        'success': True,
        'message': 'Task assigned successfully!'
    })


def get_tasks_by_week(tasks):
    """Organize tasks by week based on deadline for the main user view"""
    today = datetime.today()
    tasks_this_week = []
    
    for task in tasks:
        if 'deadline' in task and task['deadline']:
            try:
                deadline = datetime.strptime(task['deadline'], "%Y-%m-%d")
                days_until_deadline = (deadline - today).days
                
                if 0 <= days_until_deadline <= 7:
                    # Apply vertical borders based on priority
                    if 'high' in task.get('priority', '').lower():
                        task['priority_class'] = 'priority-high'
                    elif 'medium' in task.get('priority', '').lower():
                        task['priority_class'] = 'priority-medium'
                    elif 'low' in task.get('priority', '').lower():
                        task['priority_class'] = 'priority-low'
                    else:
                        task['priority_class'] = ''
                    
                    tasks_this_week.append(task)
            except:
                pass
    
    return tasks_this_week

@app.route('/main/<username>/<group_id>')
def main(username, group_id):
    # Get group roles to check role assignments
    group_ref = db.reference(f'groups/{group_id}/roles')
    roles_data = group_ref.get() or {}
    user_roles = db.reference(f'users/{username}/groups/{group_id}/roles').get() or {}

    # Get all tasks
    tasks_ref = db.reference(f'groups/{group_id}/tasks').get() or {}
    
    pending_tasks = []
    completed_tasks = []
    
    # Separate pending and completed tasks
    for task_id, task_info in tasks_ref.items():
        task_info['task_id'] = task_id
        # Add assigned_type if missing for backward compatibility
        if 'assigned_type' not in task_info:
            task_info['assigned_type'] = 'user'
        
        # Include tasks assigned to user directly or to role
        if (task_info['assigned_type'] == 'user' and task_info.get('assigned_to') == username) or \
           (task_info['assigned_type'] == 'role' and task_info.get('assigned_to') in user_roles and user_roles[task_info['assigned_to']]):
            if task_info.get('completed'):
                completed_tasks.append(task_info)
            else:
                pending_tasks.append(task_info)
    
    # Get tasks due this week with priority formatting
    tasks_this_week = get_tasks_by_week(pending_tasks)
    
    # Get unread notifications
    notifications_ref = db.reference(f'users/{username}/notifications').get() or {}
    unread_notifications = []
    for nid, notif in notifications_ref.items():
        if not notif.get('read', False):
            unread_notifications.append({**notif, 'nid': nid})
            
    # Mark notifications as read
    for notif in unread_notifications:
        db.reference(f'users/{username}/notifications/{notif["nid"]}/read').set(True)
    
    # Get chat messages
    chat_ref = db.reference(f'groups/{group_id}/chat')
    chat_data = chat_ref.get() or {}
    messages = []
    for _, msg in sorted(chat_data.items(), key=lambda x: x[1].get('timestamp', '')):
        if isinstance(msg, dict):
            messages.append({
                'sender': msg.get('sender'),
                'message': msg.get('text'), 
                'timestamp': datetime.fromisoformat(msg['timestamp']).strftime('%b %d, %I:%M %p')
            })
    
    # Sort tasks_this_week by priority
    priority_order = {'high': 1, 'medium': 2, 'low': 3}
    tasks_this_week = sorted(
        tasks_this_week,
        key=lambda x: priority_order.get(x.get('priority', '').lower(), 4)
    )
    
    return render_template(
        'main.html',
        username=username,
        group_id=group_id,
        pending_tasks=pending_tasks,
        completed_tasks=completed_tasks,
        tasks_this_week=tasks_this_week,
        messages=messages,
        notifications=unread_notifications,
        user_roles=list(user_roles.keys())
    )

@app.route('/approve_request/<group_id>/<username>', methods=['POST'])
def approve_request(group_id, username):
    group_ref = db.reference(f'groups/{group_id}')
    pending_ref = group_ref.child('pending_requests')
    members_ref = group_ref.child('members')

    if pending_ref.child(username).get():
        members_ref.child(username).set({
            'role': 'member',
            'roles': {'member': True}
        })

        pending_ref.child(username).delete()

        user_group_ref = db.reference(f'users/{username}/groups/{group_id}')
        group_data = group_ref.get()
        user_group_ref.set({
            'group_name': group_data.get('group_name', ''),
            'role': 'member',
            'roles': {'member': True}
        })

    return redirect(url_for('mainadmin', username=session.get('username'), group_id=group_id))

@app.route('/submit_progress/<username>/<group_id>/<task_id>', methods=['POST'])
def submit_progress(username, group_id, task_id):
    progress_text = request.form.get('progress')
    file = request.files.get('file')

    if not progress_text and not file:
        return 'No progress or file provided', 400

    task_ref = db.reference(f'groups/{group_id}/tasks/{task_id}')
    progress_ref = task_ref.child('progress_reports')

    progress_data = {
        'submitted_by': username,
        'progress': progress_text or '',
        'timestamp': datetime.now().isoformat()
    }

    if file and file.filename:
        filename = secure_filename(file.filename)
        user_folder = os.path.join(app.config['UPLOAD_FOLDER'], group_id, task_id, username)
        os.makedirs(user_folder, exist_ok=True)
        filepath = os.path.join(user_folder, filename)
        file.save(filepath)
        progress_data['file'] = filename

        # Add progress report without marking task as completed
        progress_ref.push(progress_data)

    flash('Progress and file submitted successfully.')
    return redirect(url_for('main', username=username, group_id=group_id))

@app.route('/download/<group_id>/<task_id>/<username>/<filename>')
def download_file(group_id, task_id, username, filename):
    directory = os.path.join(app.config['UPLOAD_FOLDER'], group_id, task_id, username)
    return send_from_directory(directory, filename, as_attachment=True)

@app.route('/send_message/<group_id>', methods=['POST'])
def send_message(group_id):
    data = request.get_json()
    sender = data.get('sender')
    text = data.get('text')

    if not text or not sender:
        return jsonify({'success': False, 'error': 'Missing data'}), 400

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = {
        'sender': sender,
        'text': text,
        'timestamp': timestamp
    }

    messages_ref = db.reference(f'groups/{group_id}/chat')
    messages_ref.push(message)

    return jsonify({'success': True})


@app.route('/get_messages/<group_id>/chat')
def get_messages(group_id):
    try:
        messages_ref = db.reference(f'groups/{group_id}/chat')
        messages = messages_ref.get() or {}
        
        message_list = []
        for key, msg in messages.items():
            if isinstance(msg, dict):
                message_list.append({
                    'sender': msg.get('sender', ''),
                    'text': msg.get('text', ''),
                    'timestamp': msg.get('timestamp', '')
                })
            else:
                logging.warning(f"Skipping malformed message in group {group_id} with key {key}: {msg}")

        return jsonify({'messages': message_list})

    except Exception as e:
        logging.error(f"Error in get_messages for group {group_id}: {e}")
        sys.stderr.write(traceback.format_exc() + '\n')
        return jsonify({'success': False, 'error': 'Internal server error fetching messages'}), 500

@app.route('/clear_notification/<notification_id>', methods=['POST'])
def clear_notification(notification_id):
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        ref = db.reference(f'users/{session["username"]}/notifications/{notification_id}')
        ref.delete()
        return jsonify({'success': True})
    except Exception as e:
        logging.error(f"Error deleting notification: {e}")
        return jsonify({'error': str(e)}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    print("UNCAUGHT EXCEPTION:", e, file=sys.stderr)
    traceback.print_exc()
    return "Internal Server Error", 500
