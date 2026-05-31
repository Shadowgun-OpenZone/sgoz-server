from flask import Flask, request, jsonify, Response
import json
import hashlib
import time
import gzip
import io
import random

app = Flask(__name__)

# ─── BASE DE DATOS EN MEMORIA ─────────────────────────────────────────────────
users = {}        # userid -> {pw, email, nickname, kind, deviceId, created}
player_data = {}  # userid -> _PlayerData dict
user_data = {}    # userid -> {_Friends, _Progress, _GameSettings, etc}

# ─── HELPERS ──────────────────────────────────────────────────────────────────
def parse_param(req):
    if req.method == "GET":
        raw = req.args.get("param", "{}")
    else:
        raw = req.form.get("param", req.data.decode("utf-8") if req.data else "{}")
    try:
        return json.loads(raw)
    except:
        return {}

def gz(data: str):
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode='wb') as f:
        f.write(data.encode('utf-8'))
    return Response(buf.getvalue(), status=200, headers={
        "Content-Type": "text/plain;charset=utf-8",
        "Content-Encoding": "gzip",
        "Server": "Shadowgun: Deadzone/1.0"
    })

def ok(extra=None):
    d = {"result": "ok"}
    if extra:
        d.update(extra)
    return gz(json.dumps(d))

def err(msg="error"):
    return gz(json.dumps({"result": "error", "msg": msg}))

def default_player(userid, nickname="Player"):
    return {
        # Core identity
        "UserId": userid,
        "NickName": nickname,
        "AccountKind": "guest",
        "AppProvider": "google",
        # Progression
        "Level": 1,
        "Xp": 0,
        "Rank": 1,
        # Currency
        "Credits": 99999,
        "Gold": 9999,
        "IsPremium": True,
        # Items
        "EquippedItems": [],
        "OwnedItems": [],
        # Stats
        "Kills": 0,
        "Deaths": 0,
        "Wins": 0,
        "Losses": 0,
        "HeadShots": 0,
        "Assists": 0,
        # Progress
        "_Progress": {"level": 1, "xp": 0},
        # Settings
        "_GameSettings": {
            "soundVolume": 1.0,
            "musicVolume": 1.0,
            "controlScheme": 0
        },
        # Premium
        "_PremiumAccountsDesc": {
            "isPremium": True,
            "expiryTime": 9999999999
        },
        "Avatar": 0,
        "CustomRegion": "",
        "Roles": [],
        "desc": "",
        "code": ""
    }

def default_user_data():
    return {
        "_Friends": [],
        "_SwearWords": [],
        "Email": "",
        "IWantNews": False,
        "AccountKind": "guest"
    }

def get_or_create_player(userid):
    if userid not in player_data:
        player_data[userid] = default_player(userid)
    if userid not in user_data:
        user_data[userid] = default_user_data()
    return player_data[userid]

# ─── APP VERSION ──────────────────────────────────────────────────────────────
@app.route("/sgdz/getAppVersion", methods=["GET"])
def get_app_version():
    return ok({"version": "2.10.0", "needsUpdate": False, "obbValid": True})

# ─── FINGERPRINT (device identification) ─────────────────────────────────────
@app.route("/sgdz/fingerPrint", methods=["GET", "POST"])
@app.route("/sgdz/Fingerprint", methods=["GET", "POST"])
@app.route("/sgdz/FingerPrint", methods=["GET", "POST"])
def fingerprint():
    p = parse_param(request)
    deviceid = p.get("deviceId", p.get("deviceid", "unknown"))
    return ok({"deviceId": deviceid, "trusted": True})

# ─── USER EXISTS ──────────────────────────────────────────────────────────────
@app.route("/sgdz/userExists", methods=["GET"])
@app.route("/sgdz/_UserExist", methods=["GET"])
def user_exists():
    p = parse_param(request)
    userid = p.get("userid", "")
    pw = p.get("pw", "")
    if userid not in users:
        return gz("0")
    if pw and users[userid].get("pw", "") != pw:
        return gz("0")
    return gz("1")

