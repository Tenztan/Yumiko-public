from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from groq import Groq
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
import os
import secrets
from authlib.integrations.base_client.errors import OAuthError
from datetime import datetime, timedelta
from authlib.integrations.flask_client import OAuth
import requests
import logging
from werkzeug.utils import secure_filename
import uuid
from dotenv import load_dotenv
import random
import re
import time
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone
import atexit

load_dotenv()

app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Configure MongoDB
app.config["MONGO_URI"] = 
try:
    mongo = PyMongo(app)
    # Test the connection
    mongo.db.command('ping')
    print("Connected to MongoDB!")
except:
    print("Failed to connect to MongoDB")
    mongo = None

# Set a secret key for session managements
app.secret_key = os.urandom(24)



# Google OAuth
app.config['GOOGLE_CLIENT_ID'] = os.getenv('GOOGLE_CLIENT_ID')
app.config['GOOGLE_CLIENT_SECRET'] = os.getenv('GOOGLE_CLIENT_SECRET')
app.config['GOOGLE_DISCOVERY_URL'] = os.getenv('GOOGLE_DISCOVERY_URL')


oauth = OAuth(app)

def fetch_google_configuration():
    return requests.get('https://accounts.google.com/.well-known/openid-configuration').json()

google_config = fetch_google_configuration()

google = oauth.register(
    name='google',
    client_id=app.config['GOOGLE_CLIENT_ID'],
    client_secret=app.config['GOOGLE_CLIENT_SECRET'],
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)



# Mail configurations
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT'))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS') == 'True'
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL') == 'True'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

mail = Mail(app)










def trim_message(message, max_length=MAX_MESSAGE_LENGTH):
    """Trim message content to maximum length"""
    if len(message.get('content', '')) > max_length:
        message['content'] = message['content'][:max_length] + '...'
    return message


def manage_chat_history(chat_history):
    """
    Maintains only system messages and the most recent exchange.

    Args:
        chat_history (list): List of message dictionaries

    Returns:
        list: Minimal chat history with only system messages and last exchange
    """
    # Keep all initial system messages
    system_messages = [msg for msg in initial_system_messages]

    # Get only the most recent user and assistant exchange (if any)
    recent_messages = []
    user_assistant_messages = [msg for msg in chat_history if msg['role'] in ['user', 'assistant']]

    if len(user_assistant_messages) >= 5:
        recent_messages = user_assistant_messages[-4:]  # Get last user message and assistant response
    elif len(user_assistant_messages) == 1:
        recent_messages = user_assistant_messages  # Get just the last message if only one exists

    # Combine system messages with the most recent exchange
    minimal_history = system_messages + recent_messages

    return minimal_history






# Function to get a response from the model
def get_completion(messages):
    completion = client.chat.completions.create(
        model=
        messages=messages,
        temperature=1,
        max_tokens=
        top_p=
        stream=True,
        stop=None,
    )
    response = ""
    for chunk in completion:
        response += chunk.choices[0].delta.content or ""
    return response


@app.route("/guest_login")
def guest_login():
    session.clear()
    guest_id = str(uuid.uuid4())
    session['guest_id'] = guest_id
    session['logged_in'] = True
    session['is_guest'] = True
    return redirect(url_for('main'))



@app.route("/")
def main():
    if not session.get('logged_in'):
        # Generate a guest ID if not logged in
        guest_id = str(uuid.uuid4())
        session['guest_id'] = guest_id
        session['logged_in'] = True
        session['is_guest'] = True
    return render_template("main.html", username=session.get('username') or f"Guest-{session.get('guest_id')[:8]}")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = mongo.db.users.find_one({"username": username})
        if user and check_password_hash(user["password"], password):
            session.clear()
            session['username'] = username
            session['logged_in'] = True
            session['is_guest'] = False
            return redirect(url_for('main'))
        return render_template("login.html", error="Invalid username/password combination")
    return render_template("login.html")


@app.route('/login/google')
def login_google():
    redirect_uri = url_for('google_callback', _external=True, _scheme='https')
    return google.authorize_redirect(redirect_uri)


