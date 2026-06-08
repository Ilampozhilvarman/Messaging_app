from pymongo import MongoClient
from flask import Flask, render_template, request, redirect, url_for, session
from bson import ObjectId
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
import time
from agora_token_builder import RtcTokenBuilder
h
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
connection_string = os.getenv("MONGO_URI")
AGORA_APP_ID = os.getenv("AGORA_APP_ID")
AGORA_APP_CERTIFICATE = os.getenv("AGORA_APP_CERTIFICATE")
client = MongoClient(connection_string)
db = client["db"]

def create_user(username: str, password: str) -> dict:
    return {
        "_id": ObjectId(),
        "username": username,
        "password": password,
    }

def create_message(text: str, chat_id: ObjectId, sender_id: ObjectId, order: int) -> dict:
    return {
        "_id": ObjectId(),
        "chat_id": chat_id,
        "sender_id": sender_id,
        "text": text,
        "order": order
    }

def create_group_chat_obj(chat_name: str, member_ids: list[ObjectId], owner_id: ObjectId) -> dict:
    return {
        "_id": ObjectId(),
        "chat_name": chat_name,
        "member_ids": member_ids,
        "owner_id": owner_id
    }

import time
from agora_token_builder import RtcTokenBuilder #

# Load Agora credentials
AGORA_APP_ID = os.getenv("AGORA_APP_ID")
AGORA_APP_CERTIFICATE = os.getenv("AGORA_APP_CERTIFICATE")

@app.route("/get-token")
def get_token():
    if "user_id" not in session or "gc_id" not in session:
        return {"error": "Unauthorized"}, 401
    channel_name = session["gc_id"] 
    uid = 0
    role = 1
    expiration_time_in_seconds = 3600
    current_timestamp = int(time.time())
    privilege_expired_ts = current_timestamp + expiration_time_in_seconds #
    token = RtcTokenBuilder.buildTokenWithUid(
        AGORA_APP_ID, 
        AGORA_APP_CERTIFICATE, 
        channel_name, 
        uid, 
        role, 
        privilege_expired_ts
    )
    return {
        "token": token,
        "channel": channel_name,
        "appId": AGORA_APP_ID
    }


@app.route("/")
def home():
    return render_template("log_in.html")

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    gcs = db['group_chats'].find({'member_ids': ObjectId(session['user_id'])})
    return render_template('index.html', group_chats=gcs)

@app.route("/login", methods=["POST"])
def log_in():
    username = request.form.get("username")
    password = request.form.get("password")
    if 8 > len(username) or len(username) > 16 or len(password) > 16 or len(password) < 8:
        print("username and password must be between 8-16 chars.")
        return render_template("log_in.html", error="Invalid username or password length.")
    else:
        user = db["users"].find_one({"username": username})
        if not user or not check_password_hash(user["password"], password):
            print("Authentication failed.")
            return render_template("log_in.html", error="Incorrect username or password.")
        print(f"user {user['username']} has been found.")
        session["user_id"] = str(user["_id"])
        gcs = list(db["group_chats"].find({"member_ids": user["_id"]}))
        return redirect(url_for("dashboard"))

@app.route("/signup", methods=["GET"])
def signup_page():
    return render_template("sign_up.html")

@app.route("/signup", methods=["POST"])
def signup():
    username = request.form.get("username")
    password = request.form.get("password")
    if len(username) < 8 or len(username) > 16:
        print("username and password must be between 8-16 chars.")
        return render_template("sign_up.html", error="Invalid username or password length.")
    does_another_user_exist = db["users"].find_one({"username": username})
    if does_another_user_exist:
        print("This username already exists.")
        return render_template("sign_up.html", error="Username is already taken.")
    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
    user_doc = create_user(username, hashed_password)
    db["users"].insert_one(user_doc)
    session["user_id"] = str(user_doc["_id"])
    return redirect(url_for("dashboard"))

