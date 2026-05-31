from flask import Flask, request, jsonify, Response
import json
import hashlib
import time
import gzip
import io

app = Flask(__name__)


users = {}      
player_data = {} 
user_data = {}   

def parse_param(req):
    
    if req.method == "GET":
        raw = req.args.get("param", "{}")
    else:
        raw = req.form.get("param", "{}")
    try:
        return json.loads(raw)
    except:
        return {}

def gzip_response(data: str):
    
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode='wb') as f:
        f.write(data.encode('utf-8'))
    return Response(
        buf.getvalue(),
        status=200,
        headers={
            "Content-Type": "text/plain;charset=utf-8",
            "Content-Encoding": "gzip",
            "Server": "Shadowgun: Deadzone/1.0"
        }
    )

def make_pw(userid, password):
    return hashlib.md5(f"{userid}:{password}".encode()).hexdigest()

def default_player_data(userid):
    return {
        "UserId": userid,
        "Level": 1,
        "Xp": 0,
        "Credits": 99999,
        "Gold": 9999,
        "IsPremium": True,
        "EquippedItems": [],
        "OwnedItems": [],
        "Kills": 0,
        "Deaths": 0,
        "Wins": 0,
        "Losses": 0,
        "Rank": 1,
        "Avatar": 0
    }


@app.route("/sgdz/getAppVersion", methods=["GET"])
def get_app_version():
    return gzip_response(json.dumps({
        "result": "ok",
        "version": "2.10.0",
        "needsUpdate": False,
        "obbValid": True
    }))


@app.route("/sgdz/getProductData", methods=["GET"])
def get_product_data():
    p = parse_param(request)
    param = p.get("param", "")

    if param == "_ShopItems":
        data = {
            "result": "ok",
            "items": [
                {"id": "weapon_rifle", "name": "Assault Rifle", "price": 100, "currency": "Credits"},
                {"id": "weapon_shotgun", "name": "Shotgun", "price": 150, "currency": "Credits"},
                {"id": "weapon_sniper", "name": "Sniper Rifle", "price": 200, "currency": "Credits"},
                {"id": "armor_basic", "name": "Basic Armor", "price": 80, "currency": "Credits"},
                {"id": "armor_heavy", "name": "Heavy Armor", "price": 300, "currency": "Credits"},
                {"id": "premium_week", "name": "Premium 1 Week", "price": 50, "currency": "Gold"},
            ]
        }
    else:
        data = {"result": "ok", "data": {}}

    return gzip_response(json.dumps(data))


@app.route("/sgdz/userExists", methods=["GET"])
def user_exists():
    p = parse_param(request)
    userid = p.get("userid", "")
    pw = p.get("pw", "")

    if userid not in users:
        return gzip_response("0")

    if pw and users[userid]["pw"] != pw:
        return gzip_response("0")

    return gzip_response("1")


@app.route("/sgdz/CreateUser", methods=["POST"])
def create_user():
    p = parse_param(request)
    userid = p.get("userid", "")
    password = p.get("pw", "")
    email = p.get("email", "")

    if not userid:
        return gzip_response(json.dumps({"result": "error", "msg": "No userid"}))

    if userid in users:
        return gzip_response(json.dumps({"result": "error", "msg": "User already exists"}))

    users[userid] = {
        "pw": password,
        "email": email,
        "created": int(time.time())
    }
    player_data[userid] = default_player_data(userid)
    user_data[userid] = {"_Friends": []}

    return gzip_response(json.dumps({"result": "ok", "userid": userid}))


@app.route("/sgdz/userGetPrimaryKey", methods=["GET"])
def user_get_primary_key():
    p = parse_param(request)
    userid = p.get("userid", "")
    pw = p.get("pw", "")

    if userid not in users:
        return gzip_response(json.dumps({"result": "error", "msg": "User not found"}))

    key = hashlib.md5(f"{userid}:shadowgun".encode()).hexdigest()
    return gzip_response(json.dumps({
        "result": "ok",
        "primaryKey": key,
        "userid": userid
    }))


@app.route("/sgdz/getUsrPerProductData", methods=["GET"])
def get_usr_per_product_data():
    p = parse_param(request)
    userid = p.get("userid", "")
    param = p.get("param", "")

    if userid not in player_data:
        player_data[userid] = default_player_data(userid)

    if param == "_PlayerData":
        return gzip_response(json.dumps({
            "result": "ok",
            "data": player_data[userid]
        }))

    return gzip_response(json.dumps({"result": "ok", "data": {}}))


@app.route("/sgdz/getUsrData", methods=["GET"])
def get_usr_data():
    p = parse_param(request)
    userid = p.get("userid", "")
    param = p.get("param", "")

    if userid not in user_data:
        user_data[userid] = {"_Friends": []}

    val = user_data[userid].get(param, [])
    return gzip_response(json.dumps({"result": "ok", "data": val}))


@app.route("/sgdz/UserAddProductData", methods=["POST"])
def user_add_product_data():
    p = parse_param(request)
    userid = p.get("userid", "")

    if userid not in player_data:
        player_data[userid] = default_player_data(userid)

    return gzip_response(json.dumps({"result": "ok"}))


