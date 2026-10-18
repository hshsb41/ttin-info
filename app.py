from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
import pycountry
from datetime import datetime
import json

app = FastAPI(title="TikTok Info API")

# Enable CORS for All Games, Websites, and Bots
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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
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
        
        json_str = None
        if '__UNIVERSAL_DATA_FOR_REHYDRATION__' in html:
            json_str = html.split('__UNIVERSAL_DATA_FOR_REHYDRATION__">')[1].split('</script>')[0]
        elif 'SIGI_STATE' in html:
            json_str = html.split('window[\'SIGI_STATE\']=')[1].split(';window[')[0]

        if not json_str:
            raise HTTPException(status_code=404, detail="Unable to parse user data from TikTok.")

        data_json = json.loads(json_str)

        user_detail = None
        if "__DEFAULT_SCOPE__" in data_json:
            user_detail = data_json["__DEFAULT_SCOPE__"].get("webapp.user-detail", {})
        
        user_info = user_detail.get("userInfo", {}).get("user", {})
        stats_info = user_detail.get("userInfo", {}).get("stats", {})

        if not user_info:
            raise HTTPException(status_code=404, detail="TikTok username not found.")

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
