# wxbiz_msg_crypt.py 伪代码

## 本文件职责（一句话）
实现企微回调消息的 SHA1 验签与 AES-256-CBC 解密（含 PKCS7 去填充与 CorpID 校验）。

## 对应PRD功能
Webhook 安全通道（支撑审批实时入库，服务 F1/F14）；ARCHITECTURE §9「Webhook 验签快速失败」

## 依赖
- 调用：标准库 base64/hashlib/struct；Crypto.Cipher.AES；decrypt_xml_msg 内用 xmltodict
- 被调用：main.py（构造 WXBizMsgCrypt，验 URL / 解密 POST）

## 伪代码

类 PKCS7Padding:
    静态方法 unpad(data):
        取末字节为 pad 长；非法则当 0；截去填充

类 WXBizMsgCrypt:
    初始化(token, encoding_aes_key, receive_id):
        key = base64 解码(aes_key + "=")
        若 key 长度 ≠ 32: 抛 ValueError

    函数 _get_sha1_signature(timestamp, nonce, encrypt_msg):
        对 [token, timestamp, nonce, encrypt_msg] 排序拼接后 SHA1
        返回 hex 摘要

    函数 verify_url(msg_signature, timestamp, nonce, echostr):
        验签失败 → ValueError
        返回 decrypt(echostr) 明文（给企微配置回显）

    函数 decrypt_xml_msg(msg_signature, timestamp, nonce, post_data):
        解析 XML 取 Encrypt 字段
        验签失败 → ValueError
        返回 decrypt(Encrypt)

    函数 decrypt(encrypt_msg):
        Base64 解码 → AES-CBC（IV=key 前 16 字节）→ PKCS7 unpad
        结构：16B 随机 + 4B 大端长度 + msg + receive_id
        若 receive_id ≠ CorpID: 抛 ValueError
        返回 msg 字符串

## 异常与边界（必填）
- 本文件处理：验签失败、CorpID 不匹配、AESKey 长度非法 → ValueError
- 故意往上抛：全部安全失败上抛；由 main 转 400（GET）或记日志后对企微仍回 success（POST 防重试风暴，见 main 伪代码）
- 边界：EncodingAESKey 须 43 字符；空 Encrypt / 畸形 XML 在解析阶段失败

## 注意事项 / 坑
- AESKey 解码时必须补 `=`，漏补会导致 key 长度错误
- 切勿在日志中打印明文审批 XML 中的敏感字段
- 与官方加解密库算法一致；勿「兼容」跳过 CorpID 校验