@app.route("/sgdz/BuyItem", methods=["POST"])
def buy_item():
    p = parse_param(request)
    userid = p.get("userid", "")
    item_id = p.get("itemId", "")

    if userid not in player_data:
        player_data[userid] = default_player_data(userid)

    if item_id and item_id not in player_data[userid]["OwnedItems"]:
        player_data[userid]["OwnedItems"].append(item_id)

    return gzip_response(json.dumps({
        "result": "ok",
        "userid": userid,
        "itemId": item_id,
        "playerData": player_data[userid]
    }))


@app.route("/sgdz/EquipItem", methods=["POST"])
def equip_item():
    p = parse_param(request)
    userid = p.get("userid", "")
    item_id = p.get("itemId", "")

    if userid not in player_data:
        player_data[userid] = default_player_data(userid)

    equipped = player_data[userid]["EquippedItems"]
    if item_id and item_id not in equipped:
        equipped.append(item_id)

    return gzip_response(json.dumps({
        "result": "ok",
        "playerData": player_data[userid]
    }))


@app.route("/sgdz/UnEquipItem", methods=["POST"])
def unequip_item():
    p = parse_param(request)
    userid = p.get("userid", "")
    item_id = p.get("itemId", "")

    if userid in player_data:
        equipped = player_data[userid]["EquippedItems"]
        if item_id in equipped:
            equipped.remove(item_id)

    return gzip_response(json.dumps({
        "result": "ok",
        "playerData": player_data.get(userid, {})
    }))


@app.route("/sgdz/BuyPremiumAccount", methods=["POST"])
def buy_premium():
    p = parse_param(request)
    userid = p.get("userid", "")

    if userid in player_data:
        player_data[userid]["IsPremium"] = True

    return gzip_response(json.dumps({"result": "ok", "isPremium": True}))


@app.route("/sgdz/BatchCommand", methods=["POST"])
def batch_command():
    p = parse_param(request)
    userid = p.get("userid", "")

    return gzip_response(json.dumps({
        "result": "ok",
        "userid": userid,
        "batchResult": []
    }))


@app.route("/sgdz/getCloudDateTime", methods=["GET"])
def get_cloud_datetime():
    return gzip_response(json.dumps({
        "result": "ok",
        "datetime": int(time.time()),
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }))


@app.route("/sgdz/getSMJackpot", methods=["GET"])
def get_sm_jackpot():
    return gzip_response(json.dumps({
        "result": "ok",
        "jackpot": 5000
    }))


@app.route("/sgdz/SlotMachineSpin", methods=["POST"])
def slot_machine_spin():
    p = parse_param(request)
    userid = p.get("userid", "")
    import random
    reward = random.choice(["Credits:100", "Credits:500", "Gold:10", "Item:weapon_rifle"])
    return gzip_response(json.dumps({
        "result": "ok",
        "reward": reward,
        "playerData": player_data.get(userid, {})
    }))


@app.route("/sgdz/fetchInboxMsgs", methods=["GET"])
def fetch_inbox_msgs():
    return gzip_response(json.dumps({
        "result": "ok",
        "messages": [
            {
                "id": 1,
                "from": "Shadowgun: Deadzone",
                "subject": "Welcome back!",
                "body": "The server is alive again. Enjoy playing!",
                "timestamp": int(time.time())
            }
        ]
    }))


@app.route("/sgdz/clanapi", methods=["GET"])
def clan_api():
    cmd = request.args.get("cmd", "")
    username = request.args.get("username", "")

    if cmd == "clanbyuser":
        return gzip_response(json.dumps({
            "result": "ok",
            "clan": None
        }))

    return gzip_response(json.dumps({"result": "ok"}))


@app.route("/sgdz/cloudapi", methods=["GET"])
def cloud_api():
    cmd = request.args.get("cmd", "")
    username = request.args.get("username", "")

    if cmd == "getrevisionlog":
        return gzip_response(json.dumps({
            "result": "ok",
            "log": [{"version": "2.10.0", "notes": "Shadowgun: Deadzone server online!"}]
        }))

    if cmd == "getleaderboard":
        return gzip_response(json.dumps({
            "result": "ok",
            "leaderboard": [
                {"rank": 1, "username": username or "Player1", "kills": 100, "xp": 5000}
            ]
        }))

    if cmd == "getleaderboardself":
        return gzip_response(json.dumps({
            "result": "ok",
            "rank": 1,
            "username": username,
            "kills": 0,
            "xp": 0
        }))

    return gzip_response(json.dumps({"result": "ok"}))


@app.route("/sgdz/RequestResetPassword", methods=["POST"])
def reset_password():
    return gzip_response(json.dumps({"result": "ok", "msg": "Reset not needed on Shadowgun: Deadzone server"}))


@app.route("/sgdz/<path:endpoint>", methods=["GET", "POST"])
def catch_all(endpoint):
    return gzip_response(json.dumps({"result": "ok"}))


@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "server": "Shadowgun: Deadzone",
        "status": "online",
        "version": "1.0.0",
        "users": len(users),
        "by": "vurkz-dev"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
