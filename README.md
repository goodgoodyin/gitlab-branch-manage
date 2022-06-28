git仓库分支管理
------

[TOC]

## 模块介绍
|module|desc|
|-|-|
|日常合并|每日hotfix|
|版本发布|灰度发布和上线发布|

## useage
### 日常合并

生产hotfix
```
python ./日常合并/daily.py prod
```

流程如下
#### 生产修复
```mermaid
sequenceDiagram
    participant local
    participant dev
    participant prod
    participant pre
    
    local ->> dev: hotfix-9.18.1合并到develop验证
    dev -->> local: 验证OK
    local ->> prod: hotfix-9.18.1合并到hotfix-9.18.1
    local ->> pre: hotfix-9.19.1


```

合代码过程
```mermaid
graph LR;

    hotfix-9.18.1 --> product;
    hotfix-9.18.1 --> hotfix-9.19.1 --> master;
    hotfix-9.19.1 --> branch_9.20 --> develop;


```


### 版本发布

#### 灰度发布

#### 上线发布