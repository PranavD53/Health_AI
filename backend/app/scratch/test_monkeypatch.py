import datetime
from app.timezone_helper import get_ist_now, get_ist_date

class PatchedDatetime(datetime.datetime):
    @classmethod
    def utcnow(cls):
        return get_ist_now()
    
    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return get_ist_now()
        return datetime.datetime.now(tz)

class PatchedDate(datetime.date):
    @classmethod
    def today(cls):
        return get_ist_date()

class PatchedDatetimeModule:
    def __init__(self, original):
        self._original = original
        self.datetime = PatchedDatetime
        self.date = PatchedDate
        self.timedelta = original.timedelta
        self.timezone = original.timezone

    def __getattr__(self, name):
        return getattr(self._original, name)

# Overwrite in local namespace
datetime_patched = PatchedDatetimeModule(datetime)

print("Original utcnow:", datetime.datetime.utcnow())
print("Patched utcnow:", datetime_patched.datetime.utcnow())
print("Original date today:", datetime.date.today())
print("Patched date today:", datetime_patched.date.today())
print("Original datetime now:", datetime.datetime.now())
print("Patched datetime now:", datetime_patched.datetime.now())