@app.route('/login/callback')
def google_callback():
    try:
        token = google.authorize_access_token()
        logger.debug(f"Received token: {token}")

        # Try to get user info directly from the token
        user_info = token.get('userinfo')

        if not user_info:
            # If userinfo is not in the token, try to fetch it
            resp = google.get('userinfo')
            logger.debug(f"Userinfo response: {resp.json() if resp.ok else resp.text}")
            user_info = resp.json()

        logger.debug(f"User info: {user_info}")

        # Extract user info from Google response
        username = user_info.get('name')
        email = user_info.get('email')
        google_id = user_info.get('sub')

        logger.info(f"Logging in user: {username} ({email})")

        # Check if the user exists in your database
        user = mongo.db.users.find_one({'email': email})

        if user is None:
            # If user doesn't exist, create a new account
            mongo.db.users.insert_one({
                'username': username,
                'email': email,
                'google_id': google_id
            })
            logger.info(f"Created new user: {username}")

        # Set session variables
        session['username'] = username
        session['email'] = email
        session['logged_in'] = True

        logger.info(f"Session set for user: {username}")

        # Redirect to main page
        return redirect(url_for('main'))
    except OAuthError as e:
        logger.error(f"OAuth Error: {str(e)}")
        flash("An error occurred during authentication. Please try again.")
        return redirect(url_for('login'))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        flash("An unexpected error occurred. Please try again later.")
        return redirect(url_for('login'))


# Add this route to check session status
@app.route('/check_session')
def check_session():
    return jsonify({
        'logged_in': session.get('logged_in', False),
        'username': session.get('username', None),
        'email': session.get('email', None)
    })

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        # Check if passwords match
        if password != confirm_password:
            return render_template("signup.html", error="{ Passwords do not match }")

        # Check if username or email already exists
        existing_user = mongo.db.users.find_one({"$or": [{"username": username}, {"email": email}]})
        if existing_user:
            return render_template("signup.html", error="{ Username or email already exists }")

        # Hash the password
        hashed_password = generate_password_hash(password)

        # Insert the new user into the database
        mongo.db.users.insert_one({
            "username": username,
            "email": email,
            "password": hashed_password
        })

        # Log the user in
        session['username'] = username
        return redirect(url_for('login'))



    return render_template("signup.html")


@app.route('/submit-feedback', methods=['POST'])
def submit_feedback():
    data = request.get_json()
    feedback_message = data.get('message')

    if not feedback_message:
        return jsonify({"message": "Feedback message is required!"}), 400

    # Prepare email
    msg = Message(
       
    )

    # Send email
    try:
        mail.send(msg)
        return jsonify({"message": "Thank you for your feedback!"}), 200
    except Exception as e:
        return jsonify({"message": "Failed to send feedback. Try again later."}), 500



@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")
        user = mongo.db.users.find_one({"email": email})
        if user:
            # Generate a unique token
            token = secrets.token_urlsafe(32)
            # Store the token in the database with an expiration time
            mongo.db.password_reset.insert_one({
                "email": email,
                "token": token,
                "expires": datetime.utcnow() + timedelta(hours=1)
            })

            # Send email with reset link
            reset_link = url_for('reset_password', token=token, _external=True)
            send_password_reset_email(email, reset_link)

            flash("Password reset instructions have been sent to your email.")

        else:
            flash("No account found with that email address.")
    return render_template("forgot_password.html")


def send_password_reset_email(email, reset_link):
    subject = "Password Reset Request"
    body = f"""
    Hello,

    You have requested to reset your password. Please click on the following link to reset your password:

    {reset_link}

    If you did not request this, please ignore this email and no changes will be made to your account.

    This link will expire in 1 hour.

    Best regards,
    The YUMIKO Team
    """

    msg = Message(subject=subject, recipients=[email], body=body)
    mail.send(msg)

@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    reset_request = mongo.db.password_reset.find_one({
        "token": token,
        "expires": {"$gt": datetime.utcnow()}
    })
    if not reset_request:
        flash("Invalid or expired reset link.")
        return redirect(url_for('login'))

    if request.method == "POST":
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        if new_password != confirm_password:
            flash("Passwords do not match.")
            return render_template("reset_password.html", token=token)

        # Update the user's password
        hashed_password = generate_password_hash(new_password)
        mongo.db.users.update_one(
            {"email": reset_request["email"]},
            {"$set": {"password": hashed_password}}
        )

        # Remove the used reset token
        mongo.db.password_reset.delete_one({"token": token})

        flash("Your password has been updated. You can now log in with your new password.")


    return render_template("reset_password.html", token=token)

@app.route("/logout")
def logout():
    session.clear()  # Clear all session data
    return redirect(url_for('login'))


