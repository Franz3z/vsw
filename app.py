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


@app.route('/assign_role/<group_id>', methods=['POST'])
def assign_role(group_id):
    # This endpoint is kept for a potential direct assign_role call,
    # but the frontend's 'saveRoles' function directly updates member roles.
    # If not used directly, it can be removed.
    # If used, ensure `request.json` contains 'username' and 'role_name'
    return jsonify({'success': False, 'message': 'This endpoint is not fully implemented for direct use in the current flow.'}), 400

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

# NEW: Endpoint to get all existing tasks for assignment dropdown
@app.route('/get_all_tasks/<group_id>', methods=['GET'])
def get_all_tasks(group_id):
    try:
        tasks_ref = db.reference(f'groups/{group_id}/tasks')
        tasks_data = tasks_ref.get() or {}
        
        all_tasks = []
        for task_id, task_info in tasks_data.items():
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

# NEW: Endpoint to assign an existing task
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
        
        # Update assignment details
        task_ref.update({
            'assigned_to_type': assigned_to_type,
            'assigned_to': assigned_to,
            'completed': False # Re-open task if it was completed and re-assigned
        })

        # Notification logic for re-assignment
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

# Old create_assign_task is now deprecated.
# @app.route('/create_assign_task/<group_id>', methods=['POST'])
# def create_assign_task_deprecated(group_id):
#     return jsonify({'success': False, 'message': 'This endpoint has been deprecated. Please use /create_project_with_tasks or /assign_existing_task.'}), 400


@app.route('/submit_progress/<username>/<group_id>/<task_id>', methods=['POST'])
def submit_progress(username, group_id, task_id):
    progress_text = request.form.get('progress')
    file = request.files.get('file')
    mark_completed = request.form.get('mark_completed') == 'true' # Check for this new field

    if not progress_text and not file and not mark_completed: # If nothing is provided
        return 'No progress, file, or completion status provided', 400

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

    # Add progress report (even if empty, if task is just being marked complete)
    progress_ref.push(progress_data)

    # Update task completion status if requested
    if mark_completed:
        task_ref.child('completed').set(True)

    flash('Progress submitted and task status updated successfully.')
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
        members_data_raw = group_members_ref.get() or {} # Renamed to raw for clarity

        members_list = []
        if not isinstance(members_data_raw, dict): # Add this check
            logging.error(f"members_data_raw for group {group_id} is not a dictionary. Type: {type(members_data_raw)}, Value: {members_data_raw}")
            members_data_raw = {} # Default to empty dict to prevent further errors

        for username, member_info in members_data_raw.items(): # Use member_info instead of data for consistency
            primary_role = 'member'
            custom_roles = {}

            if isinstance(member_info, dict):
                primary_role = member_info.get('role', 'member') # Default to 'member'
                custom_roles = member_info.get('roles', {}) # This holds the dictionary of custom roles
            elif isinstance(member_info, str): # Handle case where member data is just a string role
                primary_role = member_info
                custom_roles = {member_info: True} # Assume the string is also a custom role
                logging.warning(f"Member data for {username} in group {group_id} is string. Converting.")
            else:
                logging.error(f"Unexpected member data type for {username} in group {group_id}: {type(member_info)} - {member_info}. Skipping.")
                continue


            members_list.append({
                'username': username,
                'primary_role': primary_role, # This is the main 'admin' or 'member' role
                'custom_roles': list(custom_roles.keys()) # List of custom role names (e.g., ['editor', 'viewer'])
            })
            
        # Also fetch all available custom roles for the dropdowns
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
