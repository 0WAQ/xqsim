import os


XQSIM_DATA_HOME = os.path.realpath(
    os.environ.get("XQSIM_DATA_HOME", "/usr/local/xqsim/data")
)
STOCKS_CC_DIR = os.path.join(XQSIM_DATA_HOME, "stocks", "cc")
STOCKS_UPDATE_DIR = os.path.join(XQSIM_DATA_HOME, "stocks", "cc_update")
