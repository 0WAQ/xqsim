import click
import shutil
from functools import wraps
from qsim.provider_base import *
from qsim.data_manager import *


def menu():
    file_name = os.path.abspath(os.path.basename(__file__))
    print("python %s meta=[meta_dir(default is /cc)] action=[action] **kwargs" % file_name)
    print("action=show dst=[to_show_path]")
    print("action=check dst=[to_check_path]")
    print("action=merge dst=[dst_path] src=[src_path]")
    print("action=merge_dir dst=[dst_dir] src=[src_dir]")


class Tools(object):
    def __init__(self, meta):
        self.meta: Meta = meta

    @staticmethod
    def show(path):
        if not os.path.exists(path):
            log_error("path not exist: %s", path)
            return
        header = DataManager.load_header(path)
        log_info("path %s header %s", path, header)

    def check(self, path, begin_date, end_date) -> bool:
        # check dst begin date and end date
        if not os.path.exists(path):
            log_error("path not exist: %s", path)
            return False
        # log_info("Check %s", path)
        header = DataManager.load_header(path)
        if int(header.begin_trading_day) != int(begin_date):
            log_error("Begin date not match: %s != %s, path %s", int(header.begin_trading_day), begin_date, path)
            return False
        if int(header.end_trading_day) != int(end_date):
            log_error("End date not match: %s != %s, path %s", int(header.end_trading_day), end_date, path)
            return False

        shape, dtype_tuple = DataManager(self.meta).get_file_shape(path, header, int(header.di_size))

        total_size = dtype_tuple[1]
        for i in range(0, len(shape)):
            total_size *= shape[i]

        file_size = os.path.getsize(path)

        if file_size != total_size + DATA_HEADER_LENGTH:
            log_error("File size not match: %s != %s, path %s", file_size, total_size + DATA_HEADER_LENGTH, path)
            return False

        return True

    def check_dir(self, dir_path, begin_date, end_date) -> bool:
        if not os.path.exists(dir_path):
            log_error("Dir path not exist: %s", dir_path)
            return False
        log_info("Check dir %s", dir_path)
        for file_name in os.listdir(dir_path):
            path = os.path.join(dir_path, file_name)
            if os.path.isfile(path):
                # file data
                if not self.check(path, begin_date, end_date):
                    return False
            elif os.path.isdir(path):
                # dir data
                for trading_day in [str(self.meta.date_index[di]) for di in range(self.meta.di_mapping[int(begin_date)], self.meta.di_mapping[int(end_date)] + 1)]:
                    trading_day_dir = os.path.join(dir_path, trading_day)
                    if not os.path.exists(trading_day_dir):
                        log_error("trading day %s not found in path %s", trading_day, dir_path)
                        return False
                    # for file_name2 in os.listdir(trading_day_dir):
                    #     if not self.check(os.path.join(trading_day_dir, file_name2), trading_day, trading_day):
                    #         return False
                break
            else:
                abort("path error: %s", path)
        return True

    def check_cc(self, cc_path, begin_date, end_date) -> bool:
        log_info("Check common cache %s with %s -- %s", cc_path, begin_date, end_date)
        if not os.path.exists(cc_path):
            log_error("Common cache path not exist: %s", cc_path)
            return False
        for dir_name in os.listdir(cc_path):
            if dir_name == "meta":
                continue
            for dir_name2 in os.listdir(os.path.join(cc_path, dir_name)):
                dir_path = os.path.join(cc_path, dir_name, dir_name2)
                if not self.check_dir(dir_path, begin_date, end_date):
                    log_error("Check common cache %s failed", cc_path)
                    return False
        log_info("Check common cache %s ok", cc_path)
        return True

    def merge(self, dst_path, src_path, force=0) -> bool:
        if not os.path.exists(src_path):
            log_error("Src path not exist: %s", src_path)
            return False
        if force == 2 and os.path.exists(dst_path):
            os.remove(dst_path)
        if not os.path.exists(dst_path):
            common_utils.ensure_dir(dst_path)
            common_utils.copy_with_check(src_path, dst_path)
            log_info("Copy file %s from %s", dst_path, src_path)
            return True
        dst_file_name = os.path.split(dst_path)[1]
        src_file_name = os.path.split(src_path)[1]
        abort_if(dst_file_name != src_file_name, "file not match: %s != %s", dst_file_name, src_file_name)

        dst_header = DataManager.load_header(dst_path)
        src_header = DataManager.load_header(src_path)
        log_info("Merge %s from %s", dst_path, src_path)
        log_info("Src file header: %s", src_header)
        log_info("Before update, dst header: %s", dst_header)
        abort_if(dst_header.ti_size != src_header.ti_size, "ti size not match: %s != %s", dst_header.ti_size, src_header.ti_size)
        abort_if(dst_header.ii_size != src_header.ii_size, "ii size not match: %s != %s", dst_header.ii_size, src_header.ii_size)
        abort_if(dst_header.type_size != src_header.type_size, "type size not match: %s != %s", dst_header.type_size, src_header.type_size)

        ii_size = int(dst_header.ii_size)
        ti_size = int(dst_header.ti_size)
        type_size = int(dst_header.type_size)

        dst_begin_di = self.meta.di_mapping[int(dst_header.begin_trading_day)]
        dst_end_di = self.meta.di_mapping[int(dst_header.end_trading_day)]
        src_begin_di = self.meta.di_mapping[int(src_header.begin_trading_day)]
        src_end_di = self.meta.di_mapping[int(src_header.end_trading_day)]

        if src_begin_di <= dst_begin_di and src_end_di >= dst_end_di:
            os.remove(dst_path)
            common_utils.ensure_dir(dst_path)
            common_utils.copy_with_check(src_path, dst_path)
            log_info("Copy file %s from %s because of superset", dst_path, src_path)
            return True

        abort_if(dst_begin_di > src_begin_di,
                 "trading day not match: dst begin day(%s) > src begin day(%s)", dst_header.begin_trading_day, src_header.begin_trading_day)
        abort_if(dst_end_di + 1 < src_begin_di,
                 "trading day not match: dst end day(%s) + 1 < src begin day(%s)", dst_header.end_trading_day, src_header.begin_trading_day)

        with open(dst_path, "r+b") as dst_writer:
            dst_writer.seek(DATA_HEADER_LENGTH + (src_begin_di - dst_begin_di) * ii_size * ti_size * type_size, 0)
            with open(src_path, "rb") as src_writer:
                src_writer.seek(DATA_HEADER_LENGTH, 0)
                while True:
                    data = src_writer.read(ii_size * ti_size * type_size)
                    if not data:
                        break
                    dst_writer.write(data)

            if src_end_di > dst_end_di:
                dst_header.end_trading_day = src_header.end_trading_day
                dst_header.di_size = str(src_end_di - dst_begin_di + 1).encode("utf-8")
                dst_header.end_ti = str(ti_size - 1).encode("utf-8")
                dst_writer.seek(0)
                dst_writer.write(dst_header.encode())

        log_info("After update, dst header: %s", dst_header)
        return True

    def merge_dir(self, dst_dir, src_dir, force=0) -> bool:
        if force == 1 and os.path.exists(dst_dir):
            shutil.rmtree(dst_dir)
        if not os.path.exists(dst_dir):
            shutil.copytree(src_dir, dst_dir, copy_function=common_utils.copy_with_check)
            log_info("Copy dir %s to %s", src_dir, dst_dir)
            return True
        log_info("Merge dir %s to %s", src_dir, dst_dir)
        for file_name in os.listdir(src_dir):
            src_path = os.path.join(src_dir, file_name)
            if os.path.isfile(src_path):
                if not self.merge(os.path.join(dst_dir, file_name), src_path, force):
                    return False
            elif os.path.isdir(src_path):
                if not self.merge_dir(os.path.join(dst_dir, file_name), src_path, force):
                    return False
            else:
                abort("path error: %s", src_path)
        return True

    def merge_cc(self, dst_cc, src_cc, force=0) -> bool:
        if not os.path.exists(dst_cc):
            shutil.copytree(src_cc, dst_cc, copy_function=common_utils.copy_with_check)
            log_info("Copy common cache %s to %s", src_cc, dst_cc)
            return True
        log_info("Merge common cache %s to %s", src_cc, dst_cc)
        for dir_name in os.listdir(src_cc):
            if dir_name == "meta":
                src_meta_dir = os.path.join(src_cc, dir_name)
                dst_meta_dir = os.path.join(dst_cc, dir_name)
                log_info("Copy meta %s to %s", src_meta_dir, dst_meta_dir)
                common_utils.copy_dir(src_meta_dir, dst_meta_dir)
                continue
            for dir_name2 in os.listdir(os.path.join(src_cc, dir_name)):
                src_dir = os.path.join(src_cc, dir_name, dir_name2)
                dst_dir = os.path.join(dst_cc, dir_name, dir_name2)
                if not self.merge_dir(dst_dir, src_dir, force):
                    return False
        return True


