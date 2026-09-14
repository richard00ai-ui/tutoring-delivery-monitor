"""企微「会话内容存档」SDK 拉取器(通过 ctypes 加载官方 Linux SDK)。

⚠️ 这个文件的 SDK 接口调用是骨架/占位。许可到位、拿到官方 SDK 包(headers +
libWeWorkFinanceSdk_C.so)之后,按官方 C 头文件把 ctypes 签名对齐即可。
参考: https://developer.work.weixin.qq.com/document/path/91774

主入口:
  fetch_and_persist(config, ...) —— 从 seq 游标读增量,解密,append 到 archive_msgs.csv

调度:见 scheduler.py,每小时跑一次,防止服务端 5 天过期数据丢失。
"""
from __future__ import annotations

import ctypes
import json
import logging
from datetime import datetime
from pathlib import Path

import config
import storage

log = logging.getLogger(__name__)


class ArchiveSdk:
    """官方 libWeWorkFinanceSdk_C.so 的 Python 封装。

    实际接口(来自官方 C 头文件):
      WeWorkFinanceSdk_t* NewSdk();
      int Init(WeWorkFinanceSdk_t* sdk, const char* corpid, const char* secret);
      int GetChatData(WeWorkFinanceSdk_t* sdk, unsigned long long seq,
                      unsigned int limit, const char* proxy, const char* passwd,
                      int timeout, Slice_t* chatData);
      int DecryptData(const char* encrypt_random_key, const char* encrypt_chat_msg,
                      const char* rsa_privkey, Slice_t* msg);
      int GetMediaData(WeWorkFinanceSdk_t* sdk, const char* indexbuf, const char* sdkFileid,
                       const char* proxy, const char* passwd, int timeout, MediaData_t* media);
      void DestroySdk(WeWorkFinanceSdk_t* sdk);
      Slice_t* NewSlice();
      void FreeSlice(Slice_t* slice);
      const char* GetContentFromSlice(Slice_t* slice);
      int GetSliceLen(Slice_t* slice);
    """

    def __init__(self, lib_path: Path, corpid: str, secret: str, private_key_path: Path):
        if not lib_path.exists():
            raise FileNotFoundError(f"SDK 库文件不存在: {lib_path}")
        if not private_key_path.exists():
            raise FileNotFoundError(f"私钥不存在: {private_key_path}")

        self._lib = ctypes.CDLL(str(lib_path))
        # TODO: 按官方头文件把 argtypes / restype 全部对齐
        self._sdk = self._lib.NewSdk()
        ret = self._lib.Init(self._sdk, corpid.encode(), secret.encode())
        if ret != 0:
            raise RuntimeError(f"SDK Init 失败, code={ret}")

        self._private_key = private_key_path.read_text()

    def get_chat_data(self, seq: int, limit: int = 1000) -> list[dict]:
        """从 seq+1 开始拉一批加密消息,返回 [{seq, msgid, encrypt_random_key, encrypt_chat_msg, ...}]。
        实际实现要:
          1. NewSlice() 创建 chatData
          2. GetChatData(sdk, seq, limit, ...) 填充 chatData
          3. GetContentFromSlice(chatData) 拿到 JSON 字符串
          4. json.loads → 返回其中的 chatdata 数组
          5. FreeSlice
        """
        # TODO: 实现真正的 ctypes 调用
        raise NotImplementedError("SDK ctypes 调用待联调时补齐")

    def decrypt(self, enc_random_key: str, enc_chat_msg: str) -> dict:
        """RSA 解密 random_key,再 AES 解密 chat_msg,返回明文 JSON。"""
        # TODO: NewSlice → DecryptData(random_key, chat_msg, private_key, out) → 读 slice
        raise NotImplementedError("SDK ctypes 调用待联调时补齐")

    def close(self):
        if hasattr(self, "_sdk") and self._sdk:
            self._lib.DestroySdk(self._sdk)
            self._sdk = None


def _normalize_message(seq: int, decrypted: dict) -> dict:
    """把 SDK 解密后的原始消息映射到 archive_msgs.csv 的行。

    存档消息 JSON 结构(节选):
      {
        "msgid": "xxx",
        "action": "send",
        "from": "userid1",
        "tolist": ["userid2", ...],
        "roomid": "wrxxx" (群聊才有),
        "msgtime": 1712345678901 (ms),
        "msgtype": "text" / "image" / ...,
        "text": {"content": "..."} (msgtype=text 时),
        "image": {"sdkfileid": "...", "md5sum": "..."} (msgtype=image 时),
        ...
      }
    """
    msg_time_ms = decrypted.get("msgtime", 0)
    ts = datetime.fromtimestamp(msg_time_ms / 1000) if msg_time_ms else datetime.now()

    msgtype = decrypted.get("msgtype", "text")
    if msgtype == "text":
        content = decrypted.get("text", {}).get("content", "")
    else:
        # 其他类型消息只留个占位,判定规则只用 text 里的 hashtag
        content = f"[{msgtype}]"

    return {
        "seq": seq,
        "msgid": decrypted.get("msgid", ""),
        "action": decrypted.get("action", ""),
        "from_id": decrypted.get("from", ""),
        "roomid": decrypted.get("roomid", ""),
        "ts": ts.isoformat(),
        "msgtype": msgtype,
        "content": content,
    }


def fetch_and_persist() -> int:
    """从 seq 游标增量拉一批,归一化后 append 到 archive_msgs.csv。返回本轮拉取条数。"""
    if config.USE_MOCK:
        log.info("USE_MOCK=true, skip real fetch")
        return 0

    sdk = ArchiveSdk(config.SDK_LIB_PATH, config.CORPID, config.SECRET, config.PRIVATE_KEY_PATH)
    try:
        seq = storage.read_seq(config.DATA_DIR)
        total_new = 0
        while total_new < config.FETCH_MAX_PER_RUN:
            batch = sdk.get_chat_data(seq, config.FETCH_BATCH_SIZE)
            if not batch:
                break
            rows = []
            for enc in batch:
                try:
                    plain = sdk.decrypt(enc["encrypt_random_key"], enc["encrypt_chat_msg"])
                except Exception as e:
                    log.warning(f"decrypt failed for seq={enc.get('seq')}: {e}")
                    continue
                rows.append(_normalize_message(enc["seq"], plain))
                seq = max(seq, int(enc["seq"]))
            storage.append_archive_msgs(config.DATA_DIR, rows)
            storage.write_seq(config.DATA_DIR, seq)
            total_new += len(rows)
        return total_new
    finally:
        sdk.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    n = fetch_and_persist()
    print(f"[fetch] 本轮新拉 {n} 条")
