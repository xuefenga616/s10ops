#coding:utf-8
__author__ = 'Administrator'

import global_settings
import json
import paramiko
from BrightEye import settings
import django   #脚本导入django方法
django.setup()
from web import models
from django.db import connection
import sys,time,os
import multiprocessing

def cmd_exec(task_id,bind_host_id,user_id,cmd):
    bind_host = models.BindHosts.objects.get(id=bind_host_id)
    s = paramiko.SSHClient()
    s.load_system_host_keys()
    s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        if bind_host.host_user.auth_method == 'ssh-password':
            s.connect(bind_host.host.ip_addr,
                      int(bind_host.host.port),
                      bind_host.host_user.username,
                      bind_host.host_user.password,
                      timeout=5)
        else:#rsa_key

            key = paramiko.RSAKey.from_private_key_file(settings.RSA_PRIVATE_KEY_FILE)
            s.connect(bind_host.host.ip_addr,
                      int(bind_host.host.port),
                      bind_host.host_user.username,
                      pkey=key,
                      timeout=5)
        stdin,stdout,stderr = s.exec_command(cmd)
        result = stdout.read(),stderr.read()
        if any(result):
            cmd_result = filter(lambda x:len(x)>0,result)[0]
        else:
            cmd_result = 'execution has no output!'
        #print cmd_result
        res_status = 'success'
        s.close()
    except Exception,e:
        cmd_result = e
        res_status = 'failed'
    #修改数据库中已有任务状态
    log_obj = models.TaskLogDetail.objects.get(child_of_task_id=int(task_id),bind_host_id=bind_host.id)
    log_obj.event_log = cmd_result
    log_obj.result = res_status
    log_obj.save()

def file_tranfer_exec(task_id,bind_host_id,user_id,content ):
    pass

if __name__ == '__main__':
    require_args = ['-task_type','-task_id','-expire','-uid']
    lack_args = [arg for arg in require_args  if arg not in sys.argv[1:]]   #lack_args：缺少的必须参数
    if len(lack_args) > 0:
        sys.exit("lack args of: %s" %lack_args)

    task_type = sys.argv[sys.argv.index('-task_type')+1]    #表示'-task_type'后一个
    if task_type =='cmd':
        require_args= ['-task',]
    elif task_type == 'file_send':
        require_args = ['-local','-remote']
    elif task_type == 'file_get':
        require_args = ['-remote',]

    lack_args = [arg for arg in require_args if arg not in sys.argv[1:]]
    if len(lack_args) >0:
        sys.exit("lack args of: %s"% lack_args)

    task_id = sys.argv[sys.argv.index('-task_id')+1]
    expire_time = sys.argv[sys.argv.index('-expire')+1]

    if task_type == 'cmd':
        content = sys.argv[sys.argv.index('-task')+1]
    else:
        content = sys.argv
    uid = sys.argv[sys.argv.index('-uid')+1]

    task_obj = models.TaskLog.objects.get(id=int(task_id))
    connection.close()  #关闭数据库

    Pool = multiprocessing.Pool(processes=settings.MaxTaskProcesses) #进程池
    res_list = []

    if task_type == 'cmd':
        task_func = cmd_exec
    elif task_type == 'file_send' or task_type == 'file_get':
        task_func = file_tranfer_exec
    else:
        sys.exit('wrong task_type!')

    for h in task_obj.hosts.select_related():
        p = Pool.apply_async(task_func,args=(task_id,h.id,uid,content))
        res_list.append(p)

    Pool.close()
    Pool.join()