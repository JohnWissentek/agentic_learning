# wecom_api.py 伪代码

## 本文件职责（一句话）
封装企业微信 OpenAPI 的底层网络请求逻辑，提供访问凭证 Token 缓存与自动续期，并支持获取员工通讯录、打卡流水、审批单详情及日常工作汇报数据。

## 对应PRD功能
- 考勤打卡原始数据拉取（PRD §3.1）
- 审批单据内容获取（PRD §3.1）
- 员工通讯录同步与花名册导入（PRD §3.2）
- 出差工作日报状态获取（PRD §3.4）

## 依赖
- 调用：httpx, time, config.settings, logger
- 被调用：audit_engine.py

## 伪代码
```python
类 WeComAPIClient:
    构造函数 ():
        成员 corpid = settings.WECOM_CORPID
        成员 secret = settings.WECOM_SECRET
        成员 _access_token = None
        成员 _token_expires_at = 0 (时间戳)

    函数 get_access_token() -> 字符串:
        # 获取有效 Token (内存级高并发续期缓存算法)
        当前时间 = 当前系统时间戳
        如果 成员 _access_token 存在 且 当前时间 < 成员 _token_expires_at:
            返回 成员 _access_token

        # 发起 HTTP 请求向企业微信获取新 Token
        请求地址 = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
        请求参数 = {
            "corpid": 成员 corpid,
            "corpsecret": 成员 secret
        }
        
        尝试:
            响应 = HTTP_GET(请求地址, 请求参数, 超时=10秒)
            数据 = 响应.json()
            如果 数据["errcode"] == 0:
                成员 _access_token = 数据["access_token"]
                # 扣减 200 秒的缓冲提前量，防止临界失效错误
                成员 _token_expires_at = 当前时间 + float(数据["expires_in"]) - 200
                返回 成员 _access_token
            否则:
                抛出异常 "Token 获取失败: 数据中的 errmsg"
        捕获 异常:
            记日志 ERROR "获取 WeCom Access Token 发生网络或系统异常"
            重新抛出 异常

    函数 fetch_users(部门ID = 1) -> 列表:
        # 递归拉取该部门及子部门下的所有在岗员工列表
        凭证 = 调用 get_access_token()
        请求地址 = "https://qyapi.weixin.qq.com/cgi-bin/user/list"
        请求参数 = {
            "access_token": 凭证,
            "department_id": 部门ID,
            "fetch_child": 1
        }
        
        尝试:
            响应 = HTTP_GET(请求地址, 请求参数, 超时=15秒)
            数据 = 响应.json()
            如果 数据["errcode"] == 0:
                返回 数据["userlist"]
            否则:
                记日志 ERROR "拉取通讯录列表失败: errmsg"
                返回 空列表
        捕获 异常:
            记日志 ERROR "拉取通讯录失败，API网络错误"
            返回 空列表

    函数 fetch_punches(开始时间戳, 结束时间戳, 用户ID列表) -> 列表:
        # 批量获取员工的原始打卡数据
        凭证 = 调用 get_access_token()
        请求地址 = "https://qyapi.weixin.qq.com/cgi-bin/checkin/getcheckindata?access_token=凭证"
        请求体 = {
            "opencheckindatatype": 3,  # 3 代表获取全部打卡记录（包含上下卡与外勤卡）
            "starttime": 开始时间戳,
            "endtime": 结束时间戳,
            "useridlist": 用户ID列表
        }
        
        尝试:
            响应 = HTTP_POST(请求地址, json=请求体, 超时=15秒)
            数据 = 响应.json()
            如果 数据["errcode"] == 0:
                返回 数据["checkindata"]
            否则:
                记日志 ERROR "拉取打卡流水数据失败: errmsg"
                返回 空列表
        捕获 异常:
            记日志 ERROR "拉取打卡流水失败，API网络错误"
            返回 空列表

    函数 fetch_approval_detail(审批单号) -> 字典:
        # 拉取单个审批单详情 (主要用于获取请假时长、调休加班时长、出差时间范围等)
        凭证 = 调用 get_access_token()
        请求地址 = "https://qyapi.weixin.qq.com/cgi-bin/oa/getapprovaldetail?access_token=凭证"
        请求体 = {
            "sp_no": 审批单号
        }
        
        尝试:
            响应 = HTTP_POST(请求地址, json=请求体, 超时=15秒)
            数据 = 响应.json()
            如果 数据["errcode"] == 0:
                返回 数据["info"]
            否则:
                记日志 ERROR "获取审批单详情失败: errmsg"
                返回 空字典
        捕获 异常:
            记日志 ERROR "获取审批单详情失败，API网络错误"
            返回 空字典

    函数 fetch_daily_reports(开始时间戳, 结束时间戳) -> 列表:
        # 拉取出差人员在此期间提交的现场工作日志汇报 (日常汇报)
        凭证 = 调用 get_access_token()
        请求地址 = "https://qyapi.weixin.qq.com/cgi-bin/oa/getreportdata?access_token=凭证"
        请求体 = {
            "starttime": 开始时间戳,
            "endtime": 结束时间戳,
            "template_id": "C4NvrtgmDKznbXFJCKEw5XGNyrw6dhLquQuNkq8Zp"  # 公司日报模板固定ID
        }
        
        尝试:
            响应 = HTTP_POST(请求地址, json=请求体, 超时=15秒)
            数据 = 响应.json()
            如果 数据["errcode"] == 0:
                返回 数据["data"]["report_list"]
            否则:
                记日志 ERROR "拉取工作日志数据失败: errmsg"
                返回 空列表
        捕获 异常:
            记日志 ERROR "拉取工作日志失败，API网络错误"
            返回 空列表

# 实例化全局单例客户端
wecom_client = WeComAPIClient()
```

## 注意事项 / 坑
- 企业微信 Token 的有效期通常为 7200 秒（2 小时），频繁通过网络向企业微信请求 Token 会触发频率控制（Rate Limit）被封禁。因此，我们在 `get_access_token` 中实现了**内存级自过期缓存**。缓存到期前绝对不发网络请求。
- 每次获取 Token 时，我们特意设置了 `200` 秒的提前释放时间（`expires_in - 200`），这是为了防止在大吞吐请求过程中，Token 刚好由于物理时差在网络传输中途突然过期，导致下一轮 API 交互直接报错。