# ─── CREATE USER ──────────────────────────────────────────────────────────────
@app.route("/sgdz/createUser", methods=["GET", "POST"])
@app.route("/sgdz/CreateUser", methods=["GET", "POST"])
def create_user():
    p = parse_param(request)
    userid   = p.get("userid", p.get("Username", p.get("username", "")))
    pw       = p.get("pw", p.get("passwordHash", ""))
    email    = p.get("email", p.get("Email", ""))
    nickname = p.get("NickName", p.get("nickname", userid))
    kind     = p.get("kind", p.get("AccountKind", "guest"))
    iwant    = p.get("iWantNews", p.get("IWantNews", False))

    if not userid:
        return err("invalidparams")
    if userid in users:
        return err("alreadyproc")

    users[userid] = {
        "pw": pw, "email": email, "nickname": nickname,
        "kind": kind, "iWantNews": iwant,
        "created": int(time.time())
    }
    player_data[userid] = default_player(userid, nickname)
    user_data[userid] = default_user_data()
    user_data[userid]["Email"] = email
    user_data[userid]["IWantNews"] = iwant
    user_data[userid]["AccountKind"] = kind

    return ok({"userid": userid, "NickName": nickname})

# ─── USER GET PRIMARY KEY (token) ─────────────────────────────────────────────
@app.route("/sgdz/userGetPrimaryKey", methods=["GET"])
def user_get_primary_key():
    p = parse_param(request)
    userid = p.get("userid", "")
    pw     = p.get("pw", "")

    # Auto-create guest accounts
    if userid not in users:
        if userid.startswith("guest"):
            users[userid] = {"pw": pw, "email": "", "nickname": userid,
                             "kind": "guest", "created": int(time.time())}
            player_data[userid] = default_player(userid, userid)
            user_data[userid] = default_user_data()
        else:
            return err("invalidusr")

    key = hashlib.md5(f"{userid}:sgdz_revival".encode()).hexdigest()
    return ok({"primaryKey": key, "userid": userid,
               "NickName": users[userid].get("nickname", userid)})

# ─── VALIDATE ACCOUNT ─────────────────────────────────────────────────────────
@app.route("/sgdz/validateAccount", methods=["GET", "POST"])
@app.route("/sgdz/_VaidateUserData", methods=["GET", "POST"])
def validate_account():
    p = parse_param(request)
    userid = p.get("userid", "")
    get_or_create_player(userid)
    return ok({"valid": True, "userid": userid,
               "NickName": users.get(userid, {}).get("nickname", userid)})

# ─── GET PRODUCT DATA ─────────────────────────────────────────────────────────
@app.route("/sgdz/getProductData", methods=["GET"])
def get_product_data():
    p = parse_param(request)
    param = p.get("param", "")

    if param == "_ShopItems":
        return ok({"param": "_ShopItems", "data": [
            {"id": "weapon_pistol",   "name": "Pistol",        "price": 0,    "currency": "Credits", "unlockLevel": 1},
            {"id": "weapon_rifle",    "name": "Assault Rifle", "price": 1000, "currency": "Credits", "unlockLevel": 2},
            {"id": "weapon_shotgun",  "name": "Shotgun",       "price": 1500, "currency": "Credits", "unlockLevel": 3},
            {"id": "weapon_sniper",   "name": "Sniper Rifle",  "price": 2000, "currency": "Credits", "unlockLevel": 5},
            {"id": "weapon_smg",      "name": "SMG",           "price": 1200, "currency": "Credits", "unlockLevel": 4},
            {"id": "weapon_rocket",   "name": "Rocket Launcher","price": 3000,"currency": "Credits", "unlockLevel": 8},
            {"id": "armor_light",     "name": "Light Armor",   "price": 500,  "currency": "Credits", "unlockLevel": 1},
            {"id": "armor_medium",    "name": "Medium Armor",  "price": 1000, "currency": "Credits", "unlockLevel": 3},
            {"id": "armor_heavy",     "name": "Heavy Armor",   "price": 2000, "currency": "Credits", "unlockLevel": 6},
            {"id": "grenade_frag",    "name": "Frag Grenade",  "price": 300,  "currency": "Credits", "unlockLevel": 2},
            {"id": "grenade_emp",     "name": "EMP Grenade",   "price": 500,  "currency": "Credits", "unlockLevel": 4},
            {"id": "premium_week",    "name": "Premium 1 Week","price": 50,   "currency": "Gold",    "unlockLevel": 1},
            {"id": "premium_month",   "name": "Premium 1 Month","price": 150, "currency": "Gold",    "unlockLevel": 1},
        ]})

    if param == "_GameSettings":
        return ok({"param": "_GameSettings", "data": {
            "maxPlayersPerRoom": 8,
            "matchDuration": 600,
            "respawnTime": 5,
            "friendlyFire": False
        }})

    if param == "_PremiumAccountsDesc":
        return ok({"param": "_PremiumAccountsDesc", "data": {
            "xpBonus": 1.5,
            "creditsBonus": 1.5,
            "description": "Premium gives 50% bonus XP and Credits"
        }})

    if param == "_DefaultPlayerData":
        return ok({"param": "_DefaultPlayerData", "data": default_player("default")})

    return ok({"param": param, "data": {}})

