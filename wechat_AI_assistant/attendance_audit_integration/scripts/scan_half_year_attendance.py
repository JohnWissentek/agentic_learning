import sys
import json
import urllib.request
import time
from datetime import datetime, date, timedelta
from math import radians, cos, sin, asin, sqrt

# WeCom API details matching stage_one configuration
CORPID = "ww9238966755b26e48"
SECRET = "4v0O2zfAJmy1NvP7JCa-m6gUVgn1anccYHwbNWi2jRo"

def get_access_token():
    url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={CORPID}&corpsecret={SECRET}"
    req = urllib.request.urlopen(url)
    res = json.loads(req.read().decode('utf-8'))
    if res.get("errcode") == 0:
        return res.get("access_token")
    else:
        raise Exception(f"Failed to fetch AccessToken: {res}")

def calculate_haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in kilometers between two lat/lon coordinates."""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371.0  # Earth radius in kilometers
    return c * r

def fetch_checkin_logs(access_token, user_ids, start_time, end_time):
    """Fetch checkin logs from WeCom. Max 100 users and 30-day window per API limit."""
    url = f"https://qyapi.weixin.qq.com/cgi-bin/checkin/getcheckindata?access_token={access_token}"
    payload = {
        "opencheckindatatype": 3,  # All checkins (standard + outdoor)
        "starttime": int(start_time),
        "endtime": int(end_time),
        "useridlist": user_ids
    }
    req_data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=req_data, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            if res_data.get("errcode") == 0:
                return res_data.get("checkindata", [])
            else:
                print(f"WeCom API Error: {res_data.get('errmsg')} (code: {res_data.get('errcode')})")
                return []
    except Exception as e:
        print(f"HTTP request error: {e}")
        return []

def main():
    print("==========================================================")
    print("  WeCom Half-Year Attendance Integrity Audit Script (180 Days)")
    print("==========================================================")
    print("This script is configured to run on your whitelisted ECS server.")
    print("It pulls raw checkin records for all employees over the past 180 days")
    print("and scans for client exceptions or spatial speed inconsistencies.\n")

    # Load Roster JSON (no xlsx)
    from attendance_audit_integration.roster import load_employee_roster

    roster_rows = load_employee_roster()
    user_ids = []
    name_by_userid = {}
    for row in roster_rows:
        name = row["name"]
        uid = row.get("wecom_userid") or name
        user_ids.append(uid)
        name_by_userid[uid] = name

    print(f"Loaded {len(user_ids)} employees from JSON roster.")

    try:
        token = get_access_token()
        print("WeCom API connection initialized. Fetching records...")
    except Exception as e:
        print(f"\n[IP BLOCK/CONNECTION ERROR] {e}")
        print("Note: This script must be executed from your whitelisted ECS server IP address.")
        sys.exit(1)

    # WeCom limits queries to 30 days. We chunk the 180 days into 6 periods.
    now = datetime.now()
    periods = []
    for i in range(6):
        end = now - timedelta(days=i*30)
        start = now - timedelta(days=(i+1)*30)
        periods.append((start.timestamp(), end.timestamp()))

    all_raw_logs = []
    # Query WeCom for all employees in chunks
    for idx, (start_ts, end_ts) in enumerate(periods, 1):
        start_date = datetime.fromtimestamp(start_ts).strftime("%Y-%m-%d")
        end_date = datetime.fromtimestamp(end_ts).strftime("%Y-%m-%d")
        print(f" - Period {idx}/6: Pulling logs from {start_date} to {end_date}...")
        
        # WeCom limit is 100 users per request, our team has ~20 users, so we can send all in 1 request
        logs = fetch_checkin_logs(token, user_ids, start_ts, end_ts)
        all_raw_logs.extend(logs)
        time.sleep(0.5)  # Respect rate limit

    print(f"\nPulled {len(all_raw_logs)} raw attendance records from WeCom Cloud.")
    print("Starting integrity checks...")
    
    anomalies = []
    
    # Sort logs by user and time for chronological speed checks
    logs_by_user = {}
    for log in all_raw_logs:
        uid = log.get("userid")
        if uid not in logs_by_user:
            logs_by_user[uid] = []
        logs_by_user[uid].append(log)

    for uid, user_logs in logs_by_user.items():
        # Sort chronologically
        user_logs.sort(key=lambda x: x.get("checkin_time", 0))
        emp_name = name_by_userid.get(uid, uid)
        
        # 1. WeCom Native Client exceptions (root, simulator, mock location apps)
        for log in user_logs:
            exception_type = log.get("exception_type", "")
            if exception_type in ["root", "simulator", "virtual_location"]:
                anomalies.append({
                    "employee": emp_name,
                    "date": datetime.fromtimestamp(log.get("checkin_time")).strftime("%Y-%m-%d %H:%M:%S"),
                    "type": "企微内置安全警报",
                    "detail": f"设备处于非安全状态 (状态码: {exception_type})，可能使用了模拟器或虚拟定位软件。",
                    "location": log.get("location_title", "未知"),
                    "ip": log.get("ip_address", "未知")
                })

        # 2. Haversine Spatial Teleportation Checks (between consecutive punches on same day)
        for i in range(len(user_logs) - 1):
            log1 = user_logs[i]
            log2 = user_logs[i+1]
            
            t1 = log1.get("checkin_time", 0)
            t2 = log2.get("checkin_time", 0)
            
            d1 = datetime.fromtimestamp(t1).date()
            d2 = datetime.fromtimestamp(t2).date()
            
            # Must be same day to test teleportation speed
            if d1 == d2:
                # Lat/lng must exist in WeCom format
                # Note: WeCom API location format represents lat/lng in micro-degrees (multiplied by 1,000,000)
                lat1_raw = log1.get("lat")
                lng1_raw = log1.get("lng")
                lat2_raw = log2.get("lat")
                lng2_raw = log2.get("lng")
                
                if lat1_raw and lng1_raw and lat2_raw and lng2_raw:
                    lat1 = lat1_raw / 1000000.0
                    lon1 = lng1_raw / 1000000.0
                    lat2 = lat2_raw / 1000000.0
                    lon2 = lng2_raw / 1000000.0
                    
                    dist = calculate_haversine_distance(lat1, lon1, lat2, lon2)
                    time_diff_hours = (t2 - t1) / 3600.0
                    
                    if time_diff_hours > 0.005:  # Ignore double-punches within 18 seconds
                        speed = dist / time_diff_hours
                        # Speed limit exceeding 350 km/h implies physical impossibility
                        if speed > 350.0:
                            anomalies.append({
                                "employee": emp_name,
                                "date": d1.strftime("%Y-%m-%d"),
                                "type": "空间瞬移异常",
                                "detail": f"打卡间距 {dist:.1f}公里，用时 {time_diff_hours*60:.1f}分钟，换算时速达 {speed:.1f}公里/小时，超出物理学极限。",
                                "location": f"打卡1: {log1.get('location_title')} -> 打卡2: {log2.get('location_title')}",
                                "ip": f"IP1: {log1.get('ip_address')} -> IP2: {log2.get('ip_address')}"
                            })

    # Summary Report
    print("\n" + "="*50)
    print("              HALF-YEAR AUDIT REPORT SUMMARY            ")
    print("="*50)
    print(f"Total punched scanned: {len(all_raw_logs)}")
    print(f"Total anomalies flagged: {len(anomalies)}")
    print("-"*50)
    
    if not anomalies:
        print("Congratulations! No telemetry anomalies or virtual location indicators found in the past 6 months.")
    else:
        for idx, a in enumerate(anomalies, 1):
            print(f"[{idx}] 员工: {a['employee']} | 日期: {a['date']}")
            print(f"    类别: {a['type']}")
            print(f"    详情: {a['detail']}")
            print(f"    地点: {a['location']}")
            print(f"    网络: {a['ip']}")
            print("-" * 50)

if __name__ == "__main__":
    main()
