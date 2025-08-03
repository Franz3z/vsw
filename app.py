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
    logging.debug(f"Tasks data: {tasks_data}")

    tasks_this_week = []
    tasks_next_week = []
    completed_tasks = []
    
    today = datetime.now()
    # Calculate the start of "this week" (e.g., Sunday) and "next week"
    # Assuming week starts on Monday for calculation purposes
    start_of_this_week = today - timedelta(days=today.weekday()) # Monday
    start_of_next_week = start_of_this_week + timedelta(weeks=1)


    for task_id, task in tasks_data.items():
        task_info = {
            'task_id': task_id,
            'task_name': task.get('task_name', 'No Name'),
            'description': task.get('description', ''),
            'assigned_to': task.get('assigned_to', 'N/A'),
            'priority': task.get('priority', 'Low'),
            'progress_reports': task.get('progress_reports', {}),
            'assigned_type': task.get('assigned_type', 'user'),
            'deadline': task.get('deadline', '')
        }
        
        # Determine if task is completed
        if task.get('completed', False): # Use the 'completed' flag now
            completed_tasks.append(task_info)
        else:
            # Categorize pending tasks by deadline
            if task_info['deadline']:
                try:
                    deadline_dt = datetime.strptime(task_info['deadline'], "%Y-%m-%d")
                    
                    if start_of_this_week <= deadline_dt < start_of_next_week + timedelta(weeks=1):
                         tasks_this_week.append(task_info)
                    elif start_of_next_week <= deadline_dt < start_of_next_week + timedelta(weeks=2):
                        tasks_next_week.append(task_info)
                except ValueError:
                    logging.warning(f"Invalid deadline format for task {task_id}: {task_info['deadline']}")
                    # If deadline is invalid or not set, it won't fall into week categories
            # If no deadline or invalid, it won't be in specific weekly categories,
            # but you might want a general 'upcoming tasks' or 'backlog' section.
            # For this example, if it doesn't fit a week, it's just not shown in week categories.
    
    # Sort tasks within categories (e.g., by priority)
    priority_order = {'high': 1, 'medium': 2, 'low': 3}
    tasks_this_week.sort(key=lambda x: priority_order.get(x.get('priority', 'Low').lower(), 4))
    tasks_next_week.sort(key=lambda x: priority_order.get(x.get('priority', 'Low').lower(), 4))
    completed_tasks.sort(key=lambda x: x.get('task_name', '')) # Example sort


    logging.debug(f"Tasks This Week: {tasks_this_week}")
    logging.debug(f"Tasks Next Week: {tasks_next_week}")
    logging.debug(f"Completed tasks: {completed_tasks}")


    # --- Get ALL Available Custom Roles for the Group ---
    custom_roles_ref = db.reference(f'groups/{group_id}/custom_roles') # Use custom_roles consistently
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

@app.route('/create_role/<group_id>', methods=['POST'])
def create_role(group_id):
    try:
        data = request.get_json()
        if not data or 'role_name' not in data:
            return jsonify({'success': False, 'message': 'Role name is required.'}), 400
            
        role_name = data['role_name'].strip()
        if not role_name:
            return jsonify({'success': False, 'message': 'Role name cannot be empty.'}), 400

        # Use 'custom_roles' for clarity, consistent with frontend and mainadmin route
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


@app.route('/assign_role/<group_id>', methods=['POST'])
def assign_role(group_id):
    # This endpoint is kept for a potential direct assign_role call,
    # but the frontend's 'saveRoles' function directly updates member roles.
    # If not used directly, it can be removed.
    # If used, ensure `request.json` contains 'username' and 'role_name'
    return jsonify({'success': False, 'message': 'This endpoint is not fully implemented for direct use in the current flow.'}), 400


