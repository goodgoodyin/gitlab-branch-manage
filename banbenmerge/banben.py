#coding:utf-8

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
    yaml_path = os.path.join(head, "config_branch.yaml")

    f = open(yaml_path, 'r')
    file_data = f.read()
    f.close()

    data = yaml.load(file_data, Loader=yaml.SafeLoader)

    # 初始化 gitlab 鉴权 相关
    initGitlab(data)
    
    # 初始化项目列表
    initProjectName(data)

    # 初始化 代码分支流水线相关
    initBranchPipeLine(data)

# 初始化 代码分支流水线相关
def initBranchPipeLine(data):
    global project_branch_dict
    project_branch_dict = {}

    config_list = data['config']
    for config in config_list:

        if not config.__contains__("name"):
            print("Invalid config, [{}] is required".format("name"))
            exit(0)

        global diedai_name
        if config.__contains__("diedai"):
            diedai_name = config['diedai']

        name = config['name']
        if project_branch_dict.__contains__(name):
            print("Invalid config, name [{}] is duplicate".format(name))
            exit(0)

        if not config.__contains__("action"):
            print("Invalid config, [{}] action is required".format(name))
            exit(0)

        action = config['action']

        if "default" == action:
            if not config.__contains__("default"):
                print("Invalid config, [{}] default is required".format(name))
                exit(0)

            default_name = config['default']
            temp_dict = {}
            temp_dict["action"] = action
            temp_dict["default"] = default_name

            # 这个场景不用分析流水线
            project_branch_dict[name] = temp_dict
            return

        pipeline = config['pipeline']

        # 是一个二元数组列表
        # print(name)
        pipe_list = analysis(pipeline)

        temp_dict = {}
        temp_dict["action"] = action
        temp_dict["pipeline"] = pipe_list
        temp_dict["title"] = config.get("title", '')
        temp_dict["branches"] = config.get("branches", [])
        temp_dict["default"] = config.get("default", '')

        # key 是 project name, value 是dict， 有两个key，分别是动作和流水线
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

# 初始化 gitlab 相关
def initGitlab(data):
    global private_gitlab__token
    global gitlab_url
    global headers

    private_gitlab__token = data['private_token']
    gitlab_url = data['gitlab_url']

    headers = {'PRIVATE-TOKEN': private_gitlab__token}


# 初始化项目列表
def initProjectName(data):
    global project_names

    project_names = data['project']

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

def init():
    initConfig()
    
    initProjectId()

def setDefaultBranch(config):
    # 分支名
    default_name = config["default"]

    temp_dict = {}

    # 遍历项目名
    for project_name in project_names:
        result = setDefaultBranchImpl(project_name, default_name)
        temp_dict[project_name] = result

    pp.pprint(temp_dict)

def setDefaultBranchImpl(project_name, default_name):
    # PUT /projects/:id
    # 项目id
    p_id = name_id_map.get(project_name, "000")

    current_url = "/projects/{}".format(p_id)
    temp_url = "{}{}".format(gitlab_url, current_url)

    data = {
        'id': p_id,
        'name': project_name,
        'default_branch': default_name
    }

    r = requests.put(temp_url, headers=headers, data = data)
    if r.status_code >= 300:
        print("error, setDefaultBranch {}, code {}".format(project_name, r.status_code))
        print(r.text)
        return False
    else:
        print("success, setDefaultBranch {} to {}".format(project_name, default_name))
        return True

# 检查是否有变化，出错-1，没有0， 有大于0
def checkMR(p_id, iid):
    current_url = "/projects/{}/merge_requests/{}/commits".format(p_id, iid)
    temp_url = "{}{}".format(gitlab_url, current_url)

    r = requests.get(temp_url, headers=headers)
    if r.status_code >= 300:
        print("check MR commits error, code {}".format(r.status_code))
        print(r.status_code)
        print(r.text)
        return -1

    commit_number = len(r.json())
    if 0 == commit_number:
        return 0

    current_url = "/projects/{}/merge_requests/{}/changes".format(p_id, iid)
    temp_url = "{}{}".format(gitlab_url, current_url)

    r = requests.get(temp_url, headers=headers)
    if r.status_code >= 300:
        print("check MR changes error, code {}".format(r.status_code))
        print(r.status_code)
        print(r.text)
        return -1

    return 1

def closeMR(project_name, iid):
    p_id = name_id_map.get(project_name, "000")

    current_url = "/projects/{}/merge_requests/{}".format(p_id, iid)
    temp_url = "{}{}".format(gitlab_url, current_url)
    r = requests.delete(temp_url, headers=headers)

    if r.status_code >= 300:
        print("close MR error, project {}, code {}".format(project_name, r.status_code))
        print(r.status_code)
        print(r.text)
        return -1

