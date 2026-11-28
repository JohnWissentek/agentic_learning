import base64
import hashlib
import struct
from Crypto.Cipher import AES

class PKCS7Padding:
    @staticmethod
    def unpad(data):
        pad = data[-1]
        if pad < 1 or pad > 32:
            pad = 0
        return data[:-pad] if pad else data

class WXBizMsgCrypt:
    def __init__(self, token: str, encoding_aes_key: str, receive_id: str):
        self.token = token
        self.key = base64.b64decode(encoding_aes_key + "=")
        self.receive_id = receive_id
        if len(self.key) != 32:
            raise ValueError("EncodingAESKey must be exactly 43 characters long")

    def _get_sha1_signature(self, timestamp: str, nonce: str, encrypt_msg: str) -> str:
        """Calculate SHA1 signature for verification."""
        arr = sorted([self.token, timestamp, nonce, encrypt_msg])
        sha1 = hashlib.sha1()
        sha1.update("".join(arr).encode("utf-8"))
        return sha1.hexdigest()

    def verify_url(self, msg_signature: str, timestamp: str, nonce: str, echostr: str) -> str:
        """Verify the signature and decrypt the echostr for WeCom callback configuration."""
        expected_sig = self._get_sha1_signature(timestamp, nonce, echostr)
        if expected_sig != msg_signature:
            raise ValueError("WeCom URL MsgSignature verification failed")
        
        decrypted = self.decrypt(echostr)
        return decrypted

    def decrypt_xml_msg(self, msg_signature: str, timestamp: str, nonce: str, post_data: str) -> str:
        """Decrypt encrypted XML message push from WeCom."""
        import xmltodict
        doc = xmltodict.parse(post_data)
        xml_data = doc.get("xml", {})
        encrypt_msg = xml_data.get("Encrypt")
        
        # Verify signature
        expected_sig = self._get_sha1_signature(timestamp, nonce, encrypt_msg)
        if expected_sig != msg_signature:
            raise ValueError("WeCom XML MsgSignature verification failed")
            
        return self.decrypt(encrypt_msg)

    def decrypt(self, encrypt_msg: str) -> str:
        """Perform AES CBC decryption of WeCom encrypted string."""
        cipher_bytes = base64.b64decode(encrypt_msg)
        # IV is the first 16 bytes of key
        cipher = AES.new(self.key, AES.MODE_CBC, self.key[:16])
        plain_bytes = PKCS7Padding.unpad(cipher.decrypt(cipher_bytes))
        
        # Structure: random (16B) + msg_len (4B) + msg + receive_id (CorpID)
        msg_len = struct.unpack("!I", plain_bytes[16:20])[0]
        msg = plain_bytes[20:20 + msg_len].decode("utf-8")
        recv_id = plain_bytes[20 + msg_len:].decode("utf-8")
        
        if recv_id != self.receive_id:
            raise ValueError("Decrypted receive_id does not match CorpID")
            
        return msg