@app.route('/create_assign_task/<group_id>', methods=['POST']) # Renamed endpoint
def create_assign_task(group_id):
    try:
        # Expecting JSON data from the frontend
        data = request.get_json() 
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        task_name = data.get('task_name')
        task_description = data.get('description', '')
        assigned_to = data.get('assigned_to')
        priority = data.get('priority')
        assigned_type = data.get('assigned_type', 'user') # 'user' or 'everyone'

        # Basic validation
        if not task_name or not assigned_to or not priority:
            return jsonify({'success': False, 'message': 'Task name, assigned to, and priority are required.'}), 400

        task_data = {
            'task_name': task_name,
            'description': task_description,
            'assigned_to': assigned_to,
            'priority': priority,
            'completed': False, # Default to false for new tasks
            'progress_reports': {},
            'assigned_type': assigned_type
        }
        
        # Add deadline if present in the request
        deadline = data.get('deadline')
        if deadline:
            task_data['deadline'] = deadline

        db.reference(f'groups/{group_id}/tasks').push(task_data)
        
        # --- Notification Logic (Remains the same as your original) ---
        if assigned_type == 'everyone':
            # Notify all members of the group
            members_ref = db.reference(f'groups/{group_id}/members').get() or {}
            for member_username in members_ref.keys():
                notifications_ref = db.reference(f'users/{member_username}/notifications').push()
                notifications_ref.set({
                    'message': f'New group task "{task_name}" assigned to everyone in group {group_id}.',
                    'group_id': group_id,
                    'task_id': task_data['task_id'], # Pass task_id for direct link if desired
                    'timestamp': datetime.now().isoformat(),
                    'read': False
                })
        elif assigned_type == 'username': # Specific user assignment
            notifications_ref = db.reference(f'users/{assigned_to}/notifications').push()
            notifications_ref.set({
                'message': f'New task "{task_name}" assigned to you in group {group_id}.',
                'group_id': group_id,
                'task_id': task_data['task_id'],
                'timestamp': datetime.now().isoformat(),
                'read': False
            })
        
        # Note: Your original code had 'assigned_type == 'role'' for notifications.
        # If you intend to assign tasks specifically to a *role* and notify all users with that role,
        # you'll need to expand this logic. For now, it handles 'user' and 'everyone'.

        return jsonify({
            'success': True,
            'message': 'Task assigned successfully!'
        }), 201 # 201 Created

    except Exception as e:
        logging.error(f"Error assigning task for group {group_id}: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error assigning task: {str(e)}'}), 500


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
    group_ref = db.reference(f'groups/{group_id}/custom_roles') # Use custom_roles consistent with mainadmin
    roles_data = group_ref.get() or {}
    
    user_roles_data = db.reference(f'users/{username}/groups/{group_id}/roles').get() or {}
    user_custom_roles = list(user_roles_data.keys()) # Get list of custom roles for the user

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
            
        # Determine if the task is assigned to the current user, or to a role the user possesses,
        # or to 'everyone'.
        is_assigned_to_user = (task_info['assigned_type'] == 'username' and task_info.get('assigned_to') == username)
        is_assigned_to_everyone = (task_info['assigned_type'] == 'everyone' and task_info.get('assigned_to') == 'everyone')
        
        # Check if the task is assigned to a role that the user has
        is_assigned_to_user_role = False
        if task_info['assigned_type'] == 'role':
            assigned_role = task_info.get('assigned_to')
            if assigned_role in user_custom_roles: # Check if the user's custom roles include the assigned role
                is_assigned_to_user_role = True

        if is_assigned_to_user or is_assigned_to_everyone or is_assigned_to_user_role:
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
        user_roles=list(user_custom_roles) # Pass the list of user's custom roles
    )

@app.route('/approve_request/<group_id>/<username>', methods=['POST'])
def approve_request(group_id, username):
    group_ref = db.reference(f'groups/{group_id}')
    pending_ref = group_ref.child('pending_requests')
    members_ref = group_ref.child('members')

    if pending_ref.child(username).get():
        members_ref.child(username).set({
            'role': 'member', # Set primary role
            'roles': {'member': True} # Assign 'member' as a default custom role
        })

        pending_ref.child(username).delete()

        user_group_ref = db.reference(f'users/{username}/groups/{group_id}')
        group_data = group_ref.get()
        user_group_ref.set({
            'group_name': group_data.get('group_name', ''),
            'role': 'member', # Set primary role for user's group view
            'roles': {'member': True} # Assign 'member' as a default custom role for user's group view
        })
        flash(f'{username} has been approved to join the group.')
    else:
        flash(f'No pending request from {username}.')

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

    timestamp = datetime.now().isoformat() # Changed to ISO format for easier sorting
    message = {
        'sender': sender,
        'text': text,
        'timestamp': timestamp
    }

    messages_ref = db.reference(f'groups/{group_id}/chat')
    messages_ref.push(message)

    return jsonify({'success': True})


