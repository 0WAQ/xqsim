from qsim.api import *


class OperationDemo(alphabase.AlphaOperationBase):
    def __init__(self, *args):
        super(OperationDemo, self).__init__(*args)

    def apply(self, didx, alpha):
        log_info("%s apply %s", self.id, didx)
        # print(self.parent_module.cfg)


def create(*args):
    return OperationDemo(*args)
