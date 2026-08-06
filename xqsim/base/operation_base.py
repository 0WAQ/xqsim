from .module_base import ModuleBase

class OperationBase(ModuleBase):
    def __init__(self, *args):
        super().__init__(*args)

    def apply(self, di, alpha):
        pass
