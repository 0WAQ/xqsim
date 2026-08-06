import paramiko
import stat
import os


class SSH(object):
    def __init__(self, ip, port, username, password):
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(hostname=ip, port=port, username=username, password=password)
        self.sftp = paramiko.SFTPClient.from_transport(self.ssh.get_transport())

    def exec_cmd(self, cmd):
        stdin, stdout, stderr = self.ssh.exec_command(cmd)
        stdout_str = str(stdout.read()).strip()
        stderr_str = str(stderr.read()).strip()
        return stdout_str, stderr_str

    def put(self, local_path, remote_path):
        print("put from %s to %s" % (local_path, remote_path))
        self.sftp.put(local_path, remote_path)

    def get(self, remote_path, local_path):
        print("get from %s to %s" % (remote_path, local_path))
        self.sftp.get(remote_path, local_path)

    def __get_all_files_in_remote_dir(self, remote_dir):
        # 保存所有文件的列表
        all_files = list()

        # 去掉路径字符串最后的字符'/'，如果有的话
        if remote_dir[-1] == '/':
            remote_dir = remote_dir[0:-1]

        # 获取当前指定目录下的所有目录及文件，包含属性值
        files = self.sftp.listdir_attr(remote_dir)
        for x in files:
            # remote_dir目录中每一个文件或目录的完整路径
            filename = remote_dir + '/' + x.filename
            # 如果是目录，则递归处理该目录，这里用到了stat库中的S_ISDIR方法，与linux中的宏的名字完全一致
            if stat.S_ISDIR(x.st_mode):
                all_files.extend(self.__get_all_files_in_remote_dir(filename))
            else:
                all_files.append(filename)
        return all_files

    def get_dir(self, remote_dir, local_dir):
        remote_files = self.__get_all_files_in_remote_dir(remote_dir)
        for remote_file in remote_files:
            filename = remote_file[remote_file.index(remote_dir) + len(remote_dir):]
            local_file = local_dir + "/" + filename
            dir_path = os.path.split(local_file)[0]
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
            self.get(remote_file, local_file)


class Host(object):
    def __init__(self, name, ip, port, username, password):
        self.name = name
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.ssh = SSH(ip, port, username, password)
        print("Create host %s, %s@%s:%s" % (self.name, self.username, self.ip, self.port))

    def __repr__(self):
        return str(self.__dict__)