@app.route('/get_messages/<group_id>', methods=['GET']) # Removed /chat from URL path
def get_messages(group_id):
    try:
        messages_ref = db.reference(f'groups/{group_id}/chat')
        messages = messages_ref.get() or {}
        
        message_list = []
        # Sort messages by timestamp before sending
        sorted_messages = sorted(messages.items(), key=lambda item: item[1].get('timestamp', ''))

        for key, msg in sorted_messages:
            if isinstance(msg, dict):
                # Ensure timestamp is in correct format for client-side display
                timestamp_str = msg.get('timestamp', '')
                try:
                    # Attempt to parse as ISO format if it matches
                    dt_object = datetime.fromisoformat(timestamp_str)
                    formatted_timestamp = dt_object.strftime('%b %d, %I:%M %p')
                except ValueError:
                    # Fallback if not ISO, or use as is
                    formatted_timestamp = timestamp_str

                message_list.append({
                    'sender': msg.get('sender', ''),
                    'message': msg.get('text', ''),
                    'timestamp': formatted_timestamp
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

@app.route('/get_group_members_with_roles/<group_id>')
def get_group_members_with_roles(group_id):
    try:
        group_members_ref = db.reference(f'groups/{group_id}/members')
        members_data = group_members_ref.get() or {}

        # Prepare a list of members with their primary role ('admin' or 'member')
        # And also include any custom roles they might have
        members_list = []
        for username, data in members_data.items():
            primary_role = data.get('role', 'member') # Default to member if not set
            custom_roles = data.get('roles', {}) # This holds the dictionary of custom roles

            members_list.append({
                'username': username,
                'primary_role': primary_role, # This is the main 'admin' or 'member' role
                'custom_roles': list(custom_roles.keys()) # List of custom role names (e.g., ['editor', 'viewer'])
            })
            
        # Also fetch all available custom roles for the dropdowns
        # IMPORTANT: Ensure this path matches where you store available roles.
        # It's currently `/groups/{group_id}/custom_roles` based on `create_role` change.
        available_roles_ref = db.reference(f'groups/{group_id}/custom_roles')
        available_roles_data = available_roles_ref.get() or {}
        available_custom_roles = list(available_roles_data.keys())


        return jsonify({
            'success': True,
            'members': members_list,
            'available_custom_roles': available_custom_roles
        })

    except Exception as e:
        logging.error(f"Error fetching group members with roles for group {group_id}: {e}")
        return jsonify({'success': False, 'message': 'Error fetching members.'}), 500

@app.route('/update_roles/<group_id>', methods=['POST'])
def update_roles(group_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        for username, updates in data.items():
            member_ref = db.reference(f'groups/{group_id}/members/{username}')
            user_group_ref = db.reference(f'users/{username}/groups/{group_id}')

            if 'primary_role' in updates:
                # Update the primary role (admin/member)
                member_ref.child('role').set(updates['primary_role'])
                user_group_ref.child('role').set(updates['primary_role'])

            # Handle custom roles: The client-side sends all selected as 'to_assign' and all unselected as 'to_unassign'
            # This logic will effectively overwrite the custom roles with the new selection.
            if 'custom_roles_to_assign' in updates:
                # Get current custom roles to avoid deleting others if not in 'to_unassign'
                current_member_custom_roles = member_ref.child('roles').get() or {}
                current_user_custom_roles = user_group_ref.child('roles').get() or {}

                # Clear only custom roles (leave primary 'role' key untouched)
                for role_name in updates['custom_roles_to_unassign']:
                    if role_name in current_member_custom_roles:
                        del current_member_custom_roles[role_name]
                    if role_name in current_user_custom_roles:
                        del current_user_custom_roles[role_name]
                
                for role_name in updates['custom_roles_to_assign']:
                    current_member_custom_roles[role_name] = True
                    current_user_custom_roles[role_name] = True
                
                member_ref.child('roles').set(current_member_custom_roles)
                user_group_ref.child('roles').set(current_user_custom_roles)
        
        return jsonify({'success': True, 'message': 'Roles updated successfully.'})

    except Exception as e:
        logging.error(f"Error updating roles for group {group_id}: {e}")
        traceback.print_exc() # Print full traceback
        return jsonify({'success': False, 'message': 'Error updating roles.'}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    print("UNCAUGHT EXCEPTION:", e, file=sys.stderr)
    traceback.print_exc()
    return "Internal Server Error", 500
