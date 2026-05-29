from bsim.provider_base import *

dr = init_dr(meta_dir="/cc", begin_date=20200720, end_date=20200728)
data1 = dr.get_data("k.close").data  # get numpy
data2 = dr.get_data("k.open").data
data3 = data1 + data2
dr.write_data("output_dir", "data_name", data3)
