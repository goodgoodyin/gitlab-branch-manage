#coding: utf-8

import requests
import pprint
import yaml
import os
import sys
import time
import datetime

pp = pprint.PrettyPrinter(indent=2)

name_id_map = {}

def initConfig():

    head, tail = os.path.split(os.path.realpath(__file__))
    yaml_path = os.path.join(head, "config.yaml")

    f = open(yaml_path, 'r')
    file_data = f.read()
    f.close()

    data = yaml.load(file_data, Loader=yaml.SafeLoader)

    initBranchPipeLine(data)

    initGitlab(data)

# 初始化 gitlab 相关
def initGitlab(data):
    global private_gitlab__token
    global gitlab_url
    global headers

    private_gitlab__token = data['private_token']
    gitlab_url = data['gitlab_url']

    headers = {'PRIVATE-TOKEN': private_gitlab__token}

# 初始化 代码分支流水线相关
def initBranchPipeLine(data):
    global project_branch_dict
    project_branch_dict = {}

    config_list = data['config']
    for config in config_list:

        if not config.__contains__("name"):
            print("Invalid config, name is required")
            exit(0)

        name = config['name']
        if project_branch_dict.__contains__(name):
            print("Invalid config, name [{}] is duplicate".format(name))
            exit(0)

        if not config.__contains__("project_name"):
            print("Invalid config, [{}] project_name is required".format(name))
            exit(0)

        project_name = config['project_name']

        pipeline = config['pipeline']

        # 是一个二元数组列表
        # print(name)
        pipe_list = analysis(pipeline)

        temp_dict = {}
        temp_dict["project_name"] = project_name
        temp_dict["pipeline"] = pipe_list

        # key 是 project name, value 是dict， 有两个key，分别是项目名称和流水线
        # print(name)
        project_branch_dict[name] = temp_dict

# 分析 项目的合并配置
def analysis(pipeline):
    pipe_list = []

    for src, dst in pipeline.items():
        # 数组
        # print(dst)

        for a in dst:
            if isinstance(a, dict):
                append(pipe_list, src, a)
            elif isinstance(a, str):
                pipe_list.append((src, a))

    # 打印 pipeline
    # pp.pprint(pipe_list)
    return pipe_list

# 是一个递归函数，递归分析
def append(pipe_list, src_branch, branch_dict):
    for key, value in branch_dict.items():

        # value 是数组
        # src --> key  可以组成一个组合
        pipe_list.append((src_branch, key))

        for a in value:
            if isinstance(a, dict):
                append(pipe_list, key, a)
            elif isinstance(a, str):
                pipe_list.append((key, a))

def initProjectId():

    i = 0;
    while True:
        ## gitlab api规定 per_page最大值为100
        temp_url = "{}{}{}".format(gitlab_url, "/projects?simple=true&membership=true&per_page=100&order_by=id&sort=asc&id_after=", i)
        r = requests.get(temp_url, headers=headers)

        res = r.json()
        length = len(res)
        if length == 0:
            break;

        i = res[length - 1]['id'];

        for data in r.json():
            project_owner = data['namespace']['path']
            if project_owner == "xxx" or project_owner == "xxx":

                name = data['name']
                p_id = data['id']
                name_id_map[name] = p_id

    # pp.pprint(r.json())

def init():
    initConfig()

    initProjectId()

# 创建分支
def createBranch(project_name, src_name, dst_name):
    p_id = name_id_map.get(project_name, "000")
    if "000" == p_id:
        print("error! do not konw id of project {}".format(project_name))
        return

    current_url = "/projects/{}/repository/branches".format(p_id)
    temp_url = "{}{}?branch_name={}&ref={}".format(gitlab_url, current_url, dst_name, src_name)
    r = requests.post(temp_url, headers=headers)
    if 200 != r.status_code:
        print("create error, project_name {}, src_name {}, dst_name{}".format(project_name, src_name, dst_name))

# 是否可以 merge
def canBeMerged(p_id, merge_request_iid):

    startTime = datetime.datetime.now()

    for i in range(200):
        resp = getMR(p_id, merge_request_iid)
        # print(resp)

        # gitlab MR 创建完成之后，merge_status 开始是 checking， 后面是 can_be_merged
        status = resp["merge_status"]
        if "checking" == resp["merge_status"]:
            # print("checking- {}, status {}".format(i, status))
            time.sleep(0.9)
            continue

        if "can_be_merged" == resp["merge_status"]:
            endTime = datetime.datetime.now()
            cost =  (endTime - startTime).microseconds / 1000 
            #print("checking count- {}, status {}, cost {} ms".format(i, status, cost  ))
            
            return True, cost

    return False,0

def getMRChanges(p_id, merge_request_iid):
    current_url = "/projects/{}/merge_requests/{}/changes".format(p_id, merge_request_iid)
    temp_url = "{}{}".format(gitlab_url, current_url)

    r = requests.get(temp_url, headers=headers)
    resp = r.json()

    # print(resp['changes'])

