import os
import io
import boto3
import base64
from botocore.exceptions import NoCredentialsError
from botocore.config import Config
from boto3 import session
from typing import Optional, Tuple
from boto3.s3.transfer import TransferConfig
import multiprocessing
from tqdm import tqdm

ACCESS_KEY = None
SECRET_KEY = None
REGION_NAME = None
BUCKET_NAME = None
ENDPOINT = None

# --------------------------- S3 Bucket Connection --------------------------- #
def get_boto_client(
    bucket_creds: Optional[dict] = None) -> Tuple[boto3.client, TransferConfig]: # pragma: no cover
    '''
    Returns a boto3 client and transfer config for the bucket.
    '''
    bucket_session = session.Session()

    boto_config = Config(
        signature_version='s3v4',
        retries={
            'max_attempts': 3,
            'mode': 'standard'
        }
    )

    transfer_config = TransferConfig(
        multipart_threshold=1024 * 1024 * 10, # 10 MiB
        max_concurrency=multiprocessing.cpu_count(),
        multipart_chunksize=1024 * 1024 * 10,
        use_threads=True
    )

    if bucket_creds:
        region_name = bucket_creds['region_name']
        access_key_id = bucket_creds['access_id']
        secret_access_key = bucket_creds['access_secret']
    else:
        region_name = os.environ.get('REGION_NAME', REGION_NAME)
        access_key_id = os.environ.get('BUCKET_ACCESS_KEY_ID', ACCESS_KEY)
        secret_access_key = os.environ.get('BUCKET_SECRET_ACCESS_KEY',SECRET_KEY)

    if region_name and access_key_id and secret_access_key:
        boto_client = bucket_session.client(
            's3',
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region_name,
            config=boto_config
        )
    else:
        boto_client = None

    return boto_client, transfer_config

def upload_to_s3(local_file_path, s3_file_path):
    s3, transfer_config = get_boto_client()

    file_size = os.path.getsize(local_file_path)

    try:
        # 分块上传
        with tqdm(total=file_size, unit='B', unit_scale=True, desc=s3_file_path) as progress_bar:
            upload_file_args = {
                "Filename": local_file_path,
                "Bucket": BUCKET_NAME,
                "Key": s3_file_path,
                "Config": transfer_config,
                "Callback": progress_bar.update
            }

            s3.upload_file(**upload_file_args)

        print(f'{local_file_path} 上传成功到 {BUCKET_NAME}/{s3_file_path}')
        return get_presigned_url(s3, s3_file_path)
    except FileNotFoundError:
        print(f'{local_file_path} 不存在')
        return False
    except NoCredentialsError:
        print('AWS 认证信息不正确或缺失')
        return False
    except Exception as ex:
        print("出现如下异常%s"%ex)

def upload_obj_to_s3(file_data, s3_file_path) -> str:
    s3, transfer_config = get_boto_client()
    file_size = len(file_data)
    try:
        with tqdm(total=file_size, unit='B', unit_scale=True, desc=s3_file_path) as progress_bar:
            s3.upload_fileobj(
                    io.BytesIO(file_data), BUCKET_NAME, s3_file_path,
                    Config=transfer_config,
                    Callback=progress_bar.update)

        print(f'上传成功到 {BUCKET_NAME}/{s3_file_path}')
        return get_presigned_url(s3, s3_file_path)
    except NoCredentialsError:
        print('AWS 认证信息不正确或缺失')
        return None
    except Exception as ex:
        print("出现如下异常%s"%ex)
        return None

def download_s3_file(s3_file_path, local_file_path):
    s3, transfer_config = get_boto_client()

    try:
        # 获取文件大小
        response = s3.head_object(Bucket=BUCKET_NAME, Key=s3_file_path)
        file_size = response['ContentLength']

        with tqdm(total=file_size, unit='B', unit_scale=True, desc=s3_file_path) as progress_bar:
            s3.download_file(BUCKET_NAME, s3_file_path, local_file_path, Callback=progress_bar.update, Config=transfer_config)

        print(f'{BUCKET_NAME}/{s3_file_path} 下载成功到 {local_file_path}')
        return True
    except FileNotFoundError:
        print(f'{BUCKET_NAME}/{s3_file_path} 不存在')
        return False
    except NoCredentialsError:
        print('AWS 认证信息不正确或缺失')
        return False
    except Exception as ex:
        print("出现如下异常%s"%ex)
        return False

def download_s3_object(s3_file_path):
    # 初始化 S3 客户端
    s3, transfer_config = get_boto_client()
    try:
        # 创建一个 BytesIO 对象用于保存下载的文件内容
        content = io.BytesIO()
        # 获取文件大小
        response = s3.head_object(Bucket=BUCKET_NAME, Key=s3_file_path)
        file_size = response['ContentLength']
        # 开始下载文件
        with tqdm(total=file_size, unit='B', unit_scale=True, desc=s3_file_path) as progress_bar:
            s3.download_fileobj(BUCKET_NAME, s3_file_path, content, Callback=progress_bar.update, Config=transfer_config)
        # 重置 BytesIO 对象的指针位置
        content.seek(0)
        # 将内容转换为 base64
        return base64.b64encode(content.read()).decode('utf-8')
    except FileNotFoundError:
        print(f'{BUCKET_NAME}/{s3_file_path} 不存在')
        return None
    except NoCredentialsError:
        print('AWS 认证信息不正确或缺失')
        return None
    except Exception as ex:
        print("出现如下异常%s"%ex)
        return None

def get_presigned_url(s3, s3_file_path) -> str:
    presigned_url = s3.generate_presigned_url(
        'get_object',
        Params={
            'Bucket': BUCKET_NAME,
            'Key': s3_file_path,
        }, ExpiresIn=86400)
    return presigned_url