@app.route('/chat/<gc_name>/call')
def call_room(gc_name):
    if "user_id" not in session:
        print("something went wrong.") 
        return redirect(url_for("home")) 
    gc = db["group_chats"].find_one({"chat_name": gc_name})
    if not gc:
        print("Gc has not been found.")
        return redirect(url_for("dashboard"))
    session["gc_id"] = str(gc["_id"])
    return render_template("call.html", gc_name=gc_name, gc_id=str(gc["_id"]))

@app.route('/chat/<gc_name>')
def group_chat(gc_name):
    if "user_id" not in session:
        return redirect(url_for("home"))
    gc = db["group_chats"].find_one({"chat_name": gc_name})
    if not gc:
        return render_template("index.html")
    session["gc_id"] = str(gc["_id"])
    owner = gc["owner_id"]
    gc_messages_ordered = list(db["messages"].find({"chat_id": gc["_id"]}).sort("order", 1))
    for message in gc_messages_ordered:
        sender_user = db["users"].find_one({"_id": message["sender_id"]})
        if sender_user:
            message["sender_name"] = sender_user["username"]
        else:
            message["sender_name"] = "Unknown User"
    return render_template("gc.html", messages=gc_messages_ordered, user_id=ObjectId(session["user_id"]), owner_id=owner, gc_name=gc_name)

@app.route("/send-message", methods=["POST"])
def message_sent():
    if "user_id" not in session or "gc_id" not in session:
        return redirect(url_for("home"))
    new_message = request.form.get("message")
    chat_id = ObjectId(session["gc_id"])
    gc = db["group_chats"].find_one({"_id": chat_id})
    owner = gc["owner_id"]
    if new_message.replace(" ", "") == "":
        return redirect(url_for("group_chat", gc_name=gc["chat_name"], owner_id=owner))
    last_msg = db['messages'].find_one({'chat_id': ObjectId(session["gc_id"])}, sort=[('order', -1)])
    last_order = last_msg['order'] if last_msg else 1
    new_order = last_order + 1
    db["messages"].insert_one(create_message(new_message, ObjectId(session["gc_id"]), ObjectId(session["user_id"]), new_order))
    return redirect(url_for("group_chat", gc_name=gc["chat_name"]))

@app.route("/new-gc", methods=["POST", "GET"])
def new_gc():
    if request.method == 'GET':
        return render_template('new_gc.html')
    gc_name = request.form.get("gc-name")
    if len(gc_name) > 16 or len(gc_name) < 8:
        return render_template("new_gc.html", error="Group Chat name must be between 8 and 16 characters long.")
    
    does_gc_exist_already = db["group_chats"].find_one({"chat_name": gc_name})
    if does_gc_exist_already:
        return render_template("new_gc.html", error="Group chat name already exists.")
    db["group_chats"].insert_one(create_group_chat_obj(gc_name, [ObjectId(session["user_id"])], ObjectId(session["user_id"])))
    return redirect(url_for("dashboard"))

@app.route("/finish-changes")
def finished_changes():
    return redirect(url_for("dashboard"))

@app.route("/edit-gc")
def go_to_edit_page():
    if "user_id" not in session or "gc_id" not in session:
        return redirect(url_for("home"))
    current_gc = db["group_chats"].find_one({"_id": ObjectId(session["gc_id"])})
    if current_gc["owner_id"] != ObjectId(session["user_id"]):
        return "Unauthorized", 403
    return render_template("edit_gc.html", gc=current_gc)

