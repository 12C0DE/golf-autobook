import json
import os
import time
import uuid
import traceback
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
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


def minutes_to_time_str(mins):
    h = mins // 60
    m = mins % 60
    return f"{h:02d}:{m:02d}"


def fetch_club_booking_policy(session, token, club_group_id):
    """
    Queries MemberSports API to dynamically discover:
    1. advanceBookingDays (e.g. 7 days or 14 days in advance)
    2. onlineBookingStartTime (e.g. "06:00:00" vs "00:00:00" / Midnight)
    """
    headers = get_base_headers()
    headers["authorization"] = f"Bearer {token}"
    config_url = f"https://api.membersports.com/api/v1/golfclubs/group/{club_group_id}"

    try:
        print(f"[POLICY] Fetching booking policy from: {config_url}")
        res = session.get(config_url, headers=headers, timeout=10)
        print(f"[POLICY] Response status: {res.status_code}")
        if res.status_code == 200:
            data = res.json()
            days_ahead = data.get("advanceBookingDays") or data.get("onlineBookingDaysInAdvance") or 7
            start_time = data.get("onlineBookingStartTime") or data.get("bookingOpeningTime") or "06:00:00"
            print(f"[POLICY] Discovered policy -> Advance Days: {days_ahead}, Opening Time: {start_time}")
            return int(days_ahead), str(start_time)
        else:
            print(f"[POLICY] Non-200 response: {res.text[:200]}")
    except Exception as e:
        print(f"[POLICY-WARN] Failed to fetch club policy ({str(e)}). Falling back to defaults (7 days, 06:00:00).")

    return 7, "06:00:00"