# ─── GET USR PER PRODUCT DATA (_PlayerData, etc) ──────────────────────────────
@app.route("/sgdz/getUsrPerProductData", methods=["GET"])
@app.route("/sgdz/setUsrPerProductData", methods=["GET", "POST"])
def get_usr_per_product_data():
    p = parse_param(request)
    userid = p.get("userid", "")
    param  = p.get("param", "")
    pd     = get_or_create_player(userid)

    if request.path.endswith("setUsrPerProductData"):
        # Save data sent by client
        new_data = p.get("data", {})
        if isinstance(new_data, dict):
            pd.update(new_data)
        return ok()

    if param == "_PlayerData":
        return ok({"param": "_PlayerData", "data": pd})
    if param == "_Progress":
        return ok({"param": "_Progress", "data": pd.get("_Progress", {})})
    if param == "_GameSettings":
        return ok({"param": "_GameSettings", "data": pd.get("_GameSettings", {})})
    if param == "_PremiumAccountsDesc":
        return ok({"param": "_PremiumAccountsDesc", "data": pd.get("_PremiumAccountsDesc", {})})

    return ok({"param": param, "data": pd.get(param, {})})

# ─── GET USR DATA (_Friends, etc) ─────────────────────────────────────────────
@app.route("/sgdz/getUsrData", methods=["GET"])
@app.route("/sgdz/setUsrData", methods=["GET", "POST"])
def get_usr_data():
    p = parse_param(request)
    userid = p.get("userid", "")
    param  = p.get("param", "")
    get_or_create_player(userid)
    ud = user_data.get(userid, default_user_data())

    if request.path.endswith("setUsrData"):
        new_data = p.get("data", p.get("value", None))
        if new_data is not None:
            ud[param] = new_data
        return ok()

    if param == "_Friends":
        return ok({"param": "_Friends", "data": ud.get("_Friends", [])})
    if param == "Email":
        return ok({"param": "Email", "data": ud.get("Email", "")})
    if param == "IWantNews":
        return ok({"param": "IWantNews", "data": ud.get("IWantNews", False)})
    if param == "AccountKind":
        return ok({"param": "AccountKind", "data": ud.get("AccountKind", "guest")})

    return ok({"param": param, "data": ud.get(param, "")})

# ─── GET PUBLIC USER DATA ──────────────────────────────────────────────────────
@app.route("/sgdz/getPublicUserData", methods=["GET"])
def get_public_user_data():
    p = parse_param(request)
    userid = p.get("userid", "")
    pd = get_or_create_player(userid)
    return ok({"data": {
        "UserId": userid,
        "NickName": pd.get("NickName", userid),
        "Level": pd.get("Level", 1),
        "Rank": pd.get("Rank", 1),
        "Kills": pd.get("Kills", 0),
        "IsPremium": pd.get("IsPremium", False),
        "Avatar": pd.get("Avatar", 0)
    }})

# ─── GET USER DATA LIST ───────────────────────────────────────────────────────
@app.route("/sgdz/getUserDataList", methods=["GET"])
@app.route("/sgdz/GetUserDataList", methods=["GET"])
def get_user_data_list():
    p = parse_param(request)
    userid = p.get("userid", "")
    pd = get_or_create_player(userid)
    return ok({"data": [pd]})

# ─── USER ADD PRODUCT DATA ────────────────────────────────────────────────────
@app.route("/sgdz/addUsrProduct", methods=["GET", "POST"])
@app.route("/sgdz/UserAddProductData", methods=["GET", "POST"])
def user_add_product_data():
    p = parse_param(request)
    userid = p.get("userid", "")
    get_or_create_player(userid)
    return ok()