@app.route("/add-user", methods=["POST"])
def add_user():
    if "user_id" not in session or "gc_id" not in session:
        return redirect(url_for("home"))
    
    new_user_name = request.form.get("add-user")
    new_user = db["users"].find_one({"username": new_user_name })
    chat_id = ObjectId(session["gc_id"])
    gc = db["group_chats"].find_one({"_id": chat_id})

    if gc["owner_id"] != ObjectId(session["user_id"]):
        return "Unauthorized", 403
    
    if not new_user:
        return render_template("edit_gc.html", gc=gc, error="User does not exist.")
    
    if new_user["_id"] in gc["member_ids"]:
        return render_template("edit_gc.html", gc=gc, error="User is already in this chat.")
    
    db["group_chats"].update_one({"_id": chat_id}, {"$push": {"member_ids": new_user["_id"]}})
    print("User has been added.")
    return redirect(url_for("go_to_edit_page"))

@app.route("/del-user", methods=["POST"])
def del_user():
    if "user_id" not in session or "gc_id" not in session:
        return redirect(url_for("home"))
    
    new_user_name = request.form.get("remove-user")
    new_user = db["users"].find_one({"username": new_user_name})
    chat_id = ObjectId(session["gc_id"])
    gc = db["group_chats"].find_one({"_id": chat_id})

    if gc["owner_id"] != ObjectId(session["user_id"]):
        return "Unauthorized", 403
    
    if not new_user:
        return render_template("edit_gc.html", gc=gc, error="User does not exist.")
    
    if new_user["_id"] == gc["owner_id"]:
        return render_template("edit_gc.html", gc=gc, error="Owners cannot remove themselves.")

    if new_user["_id"] not in gc["member_ids"]:
        return render_template("edit_gc.html", gc=gc, error="User is not a member of this chat.")
    db["group_chats"].update_one({"_id": chat_id}, {"$pull": {"member_ids": new_user["_id"]}})
    print("User has been deleted.")
    return redirect(url_for("go_to_edit_page"))

@app.route("/delete-gc", methods=["POST"])
def delete_gc():
    if "user_id" not in session or "gc_id" not in session:
        return redirect(url_for("home"))
    gc = db["group_chats"].find_one({"_id": ObjectId(session["gc_id"])})
    if not gc or gc["owner_id"] != ObjectId(session["user_id"]):
        return "Unauthorized", 403
    
    if not gc:
        return redirect(url_for("dashboard"))
    
    if gc["owner_id"] != ObjectId(session["user_id"]):
        return render_template("edit_gc.html", gc=gc, error="You are not authorized to delete this group.")
    
    db["messages"].delete_many({"chat_id": ObjectId(session["gc_id"])})
    db["group_chats"].delete_one({"_id": ObjectId(session["gc_id"])})
    session.pop('gc_id', None)
    return redirect(url_for("dashboard"))

@app.route("/delete-user")
def delete_main_user():
    user_to_delete = db["users"].find_one({"_id": ObjectId(session["user_id"])})
    user_id = ObjectId(session["user_id"])
    if not user_to_delete:
        print("Something went wrong.")
        return redirect(url_for("dashboard"))
    db["users"].delete_one({"_id": user_id})
    all_gcs_user_owns = db["group_chats"].delete_many({"owner_id": user_id})
    all_messages_sent_by_user = db["messages"].delete_many({"sender_id": user_id})
    print(f"Gcs {all_gcs_user_owns} have been deleted.")
    print(f"Mesages {all_messages_sent_by_user} have been deleted.")
    session.clear()
    return redirect(url_for("home"))

@app.route("/delete-message/<message_id>", methods=["POST"])
def del_message(message_id):
    if "user_id" not in session or "gc_id" not in session:
        return redirect(url_for("home"))
    chat_id = ObjectId(session["gc_id"])
    gc = db["group_chats"].find_one({"_id": chat_id})
    if not gc:
        return redirect(url_for("dashboard"))
    if gc["owner_id"] != ObjectId(session["user_id"]):
        return "Unauthorized Action", 403
    target_message_id = ObjectId(message_id)
    db["messages"].delete_one({"_id": target_message_id})
    print(f"Message {message_id} was deleted by owner.")
    return redirect(url_for("group_chat", gc_name=gc["chat_name"]))


if __name__ == "__main__":
    app.run(debug=True, port=8080)