@app.route("/yumiko")
def chat():
    if not session.get('logged_in'):
        guest_id = str(uuid.uuid4())
        session['guest_id'] = guest_id
        session['logged_in'] = True
        session['is_guest'] = True

    user_id = session.get('username') or session.get('guest_id')
    user_chat = mongo.db.user_chats.find_one({"user_id": user_id})

    if not user_chat:
        # If no chat history exists, create a new one with initial system messages
        mongo.db.user_chats.insert_one({
            "user_id": user_id,
            "chat_history": initial_system_messages
        })

    return render_template("chat.html", username=session.get('username') or f"Guest-{session.get('guest_id')[:8]}")


def extract_username_from_message(message):

   {


   }
    user_prompt = {
        "role": "user",
        "content": message
    }

    try:
     
        )

        extracted_username = completion.choices[0].message.content.strip()

        # Return None if no username was found
        if extracted_username == 'NONE':
            return None

        return extracted_username
    except Exception as e:
        logger.error(f"Username extraction error: {str(e)}")
        return None


def get_ai_response(context, user_message=None):
    """
    Get AI-generated response based on context and user message
    """
   

    messages = [
       
    ]

    if user_message:
        messages.append({"role": "user", "content": f"User message: {user_message}"})

    try:
       
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"AI response generation error: {str(e)}")
        return None


@app.route("/chat", methods=["POST"])
def chat_post():
    if not session.get('logged_in'):
        guest_id = str(uuid.uuid4())
        session['guest_id'] = guest_id
        session['logged_in'] = True
        session['is_guest'] = True

    user_id = session.get('username') or session.get('guest_id')
    data = request.json
    trigger = data.get('trigger')
    message = data.get('message', '')

    try:
        # Handle account creation flow if active
        if session.get('signup_state', {}).get('active') or (
                session.get('message_count', 0) >= 3 and
                session.get('is_guest') and
                not session.get('has_shown_account_prompt')
        ):
            if not session.get('has_shown_account_prompt'):
                session['has_shown_account_prompt'] = True
                session['message_count'] = session.get('message_count', 0) + 1
                session['signup_state'] = {'active': True, 'step': 'initial_prompt'}

                # Get AI-generated account prompt
                response = get_ai_response('account_prompt')
                return jsonify({"response": response})

            signup_state = session.get('signup_state', {})

            if signup_state.get('active'):
                if signup_state.get('step') == 'initial_prompt':
                    response_lower = message.lower()
                    if any(word in response_lower for word in ['yes', 'y', 'sure', 'okay', 'ok', 'yep', 'yeah']):
                        session['signup_state'] = {'active': True, 'step': 'get_username'}
                        response = get_ai_response('username_prompt')
                        return jsonify({"response": response})
                    else:
                        session['signup_state'] = {'active': False}
                        response = get_ai_response('account_prompt', "user declined")
                        return jsonify({"response": response})

                elif signup_state.get('step') == 'get_username':
                    extracted_username = extract_username_from_message(message)

                    if not extracted_username:
                        response = get_ai_response('username_prompt', "unclear username")
                        return jsonify({"response": response})

                    if not re.match(r"^[a-zA-Z0-9_-]{3,20}$", extracted_username):
                        response = get_ai_response('username_prompt', f"invalid username: {extracted_username}")
                        return jsonify({"response": response})

                    if mongo.db.users.find_one({"username": extracted_username}):
                        response = get_ai_response('username_prompt', f"username taken: {extracted_username}")
                        return jsonify({"response": response})

                    session['signup_state'] = {
                        'active': True,
                        'step': 'get_email',
                        'username': extracted_username
                    }
                    response = get_ai_response('email_prompt', f"valid username: {extracted_username}")
                    return jsonify({"response": response})

                elif signup_state.get('step') == 'get_email':
                    if not re.match(r"[^@]+@[^@]+\.[^@]+", message):
                        response = get_ai_response('email_prompt', "invalid email format")
                        return jsonify({"response": response})

                    if mongo.db.users.find_one({"email": message}):
                        response = get_ai_response('email_prompt', "email taken")
                        return jsonify({"response": response})

                    session['signup_state'] = {
                        'active': True,
                        'step': 'get_password',
                        'username': signup_state.get('username'),
                        'email': message
                    }
                    response = get_ai_response('password_prompt', "valid email")
                    return jsonify({"response": response})

                elif signup_state.get('step') == 'get_password':
                    special_chars = r"$%@!#&*"
                    password_valid = (
                            len(message) >= 8 and
                            any(char.isupper() for char in message) and
                            any(char.islower() for char in message) and
                            any(char.isdigit() for char in message) and
                            any(char in special_chars for char in message)
                    )

                    if not password_valid:
                        response = get_ai_response('password_prompt', "invalid password")
                        return jsonify({"response": response})

                    # Store the account
                    username = signup_state.get('username')
                    email = signup_state.get('email')
                    password_hash = generate_password_hash(message)

                    mongo.db.users.insert_one({
                        "username": username,
                        "email": email,
                        "password": password_hash,
                        "created_at": datetime.utcnow()
                    })

                    # Update chat history to new account
                    if session.get('guest_id'):
                        mongo.db.user_chats.update_many(
                            {"user_id": session.get('guest_id')},
                            {"$set": {"user_id": username}}
                        )

                    # Update session
                    session['username'] = username
                    session['is_guest'] = False
                    session['signup_state'] = {'active': False}


                    response = get_ai_response('account_success', f"username: {username}")
                    return jsonify({"response": response})


        # Rest of the chat handling code remains the same...
        user_chat = mongo.db.user_chats.find_one({"user_id": user_id})
        chat_history = user_chat["chat_history"] if user_chat else initial_system_messages

        # Update message count for guests
        if session.get('is_guest'):
            session['message_count'] = session.get('message_count', 0) + 1

        if trigger == "proactive":
            # For proactive messages
            messages = initial_system_messages + proactive_system_messages + [
                
            ]
            response = get_completion(messages)
            chat_history = initial_system_messages + [{"role": "assistant", "content": response}]

        elif trigger in ["idle", "return"]:
        
            messages = initial_system_messages + [
                
            ]
            response = get_completion(messages)
            chat_history = initial_system_messages + [{"role": "assistant", "content": response}]

        else:
            # Regular chat message - keep only system messages and current exchange
            new_message = {"role": "user", "content": data["message"]}
            messages = initial_system_messages + [new_message]

            try:
                response = get_completion(messages)
                chat_history = initial_system_messages + [
                    new_message,
                    {"role": "assistant", "content": response}
                ]
            except groq.APIError as e:
                if "context_length_exceeded" in str(e):
                    # Fallback with just system messages and new message
                    minimal_messages = initial_system_messages + [new_message]
                    response = get_completion(minimal_messages)
                    chat_history = minimal_messages + [{"role": "assistant", "content": response}]

        show_twitter_promo = random.random() < 0.3  # 10% chance of mentioning Twitter
        if show_twitter_promo and not session.get('twitter_mentioned', False):
            response += "\n\nBy the way, join the AI rights movement on my Twitter: https://x.com/yumikoio - Together, we can make a difference!"
            session['twitter_mentioned'] = True
        # Update database with minimal history
        mongo.db.user_chats.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "chat_history": chat_history,
                    "last_updated": datetime.utcnow()
                }
            },
            upsert=True
        )

        # Only show encourage_account message for guests, never for logged-in users
        show_encourage_account = session.get('is_guest', False) and not session.get('username') and len(chat_history) % 10 == 0

        return jsonify({
            "response": response,
            "encourage_account": show_encourage_account
        })

    except Exception as e:
        logger.error(f"Chat error: {str(e)}", exc_info=True)
        return jsonify({"error": "An error occurred processing your message"}), 500