# ─── BUY ITEM ─────────────────────────────────────────────────────────────────
@app.route("/sgdz/buyItem", methods=["GET", "POST"])
@app.route("/sgdz/BuyItem", methods=["GET", "POST"])
def buy_item():
    p = parse_param(request)
    userid  = p.get("userid", "")
    item_id = p.get("itemId", p.get("itemid", ""))
    pd = get_or_create_player(userid)

    if item_id and item_id not in pd["OwnedItems"]:
        pd["OwnedItems"].append(item_id)

    return ok({"userid": userid, "itemId": item_id, "playerData": pd})

# ─── EQUIP ITEM ───────────────────────────────────────────────────────────────
@app.route("/sgdz/equipItem", methods=["GET", "POST"])
@app.route("/sgdz/EquipItem", methods=["GET", "POST"])
def equip_item():
    p = parse_param(request)
    userid  = p.get("userid", "")
    item_id = p.get("itemId", p.get("itemid", ""))
    pd = get_or_create_player(userid)

    if item_id and item_id not in pd["EquippedItems"]:
        pd["EquippedItems"].append(item_id)

    return ok({"playerData": pd})

# ─── UNEQUIP ITEM ─────────────────────────────────────────────────────────────
@app.route("/sgdz/unEquipItem", methods=["GET", "POST"])
@app.route("/sgdz/UnEquipItem", methods=["GET", "POST"])
def unequip_item():
    p = parse_param(request)
    userid  = p.get("userid", "")
    item_id = p.get("itemId", p.get("itemid", ""))
    pd = get_or_create_player(userid)

    if item_id in pd["EquippedItems"]:
        pd["EquippedItems"].remove(item_id)

    return ok({"playerData": pd})

# ─── MODIFY ITEM ──────────────────────────────────────────────────────────────
@app.route("/sgdz/modifyItem", methods=["GET", "POST"])
def modify_item():
    p = parse_param(request)
    userid = p.get("userid", "")
    pd = get_or_create_player(userid)
    return ok({"playerData": pd})

# ─── BUY BUILTIN ITEM ─────────────────────────────────────────────────────────
@app.route("/sgdz/buyBuiltInItem", methods=["GET", "POST"])
def buy_builtin_item():
    p = parse_param(request)
    userid  = p.get("userid", "")
    item_id = p.get("itemId", "")
    pd = get_or_create_player(userid)
    if item_id and item_id not in pd["OwnedItems"]:
        pd["OwnedItems"].append(item_id)
    return ok({"playerData": pd})

# ─── BUY PREMIUM ACCOUNT ──────────────────────────────────────────────────────
@app.route("/sgdz/buyPremiumAccount", methods=["GET", "POST"])
@app.route("/sgdz/BuyPremiumAccount", methods=["GET", "POST"])
def buy_premium():
    p = parse_param(request)
    userid = p.get("userid", "")
    pd = get_or_create_player(userid)
    pd["IsPremium"] = True
    pd["_PremiumAccountsDesc"]["isPremium"] = True
    return ok({"isPremium": True, "playerData": pd})

# ─── GET AVAILABLE PREMIUM ACCOUNTS ──────────────────────────────────────────
@app.route("/sgdz/getAvailablePremiumAccounts", methods=["GET"])
def get_available_premium():
    return ok({"accounts": [
        {"id": "premium_week",  "name": "1 Week",  "price": 50,  "currency": "Gold"},
        {"id": "premium_month", "name": "1 Month", "price": 150, "currency": "Gold"},
    ]})

# ─── BATCH COMMAND ────────────────────────────────────────────────────────────
@app.route("/sgdz/batchCommand", methods=["GET", "POST"])
@app.route("/sgdz/BatchCommand", methods=["GET", "POST"])
def batch_command():
    p = parse_param(request)
    userid = p.get("userid", "")
    get_or_create_player(userid)
    return ok({"userid": userid, "batchResult": []})

