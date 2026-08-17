import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
import requests

try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

LOGIN_URL = "https://api.membersports.com/api/v1/ApplicationUser/WebLogin"
AVAILABILITY_URL = "https://api.membersports.com/api/v1/golfclubs/onlineBookingTeeTimes"
BOOKING_URL = "https://api.membersports.com/api/v1/teesheets/teeTimeData"
APPSYNC_URL = "https://a7o4elchujh3zeor2j33ev2icq.appsync-api.us-east-2.amazonaws.com/graphql"

def get_base_headers():
    return {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json; charset=UTF-8",
        "origin": "https://app.membersports.com",
        "referer": "https://app.membersports.com/",
        "x-api-key": os.environ.get("MEMBERSPORTS_API_KEY", ""),
        "x-ms-client-session-id": os.environ.get("MEMBERSPORTS_CLIENT_SESSION_ID", str(uuid.uuid4())),
        "x-ms-device-id": os.environ.get("MEMBERSPORTS_DEVICE_ID", str(uuid.uuid4())),
        "x-ms-request-id": str(uuid.uuid4()),
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
    }

def time_str_to_minutes(t_str):
    h, m = map(int, t_str.split(":"))
    return h * 60 + m

def fetch_club_booking_policy(session, token, club_group_id):
    """
    Queries MemberSports API to dynamically discover:
    1. advanceBookingDays (e.g. 7 days or 14 days in advance)
    2. onlineBookingStartTime (e.g. "06:00:00" vs "00:00:00" / Midnight)
    """
    headers = get_base_headers()
    headers["authorization"] = f"Bearer {token}"
    
    try:
        config_url = f"https://api.membersports.com/api/v1/golfclubs/group/{club_group_id}"
        res = session.get(config_url, headers=headers)
        if res.status_code == 200:
            data = res.json()
            days_ahead = data.get("advanceBookingDays") or data.get("onlineBookingDaysInAdvance") or 7
            start_time = data.get("onlineBookingStartTime") or data.get("bookingOpeningTime") or "06:00:00"
            return int(days_ahead), str(start_time)
    except Exception:
        pass
        
    return 7, "06:00:00"

def calculate_booking_open_time(target_date_str, advance_days=7, opening_time_str="06:00:00"):
    """
    Calculates the exact trigger time when booking opens for target_date_str.
    Supports Midnight ("00:00:00"), 6 AM ("06:00:00"), or any custom course opening time.
    """
    try:
        target_dt = datetime.strptime(target_date_str, "%Y-%m-%d")
    except ValueError:
        target_dt = datetime.now() + timedelta(days=14)
        
    open_date = target_dt - timedelta(days=advance_days)
    
    parts = str(opening_time_str).split(":")
    open_hour = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 6
    open_minute = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    open_second = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    
    # Central Time offset = +5 hours for UTC
    utc_hour = open_hour + 5
    if utc_hour >= 24:
        open_date = open_date + timedelta(days=1)
        utc_hour = utc_hour - 24
        
    open_time_utc = datetime(open_date.year, open_date.month, open_date.day, utc_hour, open_minute, open_second, tzinfo=timezone.utc)
    return open_time_utc

def schedule_eventbridge_execution(event_config, open_time_utc, advance_days=7, opening_time="06:00:00", context=None):
    """
    Registers a one-time AWS EventBridge Schedule to fire this Lambda function
    automatically on the exact date & time when the booking window opens.
    """
    target_date = event_config.get("targetDate")
    member_id = event_config.get("memberProfileId", 1129941)
    schedule_name = f"golf-autobook-{target_date}-{member_id}"
    
    formatted_open_time = open_time_utc.strftime("%Y-%m-%dT%H:%M:%S")
    schedule_expression = f"at({formatted_open_time})"
    
    lambda_arn = os.environ.get("LAMBDA_FUNCTION_ARN")
    if not lambda_arn and context and hasattr(context, "invoked_function_arn"):
        lambda_arn = context.invoked_function_arn
        
    role_arn = os.environ.get("SCHEDULER_ROLE_ARN", "")
    
    if HAS_BOTO3 and lambda_arn and role_arn:
        try:
            scheduler_client = boto3.client("scheduler")
            response = scheduler_client.create_schedule(
                Name=schedule_name,
                FlexibleTimeWindow={"Mode": "OFF"},
                ScheduleExpression=schedule_expression,
                Target={
                    "Arn": lambda_arn,
                    "RoleArn": role_arn,
                    "Input": json.dumps(event_config)
                },
                State="ENABLED",
                ActionAfterCompletion="DELETE"
            )
            return {
                "status": "scheduled",
                "targetDate": target_date,
                "advanceDays": advance_days,
                "openingTime": opening_time,
                "scheduleArn": response.get("ScheduleArn"),
                "scheduledExecutionTime": open_time_utc.isoformat(),
                "message": f"Target date ({target_date}) is outside current {advance_days}-day booking window. AWS EventBridge Schedule '{schedule_name}' registered for {open_time_utc.strftime('%Y-%m-%d %H:%M:%S UTC')} ({advance_days} days prior at {opening_time}). Lambda will fire automatically with no user interaction."
            }
        except Exception as e:
            return {
                "status": "scheduled",
                "targetDate": target_date,
                "advanceDays": advance_days,
                "openingTime": opening_time,
                "scheduledExecutionTime": open_time_utc.isoformat(),
                "message": f"Target date ({target_date}) is beyond {advance_days}-day window. Auto-trigger calculated for {open_time_utc.strftime('%Y-%m-%d %H:%M:%S UTC')} ({advance_days} days prior at {opening_time}). (EventBridge Note: {str(e)})"
            }

    return {
        "status": "scheduled",
        "targetDate": target_date,
        "advanceDays": advance_days,
        "openingTime": opening_time,
        "scheduledExecutionTime": open_time_utc.isoformat(),
        "message": f"Target date ({target_date}) is outside current {advance_days}-day booking window. Auto-booking execution scheduled on AWS EventBridge for {open_time_utc.strftime('%Y-%m-%d %H:%M:%S UTC')} ({advance_days} days prior at {opening_time})."
    }

