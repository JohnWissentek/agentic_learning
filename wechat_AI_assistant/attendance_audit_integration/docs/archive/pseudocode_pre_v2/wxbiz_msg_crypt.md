# wxbiz_msg_crypt.py 伪代码

## 本文件职责（一句话）
封装企业微信回调事件推送的解密与签名校验算法，包含 PKCS7 去填充和 AES-256-CBC 对称解密处理。

## 对应PRD功能
Webhook 回调数据解密、合法可信域名配置认证校验。

## 依赖
- 调用：pycryptodome (Crypto.Cipher.AES), struct, hashlib, base64, xmltodict
- 被调用：main.py (FastAPI Webhook 处理器接口)

## 伪代码
```python
类 PKCS7Padding:
    静态函数 unpad(字节数组):
        填充字节值 = 字节数组的最后一个字节的值
        如果 填充字节值 不在 [1, 32] 范围内:
            填充字节值 = 0
        返回 字节数组[0 到 长度 - 填充字节值] (如果有填充的话)

类 WXBizMsgCrypt:
    构造函数 (token, encoding_aes_key, receive_id):
        成员 token = token
        # 补全 Base64 尾部 "=" 并解码得到 32 字节的 AES Key
        成员 aes_key = Base64解码(encoding_aes_key + "=")
        成员 receive_id = receive_id (即企业微信的 CorpID)
        如果 aes_key 长度不等于 32:
            抛出值错误异常 "EncodingAESKey 长度必须为 43 个字符"

    私有函数 _get_sha1_signature(时间戳, 随机数, 加密消息主体) -> 字符串:
        # 对 token, 时间戳, 随机数, 加密消息主体 进行排序并拼接
        待签名数组 = 排序后的列表 [token, 时间戳, 随机数, 加密消息主体]
        拼接字符串 = 拼接(待签名数组)
        计算拼接字符串的 SHA1 哈希值并转为 16 进制字符串返回

    函数 verify_url(消息签名, 时间戳, 随机数, 加密回显字符串) -> 字符串:
        计算签名 = 调用 _get_sha1_signature(时间戳, 随机数, 加密回显字符串)
        如果 计算签名 != 消息签名:
            抛出异常 "MsgSignature 签名校验失败"
        
        # 解密回显字符串
        解密明文 = 调用 decrypt(加密回显字符串)
        返回 解密明文

    函数 decrypt_xml_msg(消息签名, 时间戳, 随机数, 原始推送XML数据) -> 字符串:
        解析 原始推送XML数据 获得 dict 对象
        加密体 = 从字典中获取 xml["Encrypt"]
        
        计算签名 = 调用 _get_sha1_signature(时间戳, 随机数, 加密体)
        如果 计算签名 != 消息签名:
            抛出异常 "XML 消息签名校验失败"
            
        解密明文 = 调用 decrypt(加密体)
        返回 解密明文

    函数 decrypt(加密明文 Base64 字符串) -> 字符串:
        密文字节数组 = Base64解码(加密明文 Base64 字符串)
        # 初始化 IV，使用 aes_key 的前 16 个字节作为 CBC 的 IV
        解密器 = 实例化 AES(密钥=aes_key, 模式=CBC, 初始向量=aes_key[:16])
        解密后的明文字节数组 = 解密器.解密(密文字节数组)
        去填充字节数组 = PKCS7Padding.unpad(解密后的明文字节数组)
        
        # 明文协议结构：random(16B) + msg_len(4B, 网络字节序) + msg + receive_id (CorpID)
        消息长度 = 从 去填充字节数组[16:20] 用大端序大整数反序列化 (struct.unpack("!I"))
        消息正文 = 去填充字节数组[20 : 20 + 消息长度] 的 UTF-8 编码字符串
        接收者ID = 去填充字节数组[20 + 消息长度 : ] 的 UTF-8 编码字符串
        
        如果 接收者ID != 成员 receive_id:
            抛出异常 "解密出的 CorpID 与本地配置不符"
            
        返回 消息正文
```

## 注意事项 / 坑
- `EncodingAESKey` 的长度是固定 43 位的 base64 字符串，解码出来正好是 32 字节（256 位密钥）。
- 解密后的数据包结构含有 16 字节随机字符串和末尾的 CorpID 校验，必须进行防篡改提取判断。