@click.group()
def cli():
    pass


def init(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        meta_dir = kwargs.get("meta")
        dr = init_dr(meta_dir=meta_dir, total=True)
        kwargs["meta_cls"] = dr.meta
        return f(*args, **kwargs)

    return decorated


@cli.command()
@click.option('--meta', '-m', help='Meta dir, default is /cc', default="/cc")
@click.option('--dst', '-d', help="Show dst path", required=True)
@init
def show(**config):
    Tools.show(config["dst"])


@cli.command()
@click.option('--meta', '-m', help='Meta dir, default is /cc', default="/cc")
@click.option('--dst', '-d', help="Check dst path", required=True)
@click.option('--begin_date', '-b', help="Check begin date", required=True)
@click.option('--end_date', '-e', help="Check end date", required=True)
@init
def check(**config):
    Tools(config["meta_cls"]).check(config["dst"], config["begin_date"], config["end_date"])


@cli.command()
@click.option('--meta', '-m', help='Meta dir, default is /cc', default="/cc")
@click.option('--dst', '-d', help="Check dir path", required=True)
@click.option('--begin_date', '-b', help="Check begin date", required=True)
@click.option('--end_date', '-e', help="Check end date", required=True)
@init
def check_dir(**config):
    Tools(config["meta_cls"]).check_dir(config["dst"], config["begin_date"], config["end_date"])


@cli.command()
@click.option('--meta', '-m', help='Meta dir, default is /cc', default="/cc")
@click.option('--dst', '-d', help="Check cc path", required=True)
@click.option('--begin_date', '-b', help="Check begin date", required=True)
@click.option('--end_date', '-e', help="Check end date", required=True)
@init
def check_cc(**config):
    Tools(config["meta_cls"]).check_cc(config["dst"], config["begin_date"], config["end_date"])


@cli.command()
@click.option('--meta', '-m', help='Meta dir, default is /cc', default="/cc")
@click.option('--dst', '-d', help="Merge dst path", required=True)
@click.option('--src', '-s', help="Merge src path", required=True)
@init
def merge(**config):
    Tools(config["meta_cls"]).merge(config["dst"], config["src"])


@cli.command()
@click.option('--meta', '-m', help='Meta dir, default is /cc', default="/cc")
@click.option('--dst', '-d', help="Merge dst dir", required=True)
@click.option('--src', '-s', help="Merge src dir", required=True)
@init
def merge_dir(**config):
    Tools(config["meta_cls"]).merge_dir(config["dst"], config["src"])


@cli.command()
@click.option('--meta', '-m', help='Meta dir, default is /cc', default="/cc")
@click.option('--dst', '-d', help="Merge dst cc", required=True)
@click.option('--src', '-s', help="Merge src cc", required=True)
@init
def merge_cc(**config):
    Tools(config["meta_cls"]).merge_cc(config["dst"], config["src"])


if __name__ == '__main__':
    cli()
