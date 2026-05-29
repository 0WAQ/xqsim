from bsim.provider_base import *


class Provider(ProviderBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.enable_modify()    # allow to change exist file
        # self.enable_part_overwrite()    # allow to overwrite(part overwrite if append)

    def generate(self):
        data1 = self.dr.get_data("k.close").data  # get numpy
        data2 = self.dr.get_data("k.open").data
        data3 = data1 + data2
        self.append_data("data_name", data3)    # for daily data, or small data
        # self.append_compress_data("data_name", data3) for intraday data, or big data


def main():
    builder_run(meta_dir="/cc", begin_date=20200730, end_date=20200730, output_cache_dir="./cc_update")


if __name__ == '__main__':
    main()
