import eventlet
import eventlet.wsgi
eventlet.monkey_patch()

from flask import Flask, render_template, request, redirect, url_for, flash  
import firebase_admin  
from firebase_admin import credentials, db, initialize_app
from flask import session
from flask import make_response
import os
from flask import send_from_directory
from werkzeug.utils import secure_filename
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template
import json
import logging
import requests

VIDEOSDK_API_KEY = os.getenv('VIDEOSDK_API_KEY')
VIDEOSDK_SECRET = os.getenv('VIDEOSDK_SECRET')

load_dotenv()
app = Flask(__name__)  
app.secret_key = 'your-secure-secret-key' 
logging.basicConfig(level=logging.DEBUG)

app.config['UPLOAD_FOLDER'] = os.path.join('uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
database_url = os.getenv('FIREBASE_DATABASE_URL')

cred = credentials.Certificate("/etc/secrets/firebase.json")
initialize_app(cred, {
    'databaseURL': os.getenv('FIREBASE_DATABASE_URL')
})

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
    user_data = db.reference(f'users/{username}').get()
    if user_data and user_data.get('password') == password:
        session['username'] = username
        return redirect(url_for('dashboard', username=username))
    flash('Invalid username or password')
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
        }  
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
            'progress_reports': task.get('progress_reports', {})
        }
        if task_info['progress_reports']:
            completed_tasks.append(task_info)
        else:
            pending_tasks.append(task_info)

    chat_ref = db.reference(f'chats/{group_id}')
    chat_data = chat_ref.get() or {}

    messages = []
    for _, msg in sorted(chat_data.items(), key=lambda x: x[1].get('timestamp', '')):
        messages.append({
            'sender': msg.get('sender'),
            'message': msg.get('message'),
            'timestamp': datetime.fromisoformat(msg['timestamp']).strftime('%b %d, %I:%M %p')
        })

    return render_template(
        'mainadmin.html',
        username=username,
        group_id=group_id,
        members=members,
        pending_requests=pending_requests,
        pending_tasks=pending_tasks,
        completed_tasks=completed_tasks,
        messages=messages
        api_key=VIDEOSDK_API_KEY
    )

@app.route('/assign_task/<group_id>', methods=['POST'])
def assign_task(group_id):
    task_name = request.form['task_name']
    task_description = request.form['task_description']
    assigned_to = request.form['assigned_to']
    priority = request.form['priority']

    task_data = {
        'task_name': task_name,
        'description': task_description,
        'assigned_to': assigned_to,
        'priority': priority,
        'progress_reports': []
    }

    db.reference(f'groups/{group_id}/tasks').push(task_data)

    return 'Task assigned successfully!'


@app.route('/main/<username>/<group_id>')
def main(username, group_id):
    tasks_ref = db.reference(f'groups/{group_id}/tasks').get() or {}

    pending_tasks = []
    completed_tasks = []

    for task_id, task_info in tasks_ref.items():
        if task_info.get('assigned_to') == username:
            task_info['task_id'] = task_id
            if task_info.get('completed'):
                completed_tasks.append(task_info)
            else:
                pending_tasks.append(task_info)

    chat_ref = db.reference(f'chats/{group_id}')
    chat_data = chat_ref.get() or {}

    messages = []
    for _, msg in sorted(chat_data.items(), key=lambda x: x[1].get('timestamp', '')):
        messages.append({
            'sender': msg.get('sender'),
            'message': msg.get('message'),
            'timestamp': datetime.fromisoformat(msg['timestamp']).strftime('%b %d, %I:%M %p')
        })

    return render_template(
        'main.html',
        username=username,
        group_id=group_id,
        pending_tasks=pending_tasks,
        completed_tasks=completed_tasks,
        messages=messages
        api_key=VIDEOSDK_API_KEY

    )
    

@app.route('/approve_request/<group_id>/<username>', methods=['POST'])
def approve_request(group_id, username):
    group_ref = db.reference(f'groups/{group_id}')
    pending_ref = group_ref.child('pending_requests')
    members_ref = group_ref.child('members')

    if pending_ref.child(username).get():
        members_ref.child(username).set('member')
        pending_ref.child(username).delete()

        user_group_ref = db.reference(f'users/{username}/groups/{group_id}')
        group_data = group_ref.get()
        user_group_ref.set({
            'group_name': group_data.get('group_name', ''),
            'role': 'member'
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
        'progress': progress_text or ''
    }

    if file and file.filename:
        filename = secure_filename(file.filename)
        user_folder = os.path.join(app.config['UPLOAD_FOLDER'], group_id, task_id, username)
        os.makedirs(user_folder, exist_ok=True)
        filepath = os.path.join(user_folder, filename)
        file.save(filepath)
        progress_data['file'] = filename

    progress_ref.push(progress_data)
    task_ref.update({'completed': True})

    flash('Progress and file submitted successfully.')
    return redirect(url_for('main', username=username, group_id=group_id))

@app.route('/download/<group_id>/<task_id>/<username>/<filename>')
def download_file(group_id, task_id, username, filename):
    directory = os.path.join(app.config['UPLOAD_FOLDER'], group_id, task_id, username)
    return send_from_directory(directory, filename, as_attachment=True)

from flask import request, jsonify
from datetime import datetime

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


@app.route('/get_messages/<group_id>')
def get_messages(group_id):
    messages_ref = db.reference(f'groups/{group_id}/chat')
    messages = messages_ref.get() or {}
    
    message_list = []
    for key, msg in messages.items():
        message_list.append({
            'sender': msg.get('sender', ''),
            'text': msg.get('text', ''),
            'timestamp': msg.get('timestamp', '')
        })

    return jsonify({'messages': message_list})

@app.route('/get_token')
def get_token():
    response = requests.post(
        'https://api.videosdk.live/v2/token',
        json={},
        headers={
            'Authorization': VIDEOSDK_SECRET
        }
    )
    if response.status_code == 200:
        return jsonify({'token': response.json()['token']})
    else:
        return jsonify({'error': 'Unable to generate token'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
