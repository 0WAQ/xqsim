import importlib
import os
import HTMLTestRunner
import unittest
from xqsim.alpha_base import *


class TestLoaderWithKwargs(unittest.TestLoader):
    """A test loader which allows to parse keyword arguments to the
       test case class."""

    def load_tests(self, test_case_class, *args, **kwargs):
        """Return a suite of all tests cases contained in
           testCaseClass."""
        if issubclass(test_case_class, unittest.suite.TestSuite):
            raise TypeError("Test cases should not be derived from "
                            "TestSuite. Maybe you meant to derive from"
                            " TestCase?")
        test_case_names = self.getTestCaseNames(test_case_class)
        if not test_case_names and hasattr(test_case_class, 'runTest'):
            test_case_names = ['runTest']

        # Modification here: parse keyword arguments to testCaseClass.
        test_cases = []
        for test_case_name in test_case_names:
            test_cases.append(test_case_class(test_case_name, *args, **kwargs))
        return test_cases


class HTMLRunner(object):
    def __init__(self, file_path, title, description=""):
        self.file_path = file_path
        common_utils.ensure_dir(file_path)
        self.result_path = os.path.join(os.path.dirname(file_path), "result.log")
        fp = open(self.file_path, 'wb')
        self.runner = HTMLTestRunner.HTMLTestRunner(stream=fp, verbosity=2, title=title, description=description)
        self.suite = unittest.TestSuite()

    def add_cls(self, cls, *args, **kwargs):
        loader = TestLoaderWithKwargs()
        testcases = loader.load_tests(cls, *args, **kwargs)
        self.suite.addTests(testcases)

    def add_module(self, module_name, *args, **kwargs):
        module = importlib.import_module(module_name)
        cls = getattr(module, "TestClass")
        self.add_cls(cls, *args, **kwargs)

    def run(self):
        result = self.runner.run(self.suite)
        result_dict = {
            "start_time": self.runner.startTime.strftime("%Y-%m-%d %H:%M:%S"),
            "stop_time": self.runner.stopTime.strftime("%Y-%m-%d %H:%M:%S"),
            "start_date": int(self.runner.startTime.strftime("%Y%m%d")),
            "stop_date": int(self.runner.stopTime.strftime("%Y%m%d")),
            "run": result.testsRun,
            "errors": len(result.errors),
            "failures": len(result.failures)
        }
        print(str(result_dict))
        with open(self.result_path, "w") as writer:
            writer.write(str(result_dict))

    @staticmethod
    def run_test(module_name, *args, **kwargs):
        module = importlib.import_module(module_name)
        cls = getattr(module, "TestClass")
        loader = TestLoaderWithKwargs()
        testcases = loader.load_tests(cls, *args, **kwargs)
        suite = unittest.TestSuite()
        suite.addTests(testcases)
        unittest.TextTestRunner(verbosity=2).run(suite)


if __name__ == '__main__':
    data_home = os.path.realpath(os.environ.get("XQSIM_DATA_HOME", "/usr/local/xqsim/data"))
    meta_dir = os.path.join(data_home, "stocks", "cc")
    begin_date = "TODAY-2"
    end_date = "TODAY-1"
    # begin_date = 20170103
    # end_date = 20210427
    back_days = 1
    data_limit = 1024
    cache_list = []

    dr = init_dr(meta_dir=meta_dir, begin_date=begin_date, end_date=end_date, back_days=back_days, data_limit=data_limit, cache_list=cache_list)

    html_runner = HTMLRunner("/tmp/ut/result.html", "Qsim data check result")
    html_runner.add_module("ut_cls.universe", dr)
    html_runner.add_module("ut_cls.kline", dr)
    html_runner.add_module("ut_cls.nan", dr)
    # html_runner.add_module("ut_cls.cw", dr)
    # html_runner.add_module("ut_cls.citics_index", dr)
    html_runner.run()

    # HTMLRunner.run_test("ut_cls.bar", dr)