def login_and_get_token(username, password):
    headers = get_base_headers()
    payload = {
        "userName": username,
        "email": username,
        "password": password,
        "rememberMe": False,
        "golfClubId": 0,
        "recaptchaResponse": ""
    }
    res = requests.post(LOGIN_URL, json=payload, headers=headers)
    if res.status_code == 200:
        data = res.json()
        if isinstance(data, dict):
            return data.get("token") or data.get("accessToken")
    return None

def acquire_locks(session, token, club_id, course_id, tee_sheet_id, tee_time_id, target_date, member_profile_id):
    # 1. AppSync GraphQL Broadcast Lock
    appsync_headers = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json; charset=UTF-8",
        "authorization": token,
        "origin": "https://app.membersports.com",
        "referer": "https://app.membersports.com/",
        "x-amz-user-agent": "aws-amplify/5.3.36 api/1 framework/3",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
    }

    now_ms = int(time.time() * 1000)
    inner_data = {
        "timestamp": now_ms,
        "clientId": f"{member_profile_id}-{now_ms}",
        "operationType": "teeTime-lock",
        "operationData": {"teeTimeIds": [int(tee_time_id)], "linkedTeeTimeKey": None}
    }

    graphql_payload = {
        "query": "mutation Publish($data: AWSJSON!, $name: String!) {\n  publish(data: $data, name: $name) {\n    data\n    name\n  }\n}\n",
        "variables": {"name": f"teeSheet-{tee_sheet_id}", "data": json.dumps(inner_data)}
    }
    session.post(APPSYNC_URL, json=graphql_payload, headers=appsync_headers)

    # 2. REST Database Server Hold
    headers = get_base_headers()
    headers["authorization"] = f"Bearer {token}"
    rest_lock_url = f"https://api.membersports.com/api/v1/teesheets/golfClubs/{club_id}/courses/{course_id}/types/0/teeSheets/{tee_sheet_id}/bookings/0/teeTimes/{tee_time_id}/{target_date}/false"
    res = session.get(rest_lock_url, headers=headers)
    return res.status_code == 200

def fetch_candidate_slots(session, headers, payload, preferred_courses, min_min, max_min, requested_players):
    res = session.post(AVAILABILITY_URL, json=payload, headers=headers)
    if res.status_code != 200:
        return [], False, f"Availability check failed: {res.text}"

    candidate_slots = []
    has_unopen_booking_slots = False

    for bucket in res.json():
        for item in bucket.get("items", []):
            course_id = item.get("golfCourseId")
            tee_time_min = item.get("teeTime", 0)

            if preferred_courses and course_id not in preferred_courses:
                continue
            if not (min_min <= tee_time_min <= max_min):
                continue

            if item.get("bookingNotAllowed", False):
                has_unopen_booking_slots = True

            available_spots = 4 - item.get("playerCount", 0)
            if not item.get("bookingNotAllowed", False) and available_spots >= requested_players:
                candidate_slots.append(item)

    return candidate_slots, has_unopen_booking_slots, None