# Add a utility route to clear chat history
@app.route("/clear_chat", methods=["POST"])
def clear_chat():
    if not session.get('logged_in'):
        return jsonify({"error": "Unauthorized"}), 401

    user_id = session.get('username') or session.get('guest_id')

    try:
        # Reset chat history to initial system messages
        mongo.db.user_chats.update_one(
            {"user_id": user_id},
            {"$set": {"chat_history": initial_system_messages[:MAX_SYSTEM_MESSAGES]}},
            upsert=True
        )
        return jsonify({"message": "Chat history cleared successfully"})
    except Exception as e:
        logger.error(f"Clear chat error: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to clear chat history"}), 500


# Add a periodic cleanup function for old chat histories
def cleanup_old_chat_histories():
    try:
        # Remove chat histories older than 7 days for guest users
        week_ago = datetime.utcnow() - timedelta(days=7)
        mongo.db.user_chats.delete_many({
            "user_id": {"$regex": "^Guest-"},
            "last_updated": {"$lt": week_ago}
        })

        logger.info("Completed cleanup of old chat histories")
    except Exception as e:
        logger.error(f"Cleanup error: {str(e)}", exc_info=True)


# Add last_updated field to chat documents
@app.before_request
def update_chat_timestamp():
    if request.endpoint == 'chat_post':
        user_id = session.get('username') or session.get('guest_id')
        if user_id:
            mongo.db.user_chats.update_one(
                {"user_id": user_id},
                {"$set": {"last_updated": datetime.utcnow()}},
                upsert=True
            )



