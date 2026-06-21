import datetime as _orig_datetime

# Indian Standard Time (IST) is UTC + 5:30
IST = _orig_datetime.timezone(_orig_datetime.timedelta(hours=5, minutes=30))

def get_ist_now() -> _orig_datetime.datetime:
    """Returns the current time in IST as a naive datetime object."""
    return _orig_datetime.datetime.now(IST).replace(tzinfo=None)

def get_ist_date() -> _orig_datetime.date:
    """Returns the current date in IST."""
    return get_ist_now().date()

class PatchedDatetime(_orig_datetime.datetime):
    @classmethod
    def utcnow(cls):
        return get_ist_now()
    
    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return get_ist_now()
        return _orig_datetime.datetime.now(tz)

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        # Instruct Pydantic to treat this class exactly like standard datetime
        return handler(_orig_datetime.datetime)

class PatchedDate(_orig_datetime.date):
    @classmethod
    def today(cls):
        return get_ist_date()

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        # Instruct Pydantic to treat this class exactly like standard date
        return handler(_orig_datetime.date)

class PatchedDatetimeModule:
    def __init__(self, original):
        self._original = original
        self.datetime = PatchedDatetime
        self.date = PatchedDate
        self.timedelta = original.timedelta
        self.timezone = original.timezone

    def __getattr__(self, name):
        return getattr(self._original, name)

# Expose the patched datetime module wrapper
datetime = PatchedDatetimeModule(_orig_datetime)
