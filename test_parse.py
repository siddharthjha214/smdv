import pytz
from datetime import datetime

IST = pytz.timezone("Asia/Kolkata")

def format_youtube_date(upload_date):
    try:
        if isinstance(upload_date, str):
            if upload_date.isdigit() and len(upload_date) > 8:
                upload_date = float(upload_date)
            elif upload_date.isdigit() and len(upload_date) == 8:
                dt = datetime.strptime(upload_date, "%Y%m%d")
                dt_ist = IST.localize(dt)
                return dt_ist.strftime("%d %B %Y %I:%M %p IST")
            elif "-" in upload_date and len(upload_date) >= 10:
                dt = datetime.strptime(upload_date[:10], "%Y-%m-%d")
                dt_ist = IST.localize(dt)
                return dt_ist.strftime("%d %B %Y %I:%M %p IST")
                
        if isinstance(upload_date, (int, float)):
            dt_utc = datetime.fromtimestamp(upload_date, tz=pytz.utc)
            dt_ist = dt_utc.astimezone(IST)
            return dt_ist.strftime("%d %B %Y %I:%M %p IST")
            
        return "Unknown"
    except Exception as e:
        print(f"Error parsing {upload_date}:", e)
        return "Unknown"

print(format_youtube_date("20260430"))
print(format_youtube_date(1777549925))
print(format_youtube_date("1777549925"))
print(format_youtube_date("2026-04-30T12:00:00Z"))
print(format_youtube_date(None))
