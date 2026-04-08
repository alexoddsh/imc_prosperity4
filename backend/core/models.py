import logging
from enum import Enum
from pydantic import BaseModel

class LogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "/logs/" not in record.getMessage()

class SystemEnum(Enum):
    PROSPERITY = 1
    PROSPERITY4TBX = 2

class RunRequest(BaseModel): 
    algo_file: str
    round: str
    year: str
