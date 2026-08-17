from xqsim.api import *
import numpy as np

class OperationDemo(OperationBase):
    def __init__(self, *args):
        super(OperationDemo, self).__init__(*args)

    def apply(self, didx, alpha):
        print(f"{self.id} apply {didx}")
        # print(self.parent_module.cfg)


def create(*args):
    return OperationDemo(*args)