def createMR(project_name, src_name, dst_name, auto_merge=False):
    p_id = name_id_map.get(project_name, "000")
    if "000" == p_id:
        print("error! do not konw id of project {}".format(project_name))
        return

    # 关闭
    #closeAllOpenMR(project_name, p_id)

    current_url = "/projects/{}/merge_requests".format(p_id)
    temp_url = "{}{}".format(gitlab_url, current_url)

    data = {
        'id': p_id,
        'source_branch': src_name,
        'target_branch': dst_name,
        'title': "auto merge {} -> {}".format(src_name, dst_name)
    }

    r = requests.post(temp_url, headers=headers, data = data)
    if r.status_code >= 300:
        print("create MR error, project_name {}, src_name {}, dst_name {}".format(project_name, src_name, dst_name))
        print(r.status_code)
        print(r.text)
        return False
    
    resp = r.json()
    # print(resp)

    has_conflicts = resp['has_conflicts']
    if True == has_conflicts:
        # 有冲突
        print("create MR error, has_conflicts, project_name {}, src_name {}, dst_name {}".format(project_name, src_name, dst_name))
        exit(1)


    merge_request_id = resp['id']
    iid = resp['iid']

    getMRChanges(p_id, iid)

    if True == auto_merge:
        #print("checking MR, project_name {}, pid {}, src_name {}, dst_name {}".format(project_name, p_id, src_name, dst_name))

        can, cost = canBeMerged(p_id, iid)
        if can:
            accept_result =  acceptMR(project_name, iid)

            # 打印日志
            print("[{}, {} -> {}] create MR success, and accept MR {},  merge_request_id {}, cost {} ms".format(project_name, src_name, dst_name, \
                "success" if accept_result else "fail", merge_request_id, cost))

            return accept_result
    else:
        # 打印日志
        print("[{}, {} -> {}] create MR success,  merge_request_id {}".format(project_name, src_name, dst_name, merge_request_id))
    
    return True

def getMR(p_id, merge_request_iid):
    # GET /projects/:id/merge_requests/:merge_request_iid
    current_url = "/projects/{}/merge_requests/{}".format(p_id, merge_request_iid)
    temp_url2 = "{}{}".format(gitlab_url, current_url)
    r = requests.get(temp_url2, headers=headers)

    #print(r.status_code)
    #print(r.text)

    return r.json()

# 关闭所有的 已打开的 MR
def closeAllOpenMR(project_name, p_id):
    pass

    getMR(p_id, "88446")

    # GET /projects/:id/merge_requests?state=opened
    current_url2 = "/projects/{}/merge_requests".format(p_id)
    temp_url2 = "{}{}?state=opened".format(gitlab_url, current_url2)
    r = requests.get(temp_url2, headers=headers)

    datas = r.json()

    for item in datas:
        merge_request_iid = item['iid']
        closeMR(project_name, p_id, merge_request_iid)

    # print(r.status_code)
    # print(r.text)
   
def closeMR(project_name, p_id, merge_request_iid):
    current_url = "/projects/{}/merge_requests/{}".format(p_id, merge_request_iid)
    temp_url = "{}{}".format(gitlab_url, current_url)
    r = requests.delete(temp_url, headers=headers)
    print(r.status_code)
    print(r.text)

def acceptMR(project_name, merge_request_id):
    p_id = name_id_map.get(project_name, "000")
    if "000" == p_id:
        print("error! do not konw id of project {}".format(project_name))
        return False

    current_url = "/projects/{}/merge_requests/{}/merge".format(p_id, merge_request_id)
    temp_url = "{}{}".format(gitlab_url, current_url)
    r = requests.put(temp_url, headers=headers)

    if 404 == r.status_code:
        print("acceptMR error, not found! project_name {}, merge_request_id {}".format(project_name, merge_request_id))
        return False

    if 405 == r.status_code:
        print("acceptMR error, please wait, status not can_be_merged ! project_name {}, merge_request_id {}".format(project_name, merge_request_id))
        return False

    if 406 == r.status_code:
        print("acceptMR error, have conflicts! project_name {}, merge_request_id {}".format(project_name, merge_request_id))
        return False

    if 406 == r.status_code:
        print("acceptMR error, merge request is already merged or closed! project_name {}, merge_request_id {}".format(project_name, merge_request_id))
        return False

    if 409 == r.status_code:
        print("acceptMR error, SHA does not match HEAD of source branch! project_name {}, merge_request_id {}".format(project_name, merge_request_id))
        return False

    if 401 == r.status_code:
        print("acceptMR error,  don't have permissions to accept this merge request! project_name {}, merge_request_id {}".format(project_name, merge_request_id))
        return False

    if 200 == r.status_code:
        #print("acceptMR success, project_name {}, merge_request_id {}".format(project_name, merge_request_id))
        return True

    return True

def autoMerge2(config_name):

    config = project_branch_dict.get(config_name, None)
    if config is None:
        print("error! project [{}] do not exist in config.yaml".format(config_name))
        return

    project_name = config["project_name"]
    pipeline = config["pipeline"]

    for item in pipeline:
        src_name = item[0]
        dst_name = item[1]
        result = createMR(project_name, src_name, dst_name, True)
        if not result:
            return

def printUsage():
    print("you missing config name in cmd")
    print("demo: python auto_gitlab.py hello")

def start():
    if len(sys.argv) < 2:
        printUsage()
        return

    config_name = sys.argv[1]
    #config_name = "huidu"

    # 初始化项目
    init()
    
    autoMerge2(config_name) 

# 开始
start()
