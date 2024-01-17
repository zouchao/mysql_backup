#!/usr/bin/env python
# encoding: utf-8
import datetime
import os
import shutil
import socket
import subprocess
import time
import zipfile
import yaml
import s3

# 数据库用户名
# db_user = "root"
# 数据库密码
#db_password = "2023@100BadIdeas"
# 备份目录
# backup_dir = "/root/mysql/backup"
# backup_prefix和backup_suffix分别为备份文件的前缀和后缀，如test_backup_2019-09-19-11则代表该文件是在2019年9月19日的11点时备份的
backup_prefix = "backup"
backup_suffix = "%Y%m%d-%H"
# 备份数据库列表
# backup_databases = [
#     "becoming",
#     "alicecam",
#     "drone_ci",
#     "kegel",
#     "stresswatch",
#     "stretch_java",
# ]
# 容器名
# container_name = "mysqldb"
# 过期小时，定期删除5个小时前的备份文件
expire_hour = 5


# 获取备份文件名
def get_backup_filename():
    t = time.strftime(backup_suffix, time.localtime())
    return "%s_%s" % (backup_prefix, t)


def get_backup_path(backup_dir):
    return "%s%s%s" % (backup_dir, os.sep, get_backup_filename())


# 获取过期时间戳
def get_expire_time():
    t = datetime.datetime.now() - datetime.timedelta(hours=expire_hour)
    return int(time.mktime(t.timetuple()))

def create_dir(dir_path):
    # 如果目录存在则退出
    if os.path.exists(dir_path):
        return
    os.mkdir(dir_path)

def get_base_name(file_path):
    return os.path.basename(file_path)

def get_file_name(file_path):
    # 获取文件名（不包含扩展名）
    base_name = os.path.basename(file_path)
    file_name = os.path.splitext(base_name)[0]
    return file_name

def get_host_ip():
    """
    查询本机ip地址
    :return: ip
    """
    return "139.162.20.83"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
        return ip

cmd_template = "docker exec -it {container_name} mysqldump -u{db_user} -p{db_password} {database} > {file_path}"

# 备份指定数据库
def backup_database(backup_path, database, container_name, db):
    file_path = os.sep.join([backup_path, "%s.sql" % database])
    d = {
        "container_name": container_name,
        "db_user": db['db_user'],
        "db_password": db['db_password'],
        "database": database,
        "file_path": file_path,
    }
    cmd = cmd_template.format(**d)
    subprocess.call(cmd, shell=True)


def zip_dir(dir_path):
    file_path = '.'.join([dir_path, "zip"])
    if os.path.exists(file_path):
        os.remove(file_path)
    z = zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED)
    for root, directories, files in os.walk(dir_path):
        fpath = root.replace(dir_path, '')
        fpath = fpath and fpath + os.sep or ''
        for filename in files:
            z.write(os.path.join(root, filename), fpath + filename)
    z.close()
    return file_path

# 备份数据库
def backup(config):
    backup_dir, container_name, db = config['backup_dir'], config['container_name'], config['db']
    backup_path = get_backup_path(backup_dir)
    try:
        create_dir(backup_path)
        for database in db['databases']:
            backup_database(backup_path, database, container_name, db)
        zip_file = zip_dir(backup_path)
        s3.upload_to_s3(zip_file, get_base_name(zip_file))
    finally:
        shutil.rmtree(backup_path)


# 清理过期备份文件
def clean(backup_dir):
    expire_time = get_expire_time()
    for root, directories, files in os.walk(backup_dir):
        for file in files:
            if not file.startswith(backup_prefix):
                continue
            if not file.endswith(".zip"):
                continue
            file_path = os.sep.join([root, file])
            t = os.path.getctime(file_path)
            if t < expire_time:
                os.remove(file_path)

def parse_yaml():
    f = open('./config.yml', 'r')
    ystr = f.read()
    y = yaml.load(ystr, Loader=yaml.FullLoader)
    host_config = next((item for item in y['hosts'] if item.get('ip') == get_host_ip()), None)
    if host_config:
        host_config['storage_config'] = y['storage'][host_config['storage']]
    return host_config

if __name__ == "__main__":
    config = parse_yaml()
    if config['storage'] == "s3":
        storage_config = config['storage_config']
        s3.ACCESS_KEY = storage_config['access_id']
        s3.SECRET_KEY = storage_config['access_secret']
        s3.REGION_NAME = storage_config['region_name']
        s3.BUCKET_NAME = storage_config['bucket_name']
        s3.ENDPOINT = storage_config['endpoint']
    try:
        backup(config)
    finally:
        clean(config['backup_dir'])