def calculate_booking_open_time(target_date_str, advance_days=7, opening_time_str="06:00:00"):
    """
    Calculates the exact trigger time when booking opens for target_date_str.
    Supports Midnight ("00:00:00"), 6 AM ("06:00:00"), or any custom course opening time.
    Timezone assumes Central Time (UTC-5 offset).
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

    open_time_utc = datetime(
        open_date.year, open_date.month, open_date.day,
        utc_hour, open_minute, open_second,
        tzinfo=timezone.utc
    )
    return open_time_utc


def schedule_eventbridge_execution(event_config, open_time_utc, advance_days=7, opening_time="06:00:00", context=None):
    """
    Registers a one-time AWS EventBridge Schedule to fire this Lambda function
    automatically on the exact date & time when the booking window opens.
    Crucially injects `eventbridge_bypass: True` so the scheduled run directly executes.
    """
    target_date = event_config.get("targetDate")
    member_id = event_config.get("memberProfileId", 1129941)
    schedule_name = f"golf-autobook-{target_date}-{member_id}"

    early_trigger_time = open_time_utc - timedelta(minutes=2)
    formatted_open_time = early_trigger_time.strftime("%Y-%m-%dT%H:%M:%S")
    schedule_expression = f"at({formatted_open_time})"

    # Stamp explicit EventBridge bypass flag in the scheduled payload
    scheduled_payload = dict(event_config)
    scheduled_payload["eventbridge_bypass"] = True
    scheduled_payload["is_eventbridge"] = True

    lambda_arn = os.environ.get("LAMBDA_FUNCTION_ARN")
    if not lambda_arn and context and hasattr(context, "invoked_function_arn"):
        lambda_arn = context.invoked_function_arn

    role_arn = os.environ.get("SCHEDULER_ROLE_ARN", "")

    print(f"[SCHEDULER] Preparing EventBridge schedule '{schedule_name}' for {formatted_open_time} UTC")
    print(f"[SCHEDULER] Lambda Target ARN: {lambda_arn}")
    print(f"[SCHEDULER] Role ARN: {role_arn}")
    print(f"[SCHEDULER] Stamped bypass flag into payload: eventbridge_bypass=True, is_eventbridge=True")

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
                    "Input": json.dumps(scheduled_payload)
                },
                State="ENABLED",
                ActionAfterCompletion="DELETE"
            )
            schedule_arn = response.get("ScheduleArn")
            print(f"[SCHEDULER-SUCCESS] Schedule created successfully: {schedule_arn}")
            return {
                "status": "scheduled",
                "targetDate": target_date,
                "advanceDays": advance_days,
                "openingTime": opening_time,
                "scheduleArn": schedule_arn,
                "scheduledExecutionTime": open_time_utc.isoformat(),
                "message": f"Target date ({target_date}) is outside current {advance_days}-day booking window. AWS EventBridge Schedule '{schedule_name}' registered for {open_time_utc.strftime('%Y-%m-%d %H:%M:%S UTC')} ({advance_days} days prior at {opening_time}). Lambda will fire automatically with bypass flag enabled."
            }
        except Exception as e:
            print(f"[SCHEDULER-ERROR] Failed to register EventBridge schedule: {str(e)}")
            traceback.print_exc()
            return {
                "status": "scheduled",
                "targetDate": target_date,
                "advanceDays": advance_days,
                "openingTime": opening_time,
                "scheduledExecutionTime": open_time_utc.isoformat(),
                "message": f"Target date ({target_date}) is beyond {advance_days}-day window. Auto-trigger calculated for {open_time_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}. (EventBridge Note: {str(e)})"
            }

    print("[SCHEDULER-WARN] Boto3, LAMBDA_FUNCTION_ARN, or SCHEDULER_ROLE_ARN not configured. Returning schedule calculation.")
    return {
        "status": "scheduled",
        "targetDate": target_date,
        "advanceDays": advance_days,
        "openingTime": opening_time,
        "scheduledExecutionTime": open_time_utc.isoformat(),
        "message": f"Target date ({target_date}) is outside current {advance_days}-day booking window. Auto-booking execution scheduled for {open_time_utc.strftime('%Y-%m-%d %H:%M:%S UTC')} ({advance_days} days prior at {opening_time})."
    }


def login_and_get_token(session, username, password):
    headers = get_base_headers()
    payload = {
        "userName": username,
        "email": username,
        "password": password,
        "rememberMe": False,
        "golfClubId": 0,
        "recaptchaResponse": ""
    }
    print(f"[AUTH] Sending WebLogin request for user: '{username}'")
    try:
        res = session.post(LOGIN_URL, json=payload, headers=headers, timeout=12)
        print(f"[AUTH] Login response HTTP {res.status_code}")
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, dict):
                token = data.get("token") or data.get("accessToken")
                if token:
                    print(f"[AUTH-SUCCESS] Acquired Bearer token (length {len(token)}).")
                    return token
        print(f"[AUTH-FAILED] Could not acquire token. Response: {res.text[:300]}")
    except Exception as e:
        print(f"[AUTH-ERROR] Exception during login: {str(e)}")
        traceback.print_exc()
    return None


def acquire_locks(session, token, club_id, course_id, tee_sheet_id, tee_time_id, target_date, member_profile_id):
    """
    Executes MemberSports AppSync GraphQL broadcast lock and REST server hold.
    """
    print(f"[LOCKS] Acquiring locks for teeTimeId={tee_time_id}, teeSheetId={tee_sheet_id}, courseId={course_id}...")

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

    try:
        appsync_res = session.post(APPSYNC_URL, json=graphql_payload, headers=appsync_headers, timeout=5)
        print(f"[LOCKS] AppSync broadcast response: HTTP {appsync_res.status_code}")
    except Exception as e:
        print(f"[LOCKS-WARN] AppSync broadcast failed ({str(e)}), continuing to REST hold.")

    # 2. REST Database Server Hold
    headers = get_base_headers()
    headers["authorization"] = f"Bearer {token}"
    rest_lock_url = f"https://api.membersports.com/api/v1/teesheets/golfClubs/{club_id}/courses/{course_id}/types/0/teeSheets/{tee_sheet_id}/bookings/0/teeTimes/{tee_time_id}/{target_date}/false"

    try:
        res = session.get(rest_lock_url, headers=headers, timeout=8)
        print(f"[LOCKS] REST server hold response: HTTP {res.status_code}")
        return res.status_code == 200
    except Exception as e:
        print(f"[LOCKS-ERROR] REST lock exception: {str(e)}")
        return False


def fetch_candidate_slots(session, headers, payload, preferred_courses, min_min, max_min, requested_players):
    """
    Queries MemberSports onlineBookingTeeTimes endpoint and filters candidate slots.
    """
    res = session.post(AVAILABILITY_URL, json=payload, headers=headers, timeout=12)
    if res.status_code != 200:
        return [], False, f"Availability check failed with HTTP {res.status_code}: {res.text[:300]}"

    candidate_slots = []
    has_unopen_booking_slots = False

    buckets = res.json()
    total_slots_scanned = 0

    for bucket in buckets:
        for item in bucket.get("items", []):
            total_slots_scanned += 1
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

    print(f"[AVAILABILITY] Scanned {total_slots_scanned} items across {len(buckets)} buckets. Matching open slots: {len(candidate_slots)}. Unopened slots present: {has_unopen_booking_slots}")
    return candidate_slots, has_unopen_booking_slots, None


def run_booking_pipeline(event_config, context=None, session_token=None):
    """
    Encapsulates all MemberSports HTTP requests:
    1. Authenticate / get bearer token
    2. Query availability and run burst-retries if tee sheet is still opening
    3. Acquire AppSync GraphQL broadcast lock & REST server hold
    4. Post final booking payload to MemberSports
    """
    print("=================================================================")
    print("[PIPELINE] ⛳ Starting MemberSports Booking Pipeline")
    print(f"[PIPELINE] Target Date: {event_config.get('targetDate')}")
    print(f"[PIPELINE] Players: {event_config.get('playerCount')}")
    print(f"[PIPELINE] Preferred Courses: {event_config.get('preferredCourses')}")
    print(f"[PIPELINE] Time Window: {event_config.get('timeWindow')}")
    print("=================================================================")

    session = requests.Session()

    # Step 1: MemberSports Authentication
    token = session_token
    if not token:
        username = os.environ.get("MEMBERSPORTS_USER", "rubenhnt@gmail.com")
        password = os.environ.get("MEMBERSPORTS_PASS", "")
        token = login_and_get_token(session, username, password)
        if not token:
            error_msg = "Authentication failed: unable to acquire MemberSports Bearer token."
            print(f"[PIPELINE-ERROR] {error_msg}")
            return {"status": "error", "message": error_msg}

    headers = get_base_headers()
    headers["authorization"] = f"Bearer {token}"

    if event_config.get("eventbridge_bypass"):
        print("[PIPELINE] Woke up early. Waiting for exactly 5:59:59.800 AM CDT...", flush=True)
        while True:
            now = datetime.now(ZoneInfo("America/Chicago"))
            
            # Fire 200 milliseconds before 6:00:00 AM (or immediately if already 6:00 AM+)
            if (now.hour > 5) or (now.hour == 5 and now.minute == 59 and now.second == 59 and now.microsecond >= 800000):
                print(f"[PIPELINE] 🚀 FIRING REQUEST AT {now.time()}", flush=True)
                break
            
            # Sleep briefly to avoid maxing out Lambda CPU billing
            time.sleep(0.05)

    # target_date = event_config.get("targetDate", "2026-08-30")
    target_date = event_config.get("targetDate", datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d"))
    club_group_id = event_config.get("golfClubGroupId", 8)
    member_profile_id = event_config.get("memberProfileId", 1129941)
    member_email = event_config.get("email", "rubenhnt@gmail.com")
    member_name = event_config.get("name", "Ruben Hernandez")
    requested_players = int(event_config.get("playerCount", 1))
    preferred_courses = event_config.get("preferredCourses", [])

    time_window = event_config.get("timeWindow", {})
    earliest_str = time_window.get("earliestTime", "06:00")
    latest_str = time_window.get("latestTime", "20:00")
    min_min = time_str_to_minutes(earliest_str)
    max_min = time_str_to_minutes(latest_str)

    # Step 2: MemberSports Query Availability
    payload = {
        "configurationTypeId": 0,
        "date": target_date,
        "golfClubGroupId": club_group_id,
        "golfClubId": 0,
        "golfCourseId": 0,
        "groupSheetTypeId": 0,
        "memberProfileId": member_profile_id
    }

    print(f"[PIPELINE] Querying MemberSports availability at {AVAILABILITY_URL}...")
    candidate_slots, has_unopen_booking_slots, err_msg = fetch_candidate_slots(
        session, headers, payload, preferred_courses, min_min, max_min, requested_players
    )

    if err_msg:
        print(f"[PIPELINE-ERROR] Availability check error: {err_msg}")
        return {"status": "error", "message": err_msg}

    # Step 3: Rapid Burst Retry (handles the exact moment the tee sheet opens at 6:00 AM)
    max_attempts = 15
    attempt = 0
    while not candidate_slots and attempt < max_attempts and has_unopen_booking_slots:
        attempt += 1
        print(f"[BURST-RETRY] Attempt {attempt}/{max_attempts}: Tee sheet still locking slots. Retrying in 1.2s...")
        time.sleep(1.2)
        candidate_slots, has_unopen_booking_slots, _ = fetch_candidate_slots(
            session, headers, payload, preferred_courses, min_min, max_min, requested_players
        )

    if not candidate_slots:
        fail_msg = f"No available slots on {target_date} matching window {earliest_str}-{latest_str} (Courses: {preferred_courses})."
        print(f"[PIPELINE-ERROR] {fail_msg}")
        return {"status": "error", "message": fail_msg}

    def slot_sort_key(slot):
        course_rank = preferred_courses.index(slot.get("golfCourseId")) if slot.get("golfCourseId") in preferred_courses else 99
        return (course_rank, slot.get("teeTime", 9999))

    selected = sorted(candidate_slots, key=slot_sort_key)[0]

    club_id = selected.get("golfClubId")
    course_id = selected.get("golfCourseId")
    course_name = selected.get("name", "Unknown Course")
    tee_time_id = selected.get("teeTimeId")
    tee_sheet_id = selected.get("teeSheetId")
    tee_time_min = selected.get("teeTime", 0)
    total_price = selected.get("price", 51.0)

    print(f"[PIPELINE] 🎯 Selected Slot -> Course: {course_name} (ID: {course_id}), Time: {minutes_to_time_str(tee_time_min)} ({tee_time_min}m), Price: ${total_price}, TeeTimeId: {tee_time_id}")

    # Step 4: MemberSports AppSync & REST Locks
    acquire_locks(session, token, club_id, course_id, tee_sheet_id, tee_time_id, target_date, member_profile_id)

    # Step 5: MemberSports Booking Submission
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

    print(f"[PIPELINE] Submitting final booking to {BOOKING_URL}...")
    book_res = session.post(BOOKING_URL, json=book_payload, headers=headers, timeout=15)
    print(f"[PIPELINE] Booking response: HTTP {book_res.status_code}")

    try:
        book_data = book_res.json()
    except Exception:
        book_data = {"rawResponse": book_res.text}

    if book_res.status_code not in (200, 201):
        print(f"[PIPELINE-ERROR] MemberSports booking failed: {book_data}")
        return {
            "status": "error",
            "message": f"MemberSports booking failed with HTTP {book_res.status_code}",
            "response": book_data
        }

    print("[PIPELINE-SUCCESS] 🎉 Tee time successfully booked!")
    return {
        "status": "complete",
        "course": course_name,
        "teeTimeMinute": tee_time_min,
        "teeTimeFormatted": minutes_to_time_str(tee_time_min),
        "targetDate": target_date,
        "response": book_data
    }


def reserve_slot(token, event_config, context=None):
    """
    Maintains backward compatibility with any external callers.
    Routes execution to run_booking_pipeline.
    """
    return run_booking_pipeline(event_config, context=context, session_token=token)


def is_eventbridge_invocation(event, config):
    """
    Determines if the current invocation is an EventBridge-triggered run
    or contains an explicit bypass flag to skip 7-day date math.
    """
    # 1. Explicit bypass flags in config payload
    if config.get("eventbridge_bypass") in (True, "true", "True", 1):
        return True, "eventbridge_bypass flag in config"
    if config.get("is_eventbridge") in (True, "true", "True", 1):
        return True, "is_eventbridge flag in config"
    if config.get("isEventBridge") in (True, "true", "True", 1):
        return True, "isEventBridge flag in config"
    if config.get("bypassDateCheck") in (True, "true", "True", 1):
        return True, "bypassDateCheck flag in config"
    if config.get("bypass_date_math") in (True, "true", "True", 1):
        return True, "bypass_date_math flag in config"

    # 2. EventBridge standard event envelope metadata
    if isinstance(event, dict):
        if event.get("detail-type") in ("Scheduled Event", "EventBridge Scheduler"):
            return True, f"EventBridge detail-type: {event.get('detail-type')}"
        if event.get("source") in ("aws.scheduler", "aws.events"):
            return True, f"EventBridge source: {event.get('source')}"
        if event.get("eventbridge_bypass") in (True, "true", "True", 1):
            return True, "eventbridge_bypass at event root"

    return False, "Standard request (no bypass detected)"


def handler(event, context):
    print("=================================================================")
    print(f"[HANDLER-START] Lambda invoked at {datetime.now(timezone.utc).isoformat()}")
    print("=================================================================")

    # Parse config payload (handles API Gateway event with body, EventBridge payload, or direct test event)
    body = event.get("body") if isinstance(event, dict) else None
    if body and isinstance(body, str):
        try:
            config = json.loads(body)
        except Exception:
            config = event
    elif isinstance(body, dict):
        config = body
    else:
        config = event if isinstance(event, dict) else {}

    target_date = config.get("targetDate", datetime.now().strftime("%Y-%m-%d"))
    club_group_id = config.get("golfClubGroupId", 8)

    # Check for EventBridge Bypass Flag
    is_bypass, bypass_reason = is_eventbridge_invocation(event, config)
    print(f"[ROUTING] Invocation mode: {bypass_reason}")

    if is_bypass:
        print(f"[ROUTING] 🚀 EventBridge bypass active! Skipping 7-day date math check. Immediately executing run_booking_pipeline for {target_date}...")
        result = run_booking_pipeline(config, context=context)
    else:
        print(f"[ROUTING] 🔍 Checking booking window policy for targetDate: {target_date}...")
        session = requests.Session()
        username = os.environ.get("MEMBERSPORTS_USER", "rubenhnt@gmail.com")
        password = os.environ.get("MEMBERSPORTS_PASS", "")
        token = login_and_get_token(session, username, password)

        advance_days, opening_time = 7, "06:00:00"
        if token:
            advance_days, opening_time = fetch_club_booking_policy(session, token, club_group_id)

        if "advanceDays" in config:
            advance_days = int(config["advanceDays"])
        if "openingTime" in config:
            opening_time = str(config["openingTime"])

        open_time_utc = calculate_booking_open_time(target_date, advance_days, opening_time)
        now_utc = datetime.now(timezone.utc)

        print(f"[DATE-CHECK] Target Date: {target_date}")
        print(f"[DATE-CHECK] Advance Days: {advance_days}, Opening Time: {opening_time}")
        print(f"[DATE-CHECK] Calculated Booking Open Time (UTC): {open_time_utc.isoformat()}")
        print(f"[DATE-CHECK] Current UTC Time: {now_utc.isoformat()}")

        # If opening time is more than 120 seconds in the future, schedule EventBridge execution
        if open_time_utc > (now_utc + timedelta(seconds=120)):
            print(f"[DATE-CHECK] ⏳ Booking window is in the future. Scheduling execution via AWS EventBridge Scheduler...")
            result = schedule_eventbridge_execution(config, open_time_utc, advance_days, opening_time, context)
        else:
            print(f"[DATE-CHECK] ✅ Target date is within the open booking window. Executing booking pipeline...")
            result = run_booking_pipeline(config, context=context, session_token=token)

    status_code = 200 if result.get("status") in ["complete", "scheduled"] else 400
    print(f"[HANDLER-END] Execution finished. Status: {result.get('status')}, StatusCode: {status_code}")

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