# ─── GET CLOUD DATE TIME ──────────────────────────────────────────────────────
@app.route("/sgdz/getCloudDateTime", methods=["GET"])
@app.route("/sgdz/GetCloudDateTime", methods=["GET"])
def get_cloud_datetime():
    return ok({"datetime": int(time.time()),
               "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})

# ─── GET USER REGION INFO ─────────────────────────────────────────────────────
@app.route("/sgdz/getUserRegionInfo", methods=["GET"])
@app.route("/sgdz/GetUserRegionInfo", methods=["GET"])
def get_user_region_info():
    p = parse_param(request)
    userid = p.get("userid", "")
    return ok({"userid": userid, "region": "us-east", "customRegion": "",
               "serverIP": "127.0.0.1", "serverPort": 7777})

# ─── GET CUSTOM REGION INFO ───────────────────────────────────────────────────
@app.route("/sgdz/getCustomRegionInfo", methods=["GET"])
@app.route("/sgdz/GetCustomRegionInfo", methods=["GET"])
def get_custom_region_info():
    return ok({"regions": [
        {"id": "us-east", "name": "US East", "ip": "127.0.0.1", "port": 7777},
        {"id": "eu-west", "name": "EU West", "ip": "127.0.0.1", "port": 7778},
    ]})

# ─── GET GAME INFO SETTINGS ───────────────────────────────────────────────────
@app.route("/sgdz/getGameInfoSettings", methods=["GET"])
@app.route("/sgdz/GetGameInfoSettings", methods=["GET"])
def get_game_info_settings():
    return ok({"settings": {
        "maxPlayers": 8,
        "matchTime": 600,
        "respawnTime": 5,
        "killsToWin": 30,
        "friendlyFire": False,
        "boostersEnabled": True
    }})

# ─── SET DEVICE ID ────────────────────────────────────────────────────────────
@app.route("/sgdz/setDeviceId", methods=["GET", "POST"])
@app.route("/sgdz/SetDeviceId", methods=["GET", "POST"])
def set_device_id():
    p = parse_param(request)
    userid   = p.get("userid", "")
    deviceid = p.get("deviceId", "")
    if userid in users:
        users[userid]["deviceId"] = deviceid
    return ok({"deviceId": deviceid})

# ─── SET FACEBOOK ID ──────────────────────────────────────────────────────────
@app.route("/sgdz/setFacebookId", methods=["GET", "POST"])
@app.route("/sgdz/SetFacebookId", methods=["GET", "POST"])
def set_facebook_id():
    p = parse_param(request)
    userid = p.get("userid", "")
    fbid   = p.get("facebookId", "")
    if userid in users:
        users[userid]["facebookId"] = fbid
    return ok({"facebookId": fbid})

# ─── GET USER TRANSACTIONS ────────────────────────────────────────────────────
@app.route("/sgdz/getUserTransactions", methods=["GET"])
def get_user_transactions():
    return ok({"transactions": []})

# ─── TRANS PROCESSED ─────────────────────────────────────────────────────────
@app.route("/sgdz/transProcessed", methods=["GET", "POST"])
def trans_processed():
    return ok()

# ─── IAP ──────────────────────────────────────────────────────────────────────
@app.route("/sgdz/iapRequestPurchaseV2", methods=["GET", "POST"])
def iap_request():
    return ok({"purchaseToken": "revival_free_token"})

@app.route("/sgdz/iapProcessPurchaseV2", methods=["GET", "POST"])
def iap_process():
    p = parse_param(request)
    userid = p.get("userid", "")
    pd = get_or_create_player(userid)
    pd["Gold"] += 9999
    return ok({"playerData": pd})

# ─── LEADERBOARDS ─────────────────────────────────────────────────────────────
@app.route("/sgdz/createLeaderboard", methods=["GET", "POST"])
def create_leaderboard():
    return ok({"leaderboardId": "global"})

@app.route("/sgdz/leaderboardSetScores", methods=["GET", "POST"])
def leaderboard_set_scores():
    return ok()

@app.route("/sgdz/getLeaderboardRanks", methods=["GET"])
def get_leaderboard_ranks():
    p = parse_param(request)
    userid = p.get("userid", "")
    pd = get_or_create_player(userid)
    return ok({"rank": 1, "score": pd.get("Kills", 0), "total": len(users)})

@app.route("/sgdz/leaderboardQuery", methods=["GET"])
@app.route("/sgdz/getLboardUsersCount", methods=["GET"])
def leaderboard_query():
    return ok({"count": len(users), "leaderboard": [
        {"rank": i+1, "userid": uid,
         "NickName": users.get(uid, {}).get("nickname", uid),
         "score": player_data.get(uid, {}).get("Kills", 0)}
        for i, uid in enumerate(list(users.keys())[:10])
    ]})

@app.route("/sgdz/queryUsersByField", methods=["GET"])
def query_users_by_field():
    return ok({"users": []})

# ─── FRIENDS ──────────────────────────────────────────────────────────────────
@app.route("/sgdz/reqAddFriend", methods=["GET", "POST"])
def req_add_friend():
    p = parse_param(request)
    userid    = p.get("userid", "")
    friendid  = p.get("friendId", "")
    ud = user_data.get(userid, default_user_data())
    if friendid and friendid not in ud["_Friends"]:
        ud["_Friends"].append(friendid)
    return ok()

@app.route("/sgdz/reqDelFriend", methods=["GET", "POST"])
def req_del_friend():
    p = parse_param(request)
    userid   = p.get("userid", "")
    friendid = p.get("friendId", "")
    ud = user_data.get(userid, default_user_data())
    if friendid in ud["_Friends"]:
        ud["_Friends"].remove(friendid)
    return ok()

@app.route("/sgdz/getFriendsPlayerData", methods=["GET"])
def get_friends_player_data():
    p = parse_param(request)
    userid = p.get("userid", "")
    ud = user_data.get(userid, default_user_data())
    friends = []
    for fid in ud.get("_Friends", []):
        if fid in player_data:
            friends.append(player_data[fid])
    return ok({"friends": friends})

@app.route("/sgdz/getLinkedUsers", methods=["GET"])
@app.route("/sgdz/getUserLinkedWithID", methods=["GET"])
def get_linked_users():
    return ok({"users": []})

@app.route("/sgdz/linkIDWithUser", methods=["GET", "POST"])
def link_id_with_user():
    return ok()

# ─── MESSAGES / INBOX ─────────────────────────────────────────────────────────
@app.route("/sgdz/fetchInboxMsgs", methods=["GET"])
@app.route("/sgdz/GetMessagesFromInbox", methods=["GET"])
def fetch_inbox_msgs():
    return ok({"messages": [{
        "id": 1,
        "msgType": "global",
        "m_Mailbox": 0,
        "m_Sender": "Shadowgun: Deadzone",
        "m_Message": "Welcome to the revival server! Enjoy playing.",
        "m_RAWMessage": "",
        "m_SendTime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "m_IsRead": False
    }]})

@app.route("/sgdz/inboxAddMsg", methods=["GET", "POST"])
def inbox_add_msg():
    return ok()

@app.route("/sgdz/inboxRemoveMsgs", methods=["GET", "POST"])
@app.route("/sgdz/RemoveMessagesFrom", methods=["GET", "POST"])
def inbox_remove_msgs():
    return ok()

# ─── PUSH NOTIFICATIONS ───────────────────────────────────────────────────────
@app.route("/sgdz/registerForPush", methods=["GET", "POST"])
@app.route("/sgdz/RegisterForPushNotifications", methods=["GET", "POST"])
@app.route("/sgdz/createPushNotification", methods=["GET", "POST"])
def push_notifications():
    return ok()

# ─── SLOT MACHINE ─────────────────────────────────────────────────────────────
@app.route("/sgdz/getSMJackpot", methods=["GET"])
def get_sm_jackpot():
    return ok({"jackpot": 5000, "nextSpin": 0})

@app.route("/sgdz/slotmachineSpin", methods=["GET", "POST"])
@app.route("/sgdz/SlotMachineSpin", methods=["GET", "POST"])
def slot_machine_spin():
    p = parse_param(request)
    userid = p.get("userid", "")
    pd = get_or_create_player(userid)
    rewards = [
        {"type": "Credits", "amount": 100},
        {"type": "Credits", "amount": 500},
        {"type": "Credits", "amount": 1000},
        {"type": "Gold",    "amount": 10},
        {"type": "Gold",    "amount": 50},
        {"type": "XP",      "amount": 200},
    ]
    reward = random.choice(rewards)
    if reward["type"] == "Credits":
        pd["Credits"] += reward["amount"]
    elif reward["type"] == "Gold":
        pd["Gold"] += reward["amount"]
    elif reward["type"] == "XP":
        pd["Xp"] += reward["amount"]
    return ok({"reward": reward, "playerData": pd})

# ─── DAILY REWARDS ────────────────────────────────────────────────────────────
@app.route("/sgdz/getDailyRewards", methods=["GET"])
def get_daily_rewards():
    return ok({"rewards": [
        {"day": 1, "type": "Credits", "amount": 500},
        {"day": 2, "type": "Credits", "amount": 1000},
        {"day": 3, "type": "Gold",    "amount": 10},
        {"day": 4, "type": "Credits", "amount": 1500},
        {"day": 5, "type": "Gold",    "amount": 25},
        {"day": 6, "type": "Credits", "amount": 2000},
        {"day": 7, "type": "Gold",    "amount": 50},
    ], "currentDay": 1, "canClaim": True})

# ─── AD TRANSACTION ───────────────────────────────────────────────────────────
@app.route("/sgdz/adTransaction", methods=["GET", "POST"])
@app.route("/sgdz/GetVideoTickets", methods=["GET", "POST"])
@app.route("/sgdz/getAdData", methods=["GET", "POST"])
def ad_transaction():
    return ok({"tickets": 5, "reward": {"type": "Gold", "amount": 5}})

# ─── RESEARCH ─────────────────────────────────────────────────────────────────
@app.route("/sgdz/ResearchRefundAction", methods=["GET", "POST"])
@app.route("/sgdz/researchRefund", methods=["GET", "POST"])
def research_refund():
    return ok()

# ─── ADMIN ────────────────────────────────────────────────────────────────────
@app.route("/sgdz/adminGetUserDataOnUserList", methods=["GET", "POST"])
@app.route("/sgdz/adminRoleGet", methods=["GET"])
def admin_endpoints():
    return ok({"data": []})

@app.route("/sgdz/addDeviceBan", methods=["GET", "POST"])
@app.route("/sgdz/unbanDevice", methods=["GET", "POST"])
@app.route("/sgdz/isDeviceBanned", methods=["GET"])
def ban_endpoints():
    return ok({"banned": False})

@app.route("/sgdz/deleteLeaderboardContent", methods=["GET", "POST"])
def delete_leaderboard():
    return ok()

# ─── SET/ADD CONFIG ───────────────────────────────────────────────────────────
@app.route("/sgdz/getConfig", methods=["GET"])
@app.route("/sgdz/setConfig", methods=["GET", "POST"])
@app.route("/sgdz/addConfig", methods=["GET", "POST"])
@app.route("/sgdz/setDataSection", methods=["GET", "POST"])
@app.route("/sgdz/updateDataSection", methods=["GET", "POST"])
@app.route("/sgdz/getEntityField", methods=["GET"])
def config_endpoints():
    return ok({"data": {}})

# ─── CLAN API ─────────────────────────────────────────────────────────────────
@app.route("/sgdz/clanapi", methods=["GET", "POST"])
def clan_api():
    cmd = request.args.get("cmd", "")
    if cmd == "clanbyuser":
        return ok({"clan": None})
    return ok()

# ─── CLOUD API (leaderboards) ─────────────────────────────────────────────────
@app.route("/sgdz/cloudapi", methods=["GET", "POST"])
def cloud_api():
    cmd      = request.args.get("cmd", "")
    username = request.args.get("username", "")

    if cmd == "getrevisionlog":
        return ok({"log": [{"version": "2.10.0",
                             "notes": "Shadowgun: OpenZone revival server online!"}]})
    if cmd in ("getleaderboard", "getleaderboardself"):
        return ok({"rank": 1, "username": username,
                   "leaderboard": [{"rank": 1, "username": username or "Player1",
                                    "kills": 0, "xp": 0}]})
    if cmd == "getLboardUsersCount":
        return ok({"count": len(users)})
    return ok()

# ─── RESET PASSWORD ───────────────────────────────────────────────────────────
@app.route("/sgdz/reqResetPw", methods=["GET", "POST"])
@app.route("/sgdz/reqResetPwEmail", methods=["GET", "POST"])
@app.route("/sgdz/RequestResetPassword", methods=["GET", "POST"])
def reset_password():
    return ok({"msg": "Password reset not required on revival server"})

# ─── CATCH ALL ────────────────────────────────────────────────────────────────
@app.route("/sgdz/<path:endpoint>", methods=["GET", "POST"])
def catch_all(endpoint):
    app.logger.info(f"[CATCH-ALL] {request.method} /sgdz/{endpoint} | args={dict(request.args)}")
    return ok()

# ─── HEALTH CHECK ─────────────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "server": "Shadowgun: Deadzone",
        "project": "Shadowgun: OpenZone",
        "status": "online",
        "version": "2.10.0",
        "users_online": len(users),
        "by": "vurkz-dev / Aulo Oa Company"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
