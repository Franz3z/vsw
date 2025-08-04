from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
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
    
    # Calculate start of current week (Monday) and next week
    today = datetime.now()
    start_of_this_week = today - timedelta(days=today.weekday())
    # Ensure start_of_this_week is just the date for comparison (midnight)
    start_of_this_week = start_of_this_week.replace(hour=0, minute=0, second=0, microsecond=0)
    
    start_of_next_week = start_of_this_week + timedelta(weeks=1)
    
    # Define week boundaries for categorization in mainadmin
    week_boundaries = {
        'this_week': (start_of_this_week, start_of_this_week + timedelta(weeks=1)),
        'next_week': (start_of_next_week, start_of_next_week + timedelta(weeks=1)),
    }
    # Add more week categories if needed, e.g., 'week_2', 'week_3' etc.
    for i in range(2, 5): # For week_2, week_3, week_4
        week_start = start_of_this_week + timedelta(weeks=i)
        week_boundaries[f'week_{i}'] = (week_start, week_start + timedelta(weeks=1))


    for task_id, task in tasks_data.items():
        # IMPORTANT: Add a safety check to ensure task is a dictionary
        if not isinstance(task, dict):
            logging.warning(f"Skipping malformed task data for task_id: {task_id}. Data was not a dictionary: {task}")
            continue

        task_info = {
            'task_id': task_id,
            'task_name': task.get('task_name', 'No Name'),
            'description': task.get('description', ''),
            'assigned_to': task.get('assigned_to', 'N/A'),
            'priority': task.get('priority', 'Low'),
            'progress_reports': task.get('progress_reports', {}),
            'assigned_type': task.get('assigned_type', 'user'), # New field
            'deadline': task.get('deadline', ''),
            'week_category': task.get('week_category', '') # New field
        }
        
        # Determine if task is completed
        if task.get('completed', False):
            completed_tasks.append(task_info)
        else:
            # Categorize pending tasks based on week_category stored in Firebase
            if task_info['week_category'] == 'this_week':
                tasks_this_week.append(task_info)
            elif task_info['week_category'] == 'next_week':
                tasks_next_week.append(task_info)
            # You might need more lists for 'week_2', 'week_3' etc. here
            # For simplicity, if week_category is not 'this_week' or 'next_week', it won't be shown in these specific panels.
            # The JS for 'Create Project' handles setting week_category.
            
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
    tasks = []

    if not isinstance(tasks_data, dict):
        logging.error(f"tasks_data is not a dictionary for group {group_id}. Type: {type(tasks_data)}, Value: {tasks_data}")
        tasks_data = {}

    for task_id, task in tasks_data.items():
        # IMPORTANT: Add a safety check to ensure task is a dictionary
        if not isinstance(task, dict):
            logging.warning(f"Skipping malformed task data for task_id: {task_id}. Data was not a dictionary: {task}")
            continue

        task_info = {
            'task_id': task_id,
            'task_name': task.get('task_name', 'No Name'),
            'description': task.get('description', ''),
            'assigned_to': task.get('assigned_to', 'N/A'),
            'priority': task.get('priority', 'Low'),
            'progress_reports': task.get('progress_reports', {}),
            'assigned_type': task.get('assigned_type', 'user'),
            'deadline': task.get('deadline', ''),
            'week_category': task.get('week_category', '')
        }
        # Only show tasks assigned to the current user or a group they are in
        assigned_to_user = task_info['assigned_to'] == username
        assigned_to_group_with_user = (
            task_info['assigned_type'] == 'group' and
            task_info['assigned_to'] in user_group.get('roles', {}).keys()
        )

        if assigned_to_user or assigned_to_group_with_user:
            tasks.append(task_info)

    return render_template('main.html',
                           username=username,
                           group_id=group_id,
                           tasks=tasks)

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
            
            task_entry = {
                'project_id': project_id, # Link task to project
                'task_name': task_name,
                'description': description,
                'assigned_to_type': assigned_to_type,
                'assigned_to': assigned_to,
                'priority': priority,
                'completed': False,
                'progress_reports': {},
                'week_category': week_category, # Store the selected week category
                'deadline': deadline_date.strftime('%Y-%m-%d') if deadline_date else '' # Store formatted deadline
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
        tasks_ref = db.reference(f'groups/{group_id}/tasks')
        tasks_data = tasks_ref.get() or {}
        
        # Filter out tasks that are marked as completed
        all_tasks = []
        for task_id, task_info in tasks_data.items():
            if not task_info.get('completed', False): # Only include tasks not marked as completed
                all_tasks.append({
                    'task_id': task_id,
                    'task_name': task_info.get('task_name', 'Unnamed Task'),
                    'description': task_info.get('description', ''),
                    'assigned_to': task_info.get('assigned_to', 'N/A'),
                    'priority': task_info.get('priority', 'Low'),
                    'completed': task_info.get('completed', False),
                    'assigned_type': task_info.get('assigned_type', 'user'),
                    'week_category': task_info.get('week_category', ''),
                    'deadline': task_info.get('deadline', '')
                })
        
        return jsonify({'success': True, 'tasks': all_tasks})
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

@app.route('/submit_progress/<username>/<group_id>/<task_id>', methods=['POST'])
def submit_progress(username, group_id, task_id):
    progress_text = request.form.get('progress')
    file = request.files.get('file')
    mark_completed = request.form.get('mark_completed') == 'true' # Check for this new field

    if not progress_text and not file and not mark_completed: # If nothing is provided
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
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            # NOTE: For a production app, you would want to use a more persistent storage
            # solution like Firebase Storage or AWS S3 and save the URL here, not the local path.
            # This implementation is for a simple demonstration.
            progress_data['file_path'] = file_path
            progress_data['file_name'] = filename
        except Exception as e:
            logging.error(f"Error saving uploaded file: {e}")
            return f"File upload failed: {e}", 500

    progress_ref.set(progress_data)
    
    # If the user marked the task as completed, update the task status
    if mark_completed:
        task_ref.update({'completed': True})

    # Notify the group admin
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

@app.route('/messages/<group_id>')
def get_messages(group_id):
    chat_ref = db.reference(f'groups/{group_id}/chat')
    chat_data = chat_ref.get() or {}

    messages = []
    for message_id, message_data in chat_data.items():
        if isinstance(message_data, dict):
            messages.append({
                'sender': message_data.get('sender', 'Unknown'),
                'message': message_data.get('text', ''),
                'timestamp': message_data.get('timestamp', '')
            })
    return jsonify(messages)

@app.route('/send_message/<group_id>', methods=['POST'])
def send_message(group_id):
    username = request.form.get('username')
    message = request.form.get('message')
    if not username or not message:
        return jsonify({'success': False, 'message': 'Username and message are required'}), 400

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

@app.route('/update_roles/<string:group_id>', methods=['POST'])
def update_roles(group_id):
    """
    Endpoint to update roles for members within a group.
    
    It expects a JSON payload with a 'member_id' and a dictionary of 'updates'
    which contains 'custom_roles_to_assign' and 'custom_roles_to_unassign'.
    """
    try:
        data = request.get_json()
        member_id = data.get('member_id')
        updates = data.get('updates')

        if not member_id or not updates:
            return jsonify({'success': False, 'message': 'Missing member_id or updates.'}), 400

        # Reference to the group and the specific member
        group_ref = db.reference(f'groups/{group_id}')
        member_ref = group_ref.child('members').child(member_id)

        # Reference to the user's group entry
        user_group_ref = db.reference(f'users/{member_id}/groups/{group_id}')

        custom_roles_to_assign = updates.get('custom_roles_to_assign', {})
        custom_roles_to_unassign = updates.get('custom_roles_to_unassign', {})

        # Ensure we have roles to process
        if custom_roles_to_assign or custom_roles_to_unassign:
            # Fetch current custom roles from Firebase
            current_member_custom_roles = member_ref.child('roles').get() or {}
            current_user_custom_roles = user_group_ref.child('roles').get() or {}

            # Clear roles that are to be unassigned
            for role_name in custom_roles_to_unassign:
                if role_name in current_member_custom_roles:
                    del current_member_custom_roles[role_name]
                if role_name in current_user_custom_roles:
                    del current_user_custom_roles[role_name]
            
            # Add roles that are to be assigned
            for role_name in custom_roles_to_assign:
                current_member_custom_roles[role_name] = True
                current_user_custom_roles[role_name] = True
            
            # Update Firebase with the modified custom roles
            member_ref.child('roles').set(current_member_custom_roles)
            user_group_ref.child('roles').set(current_user_custom_roles)
        
        return jsonify({'success': True, 'message': 'Roles updated successfully.'})

    except Exception as e:
        logging.error(f"Error updating roles for group {group_id}: {e}")
        traceback.print_exc() # Print full traceback
        return jsonify({'success': False, 'message': 'Error updating roles.'}), 500


@app.route('/update_task_details/<group_id>/<task_id>', methods=['POST'])
def update_task_details(group_id, task_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided.'}), 400

        task_ref = db.reference(f'groups/{group_id}/tasks/{task_id}')
        task_ref.update(data)
        
        return jsonify({'success': True, 'message': 'Task details updated successfully.'})
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

@app.errorhandler(Exception)
def handle_exception(e):
    print("UNCAUGHT EXCEPTION:", e, file=sys.stderr)
    traceback.print_exc()
    return "Internal Server Error", 500
