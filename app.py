from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
import pycountry
from datetime import datetime
import json
import re

app = FastAPI(title="TikTok Info API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_created_time(user_id: str) -> str:
    try:
        binary = "{0:b}".format(int(user_id))
        bits = binary[:31]
        timestamp = int(bits, 2)
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return ""

def get_country_info(country_code: str):
    if not country_code:
        return "", ""
    try:
        c = pycountry.countries.get(alpha_2=country_code.upper())
        if c:
            return getattr(c, 'name', ''), getattr(c, 'flag', '')
    except Exception:
        pass
    return "", ""

@app.get("/")
def home():
    return {
        "status": "online",
        "message": "TikTok API is working! Use /api/tiktok?username=YOUR_USERNAME"
    }

@app.get("/api/tiktok")
def get_tiktok_info(username: str):
    username = username.replace("@", "").strip()
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.tiktok.com/",
    }

    url = f"https://www.tiktok.com/@{username}"

    try:
        res = requests.get(url, headers=headers, timeout=12)
        if res.status_code != 200:
            raise HTTPException(status_code=404, detail="User not found or TikTok blocked request.")

        html = res.text
        
        # Robust Regex Search for JSON data inside HTML script tags
        json_data = None
        
        # Try finding SIGI_STATE or __UNIVERSAL_DATA_FOR_REHYDRATION__ safely using regex
        patterns = [
            r'<script id="SIGI_STATE" type="application/json">(.*?)</script>',
            r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">(.*?)</script>',
            r'window\[\'SIGI_STATE\'\]\s*=\s*({.*?});'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    json_data = json.loads(match.group(1))
                    break
                except:
                    continue
        
        # Fallback to general substring parsing if regex fails
        if not json_data:
            if '__UNIVERSAL_DATA_FOR_REHYDRATION__' in html:
                try:
                    parts = html.split('__UNIVERSAL_DATA_FOR_REHYDRATION__">')
                    if len(parts) > 1:
                        subparts = parts[1].split('</script>')
                        json_data = json.loads(subparts[0])
                except:
                    pass

        if not json_data:
            raise HTTPException(status_code=404, detail="TikTok layout changed or user doesn't exist.")

        # Navigate nested dictionaries safely
        user_info = {}
        stats_info = {}
        
        try:
            if "__DEFAULT_SCOPE__" in json_data:
                user_detail = json_data["__DEFAULT_SCOPE__"].get("webapp.user-detail", {})
                userInfo = user_detail.get("userInfo", {})
                user_info = userInfo.get("user", {})
                stats_info = userInfo.get("stats", {})
            elif "UserModule" in json_data:
                users = json_data.get("UserModule", {}).get("users", {})
                if users:
                    uid = list(users.keys())[0]
                    user_info = users[uid]
                stats = json_data.get("UserModule", {}).get("stats", {})
                if stats:
                    uid = list(stats.keys())[0]
                    stats_info = stats[uid]
        except:
            pass

        if not user_info:
            raise HTTPException(status_code=404, detail="Could not extract user details from JSON.")

        user_id = str(user_info.get("id", ""))
        country_code = user_info.get("region", "")
        country_name, country_flag = get_country_info(country_code)
        created_at = get_created_time(user_id)

        return {
            "success": True,
            "data": {
                "username": user_info.get("uniqueId", username),
                "nickname": user_info.get("nickname", ""),
                "id": user_id,
                "secid": user_info.get("secUid", ""),
                "bio": user_info.get("signature", ""),
                "followers": stats_info.get("followerCount", 0),
                "following": stats_info.get("followingCount", 0),
                "likes": stats_info.get("heartCount", 0),
                "video_count": stats_info.get("videoCount", 0),
                "is_private": user_info.get("privateAccount", False),
                "is_verified": user_info.get("verified", False),
                "avatar": user_info.get("avatarLarger", ""),
                "country_code": country_code,
                "country_name": country_name,
                "country_flag": country_flag,
                "created_at": created_at
            }
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
