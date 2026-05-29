# cython: language_level=3
from static_provider import *


class Provider(StaticProvider):
    def __init__(self, *args):
        super().__init__(*args)

    def generate(self):
        enum_index = self.meta.enum_index_dict["code_name"]
        print(enum_index)


def main():
    builder_run(meta_dir="/cc", begin_date=20180101, end_date=20180103, output_cache_dir="./cc_update")


if __name__ == '__main__':
    main()