def findOpenMR(p_id, src_name, dst_name):

    # /projects/:id/merge_requests?state=opened

    current_url = "/projects/{}/merge_requests".format(p_id)
    temp_url = "{}{}?state=opened".format(gitlab_url, current_url)

    r = requests.get(temp_url, headers=headers)
    rsp = r.json()
    for item in rsp:
        # if item["title"].startswith(name_prefix):
        if item['source_branch'] == src_name and item['target_branch'] == dst_name :
            return item
    return None

def getMR(p_id, merge_request_iid):
    # GET /projects/:id/merge_requests/:merge_request_iid
    current_url = "/projects/{}/merge_requests/{}".format(p_id, merge_request_iid)
    temp_url2 = "{}{}".format(gitlab_url, current_url)
    r = requests.get(temp_url2, headers=headers)

    return r.json()

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

def createMR(project_name, src_name, dst_name, title):
    p_id = name_id_map.get(project_name, "000")
    if "000" == p_id:
        print("error! do not konw id of project {}".format(project_name))
        return

    current_url = "/projects/{}/merge_requests".format(p_id)
    temp_url = "{}{}?branch_name={}&ref={}".format(gitlab_url, current_url, dst_name, src_name)

    temp_title = ""
    if "" != title:
        temp_title = title
    else:
        temp_title = "auto merge {} -> {}".format(src_name, dst_name)

    data = {
        'id': p_id,
        'source_branch': src_name,
        'target_branch': dst_name,
        'title': temp_title
    }

    r = requests.post(temp_url, headers=headers, data = data)

    iid = ""
    merge_request_id = ""

    if r.status_code == 409:
        # 已存在
        if -1 != r.text.find("already exists"):

            # 去找到
            item = findOpenMR(p_id, src_name, dst_name)
            merge_request_id = item['id']
            iid = item['iid']

            if item is None:
                print("{} MR error".format(project_name))
                return
            pass

    # elif r.status_code >= 300:
    #     print("create MR error, project_name {}, src_name {}, dst_name {}".format(project_name, src_name, dst_name))
    #     print(r.status_code)
    #     print(r.text)
    #     return False
    else:
        rsp = r.json()
        merge_request_id = rsp.get('id', '')
        iid = rsp['iid']
   

    changes = checkMR(p_id, iid)
    
    if -1 == changes:
        print(" {} get change error, skip".format(project_name))
        return False
    elif 0 == changes:
        closeMR(project_name, iid)
        print("{}  no change, skip".format(project_name) )
        return False
    else:

        can, cost = canBeMerged(p_id, iid)
        if can:
            accept_result =  acceptMR(project_name, iid)

            # 打印日志
            print("[{}, {} -> {}] create MR success, and accept MR {},  merge_request_id {}, cost {} ms".format(project_name, src_name, dst_name, \
                "success" if accept_result else "fail", merge_request_id, cost))

            return accept_result
        else:
            print("[{}, {} -> {} ] MR fail, maybe conflict"  .format(project_name, src_name, dst_name))
            return True

    return True
   
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

def protectBranch(p_id, name):
    current_url = "/projects/{}/protected_branches?name={}&merge_access_level=30".format(p_id, name)
    temp_url = "{}{}".format(gitlab_url, current_url)

    r = requests.post(temp_url, headers=headers)

    if r.status_code >= 300:
        print("protectBranch error, pid {}, name {}, r.status_code {} r.text{}".format(p_id, name, r.status_code, r.text))

def setDefaultBranch2(p_id, name):
    # 设置默认分支
    current_url = "/projects/{}".format(p_id)
    temp_url = "{}{}".format(gitlab_url, current_url)

    data = {
        'default_branch': name
    }

    r = requests.put(temp_url, headers=headers, data = data)
    # print(r.json())

def autoMerge2(config):

    pipeline = config["pipeline"]
    title = config.get("title", "")

    changeProjectList = []

    for item in pipeline:
        src_name = item[0]
        dst_name = item[1]

        for project_name in project_names:
            print("now doaction for {}".format(project_name))
            result = createMR(project_name, src_name, dst_name, title)
            # if not result:
            #     return
            if result and project_name not in changeProjectList:
                changeProjectList.append(project_name);
    
    print
    print("merge has change project list: ")
    for project_name in changeProjectList:
        print(project_name)