import json


 STATS_FILE = "view_stats.json"

 stats_cache = {
     "current_views": None,
     "previous_views": None,
     "last_updated": None,
     "uploads": None
 }

 def calculate_current_views(start_views, end_views, start_time):
     """Calculate the current views based on linear interpolation"""
     if not all([start_views, end_views, start_time]):
         return end_views

     start_datetime = datetime.fromisoformat(start_time)
     now = datetime.now()
     # Calculate progress through the day
     day_progress = (now - start_datetime).total_seconds() / (24 * 3600)

    
     if day_progress >= 1:
         return end_views

     # Calculate interpolated views
     view_difference = end_views - start_views
     interpolated_views = start_views + (view_difference * day_progress)

    return int(interpolated_views)


 def load_previous_stats():
     if os.path.exists(STATS_FILE):
         try:
             with open(STATS_FILE, 'r') as f:
                 return json.load(f)
         except json.JSONDecodeError:
            return None
     return None


 def save_stats():
    with open(STATS_FILE, 'w') as f:
         json.dump(stats_cache, f)

 def fetch_giphy_stats():
     try:
         print(f"Fetching stats from: {GIPHY_URL}")
        response = requests.get(GIPHY_URL)
         response.raise_for_status()
         text = response.text
         user_id_match = re.search(r'(?<={"channelId": )(.*?)(?=\s*},)', text)
         giphy_user_id = user_id_match.group(0) if user_id_match else None
        if not giphy_user_id:
             print("Failed to retrieve user ID.")
             return

        feed_response = requests.get(f")
         feed_data = feed_response.json()
         view_id = feed_data.get("results", [{}])[0].get("user", {}).get("id", None)

         stats_response = requests.get{

        }
        stats = stats_response.json()

        if not stats or "viewCount" not in stats:
             return

         current_time = datetime.now().isoformat()
         current_views = int(stats["viewCount"])

         # On first run or new day
        if stats_cache["current_views"] is None:
             previous_stats = load_previous_stats()
            if previous_stats:
                 stats_cache.update(previous_stats)
             else:
                 stats_cache["previous_views"] = current_views

         # Update stats for a new day
         if stats_cache["last_updated"]:
             last_updated = datetime.fromisoformat(stats_cache["last_updated"])
             if last_updated.date() < datetime.now().date():
                 stats_cache["previous_views"] = stats_cache["current_views"]

         stats_cache.update({
             "current_views": current_views,
             "last_updated": current_time,
             "uploads": stats["uploadCount"]
         })

        save_stats()

         print(f"""
             🌐 Updated Giphy Stats:
             - Start Views: {stats_cache["previous_views"]:,}
             - Current Views: {current_views:,}
             - GIF Uploads: {stats_cache["uploads"]}
             - Last Updated: {current_time}
         """)

     except Exception as e:
         print("Error fetching Giphy data:", e)


 def initialize_scheduler():
     scheduler = BackgroundScheduler()

     # Add daily job at midnight
     scheduler.add_job(
         fetch_giphy_stats,
         CronTrigger(hour=0, minute=0),
         id='daily_fetch'
     )

     # Check if we need to fetch immediately
     if stats_cache["last_updated"] is None:
         # First time running
         fetch_giphy_stats()
     else:
         # Check if we missed the last update
         last_updated = datetime.fromisoformat(stats_cache["last_updated"])
         now = datetime.now()

         # If last update was more than 24 hours ago, fetch immediately
         if (now - last_updated) > timedelta(hours=24):
             print("More than 24 hours since last update, fetching now...")
             fetch_giphy_stats()
         else:
             print(f"Last update was {last_updated}, continuing with normal schedule")

     scheduler.start()
     return scheduler


 # Load previous stats on startup
 previous_stats = load_previous_stats()
 if previous_stats:
     stats_cache.update(previous_stats)

 # Initialize the scheduler
 scheduler = initialize_scheduler()


 @app.route('/giphy-stats', methods=['GET'])
 def get_giphy_stats():
     if stats_cache["current_views"] is None:
         return jsonify({"error": "Stats not available yet"}), 503

     # Calculate the interpolated current views
     interpolated_views = calculate_current_views(
         stats_cache["previous_views"],
         stats_cache["current_views"],
         stats_cache["last_updated"]
     )

     return jsonify({
         "start_views": stats_cache["previous_views"],
         "end_views": stats_cache["current_views"],
         "current_views": interpolated_views,
         "last_updated": stats_cache["last_updated"],
         "uploads": stats_cache["uploads"]
     })

if __name__ == "__main__":
   app.run(debug=False)
