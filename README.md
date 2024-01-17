# Mysql 容器数据备份

可以方便的备份 mysql 的数据，更好的保障数据安全，方便还原。可以配置多个服务器。并且可以打包成`zip`, 为了节约空间可以设置过期时间，方便在服务器上只存储一定时间内的备份文件。且可以上传到`S3`，后续考虑支持上传到其他存储平台如阿里云的`OSS`等。

## 配置示例

```yaml
storage:
    s3:
        access_id: XXXX2XXXX3X772XXX5OX
        access_secret: 'XX+X4xX1+xxx0xxXXxxxX8xXxxxXxxXxxXxXxx3X'
        region_name: 'us-west-2'
        bucket_name: 'bucket'
        endpoint: 'https://bucket.s3.us-west-2.amazonaws.com/'

hosts:
    - ip: 139.162.10.11
      name: 测试机
      backup_dir: /root/mysql_backup
      container_name: mysqldb-1
      expire_hour: 5
      storage: s3
      db:
          db_user: root
          db_password: 1234567
          databases:
              - db1
              - db2
              - drone_ci
    - ip: 139.162.10.13
      name: product
      backup_dir: /root/mysql/backup # 备份到服务器的目录
      container_name: mysqldb
      expire_hour: 5 # 过期时间
      storage: s3 # 选择远程备份的应用，目前只支持S3, 以后可能支持OSS等
      db:
          db_user: root
          db_password: Root1234
          databases:
              - fitness
              - shop
```