def unprotectBranch(p_id, name):
    current_url = "/projects/{}/protected_branches/{}".format(p_id, name)
    temp_url = "{}{}".format(gitlab_url, current_url)

    # print(temp_url)
    r = requests.delete(temp_url, headers=headers)

    # if r.status_code >= 300:
    #     print("unprotectBranch error, pid {}, name {}, r.status_code {} r.text{}".format(p_id, name, r.status_code, r.text))


def unprotectAllBranch(p_id):
    current_url = "/projects/{}/protected_branches".format(p_id)
    temp_url = "{}{}".format(gitlab_url, current_url)

    # print(temp_url)
    r = requests.get(temp_url, headers=headers)
    # print(r.text)

    for item in r.json():
        name = item['name']
        # print(name)
        unprotectBranch(p_id, name)

    # exit(0)

def delBranch(p_id, name):
    # DELETE /projects/:id/repository/branches/:branch

    current_url = "/projects/{}/repository/branches/{}".format(p_id, name)
    temp_url = "{}{}".format(gitlab_url, current_url)

    # print(temp_url)
    r = requests.delete(temp_url, headers=headers)

    # if r.status_code >= 300:
    #     print("delBranch error, pid {}, name {}, r.status_code {} r.text{}".format(p_id, name, r.status_code, r.text))

"""
删除保护的分支
"""
def delProtectBranch(p_id, name):
    unprotectBranch(p_id, name)
    delBranch(p_id, name)

def createProjctBranch(config):
    pipeline = config["pipeline"]

    for project_name in project_names:

            # 解除 保护 + 删除 product develop
            p_id = name_id_map.get(project_name, "000")

            print(project_name)

            # unprotectAllBranch(p_id)

            # delBranch(p_id, "product")
            # delBranch(p_id, "develop")
            # delBranch(p_id, "hotfix-9.17.1")
            # delBranch(p_id, "hotfix-9.16.1")
            # delBranch(p_id, "branch_9.18")

    for item in pipeline:
        src_name = item[0]
        dst_name = item[1]

        for project_name in project_names:

            createBranch(project_name, src_name, dst_name)

# 创建分支
def createBranch(project_name, src_name, dst_name):
    p_id = name_id_map.get(project_name, "000")
    if "000" == p_id:
        print("error! do not konw id of project {}".format(project_name))
        return

    current_url = "/projects/{}/repository/branches".format(p_id)
    temp_url = "{}{}?branch={}&ref={}".format(gitlab_url, current_url, dst_name, src_name)
    # print(temp_url)

    r = requests.post(temp_url, headers=headers)
    if r.status_code >= 300:
        print("create error, project_name {}, src_name {}, dst_name {}, , r.status_code {} r.text{}".format(project_name, src_name, dst_name, r.status_code, r.text))

    else:
        print("create success, project_name {}, src_name {}, dst_name {}".format(project_name, src_name, dst_name))



    # for project_name in project_names:
    #     print("createProjctBranch, project_name {}".format(project_name))
    #     createBranch(project_name, src_branch, hotfix_branch)

def createProjctBranchV2(src_branch, dev_branch, hotfix_branch):
    for project_name in project_names:
        print("createProjctBranchV2, project_name {}".format(project_name))
        createBranch(project_name, src_branch, dev_branch)
        createBranch(project_name, src_branch, hotfix_branch)

def setProtectBranch(config):
    pass
    branches = config['branches']
    default = config['default']

    for project_name in project_names:
        print("now doaction for {}".format(project_name))

        p_id = name_id_map.get(project_name, "000")

        # 解除保护
        unprotectAllBranch(p_id)

        # 重新设置保护
        for name in branches:
            protectBranch(p_id, name)

        # 设置默认
        setDefaultBranch2(p_id, default)

        print("set Protect and default success, project_name {}, default_branch {}".format(project_name, default))


def printUsage():
    print("you missing config name in cmd")
    print("demo: python auto_gitlab_branch.py prod")

def start():
    if len(sys.argv) < 2:
        printUsage()
        return
    
    config_name = sys.argv[1]

    # 初始化项目
    init()
    
    config = project_branch_dict.get(config_name, None)
    if config is None:
        print("error! project [{}] do not exist in config_branch.yaml".format(config_name))
        return
    action = config["action"]
    if "merge" == action:
        autoMerge2(config)
    elif "create" == action:
        createProjctBranch(config)
    elif "default" == action:
        setDefaultBranch(config)
    elif "unprotect" == action:
        setDefaultBranch(config)
    elif "protect" == action:
        setProtectBranch(config)
    elif "createAndDefault" == action:
        createProjctBranch(config)
        setDefaultBranch(config)
    else:
        print("error! action [{}] invalid".format(action))
        return
    
# 开始
start()