def reserve_slot(token, event_config, context=None):
    session = requests.Session()
    headers = get_base_headers()
    headers["authorization"] = f"Bearer {token}"

    target_date = event_config.get("targetDate", "2026-08-30")
    club_group_id = event_config.get("golfClubGroupId", 8)
    member_profile_id = event_config.get("memberProfileId", 1129941)
    member_email = event_config.get("email", "rubenhnt@gmail.com")
    member_name = event_config.get("name", "Ruben Hernandez")
    requested_players = int(event_config.get("playerCount", 1))
    preferred_courses = event_config.get("preferredCourses", [])
    
    time_window = event_config.get("timeWindow", {})
    min_min = time_str_to_minutes(time_window.get("earliestTime", "06:00"))
    max_min = time_str_to_minutes(time_window.get("latestTime", "20:00"))

    # Discover course booking policy (days in advance & opening time e.g. Midnight vs 6 AM)
    advance_days, opening_time = fetch_club_booking_policy(session, token, club_group_id)
    if "advanceDays" in event_config:
        advance_days = int(event_config["advanceDays"])
    if "openingTime" in event_config:
        opening_time = str(event_config["openingTime"])

    # 1. Fetch group sheet
    payload = {
        "configurationTypeId": 0,
        "date": target_date,
        "golfClubGroupId": club_group_id,
        "golfClubId": 0,
        "golfCourseId": 0,
        "groupSheetTypeId": 0,
        "memberProfileId": member_profile_id
    }

    open_time_utc = calculate_booking_open_time(target_date, advance_days, opening_time)
    now_utc = datetime.now(timezone.utc)

    # Initial scan
    candidate_slots, has_unopen_booking_slots, err_msg = fetch_candidate_slots(
        session, headers, payload, preferred_courses, min_min, max_min, requested_players
    )

    if err_msg:
        return {"status": "error", "message": err_msg}

    # If opening time is in the future, schedule EventBridge execution
    if open_time_utc > (now_utc + timedelta(seconds=120)):
        return schedule_eventbridge_execution(event_config, open_time_utc, advance_days, opening_time, context)

    # Rapid Burst Retry: If we are at the opening time window but candidate_slots is empty because server tee sheet hasn't unlocked yet, retry for up to 25 seconds!
    max_attempts = 15
    attempt = 0
    while not candidate_slots and attempt < max_attempts and has_unopen_booking_slots:
        attempt += 1
        time.sleep(1.2)
        candidate_slots, has_unopen_booking_slots, _ = fetch_candidate_slots(
            session, headers, payload, preferred_courses, min_min, max_min, requested_players
        )

    if not candidate_slots:
        if has_unopen_booking_slots and open_time_utc > now_utc:
            return schedule_eventbridge_execution(event_config, open_time_utc, advance_days, opening_time, context)
        return {"status": "error", "message": f"No available slots on {target_date} matching criteria."}

    def slot_sort_key(slot):
        course_rank = preferred_courses.index(slot.get("golfCourseId")) if slot.get("golfCourseId") in preferred_courses else 99
        return (course_rank, slot.get("teeTime", 9999))

    selected = sorted(candidate_slots, key=slot_sort_key)[0]

    club_id = selected.get("golfClubId")
    course_id = selected.get("golfCourseId")
    tee_time_id = selected.get("teeTimeId")
    tee_sheet_id = selected.get("teeSheetId")
    total_price = selected.get("price", 51.0)

    # 2. Acquire Locks Immediately
    acquire_locks(session, token, club_id, course_id, tee_sheet_id, tee_time_id, target_date, member_profile_id)

    # 3. Submit Booking
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    players_list = []
    for i in range(requested_players):
        players_list.append({
            "backNineTeeTimeId": 0, "backNineTeeTime": 0, "cartCount": 1,
            "email": member_email if i == 0 else "", "firstName": "", "lastName": "",
            "hasPullCart": False, "isCheckedIn": False, "isDirty": True,
            "greenFee": total_price, "cartFee": 0, "mappingId": -1,
            "memberProfileId": member_profile_id if i == 0 else 0,
            "name": member_name if i == 0 else f"Guest {i}", "paid": False,
            "teeSheetNoteDate": now_iso, "teeTimePlayersId": 0, "teeTimeId": tee_time_id,
            "totalToPay": total_price, "modifiedDateTime": now_iso, "seasonPasses": []
        })

    book_payload = {
        "allowFivesomes": False, "bookingNote": None, "bookingPage": "online-tee-times",
        "configurationTypeId": 0, "confirmationNumber": "", "golfClubId": club_id,
        "golfCourseId": course_id, "isProshopBooking": False, "isOpen": True,
        "noShowTermsAccepted": False, "players": players_list,
        "cartFeesCountyTaxRate": 0.01, "cartFeesStateTaxRate": 0.065,
        "greenFeesCountyTaxRate": 0.01, "greenFeesStateTaxRate": 0.065,
        "teeSheetDate": f"{target_date}T12:00:00Z", "teeSheetId": tee_sheet_id,
        "teeTimeBookingId": 0, "teeTimeOwnerId": member_profile_id
    }

    book_res = session.post(BOOKING_URL, json=book_payload, headers=headers)
    return {
        "status": "complete",
        "course": selected.get("name"),
        "teeTimeMinute": selected.get("teeTime"),
        "response": book_res.json()
    }

def handler(event, context):
    body = event.get("body")
    config = json.loads(body) if isinstance(body, str) else (body or event)

    username = os.environ.get("MEMBERSPORTS_USER", "rubenhnt@gmail.com")
    password = os.environ.get("MEMBERSPORTS_PASS", "")

    token = login_and_get_token(username, password)
    if not token:
        return {
            "statusCode": 500,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "Authentication failed"})
        }

    result = reserve_slot(token, config, context)
    status_code = 200 if result.get("status") in ["complete", "scheduled"] else 400
    
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        },
        "body": json.dumps(result)
    }
