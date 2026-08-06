import time
import sys
from typing import NoReturn


class LogLevel(object):
    DEBUG = (0, "DEBUG")
    INFO = (1, "INFO")
    WARN = (2, "WARN")
    ERROR = (3, "ERROR")
    NONE = (4, "NONE")


log_config = [LogLevel.INFO[0]]


def set_log_level(level):
    log_config[0] = int(level)


def log(level, *args):
    if level[0] < log_config[0]:
        return
    level_str = level[1]
    now = time.time()
    time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
    time_str += ".%03i" % int((now - int(now)) * 1000)
    # filename = os.path.split(sys._getframe(2).f_code.co_filename)[1]
    # lineno = sys._getframe(2).f_lineno
    content = args[0] % args[1:] if len(args) > 1 else str(args[0])
    print("%s [%s] %s" % (time_str, level_str, content))
    sys.stdout.flush()


def log_debug(*args):
    log(LogLevel.DEBUG, *args)


def log_info(*args):
    log(LogLevel.INFO, *args)


def log_warn(*args):
    log(LogLevel.WARN, *args)


def log_error(*args):
    log(LogLevel.ERROR, *args)


def abort(*args) -> NoReturn:
    log(LogLevel.ERROR, *args)
    raise Exception()


def abort_if(ret: bool, *args) -> NoReturn | None:
    if ret:
        abort(*args)
