import pandas as pd
from qsim.api import *


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("python xxxx.py csv_dir output_dir")
        exit(1)
    csv_dir = sys.argv[1]
    output_dir = sys.argv[2]

    dr: DataRepository = init_dr(meta_dir="/home/michael/cc",
                                 total=True,
                                 output_cache_dir=output_dir)

    alpha_path = csv_dir

    alpha_name = os.path.split(os.path.abspath(alpha_path))[1]

    path_list = []
    for year in os.listdir(alpha_path):
        for month in os.listdir(os.path.join(alpha_path, year)):
            for file_name in os.listdir(os.path.join(alpha_path, year, month)):
                # print(file_name)
                path_list.append(os.path.join(alpha_path, year, month, file_name))
    path_list.sort()
    # print(path_list)
    numpy_list_dict = {}

    begin_trading_day = int(os.path.splitext(path_list[0])[1][1:])
    end_trading_day = int(os.path.splitext(path_list[-1])[1][1:])
    log_info("alpha name: %s, from %s to %s", alpha_name, begin_trading_day, end_trading_day)

    for path in path_list:
        df = pd.read_csv(path, sep="|", header=None)
        # print(df)
        for index, row in df.iteritems():
            if row.dtype == np.object:
                continue
            numpy_list_dict.setdefault(index, []).append(row)
            # print(row)

    for name, result in numpy_list_dict.items():
        array = np.array(result)
        # print(array)
        # print(array.shape)
        dr.write_data(alpha_name,
                      alpha_name + "_" + str(name), array,
                      begin_trading_day=begin_trading_day,
                      end_trading_day=end_trading_day,
                      overwrite=True)
