"""업비트 주문 요청 생성(파라미터 직렬화 + query_hash + JWT 서명)과 응답 파싱.

같은 주문을 두 가지 방식으로 만든다.
- idiomatic: 업비트 공식 예제와 같은 방식(urlencode + PyJWT + requests의 json=)
- tuned: 표준 라이브러리만으로 같은 바이트를 만드는 방식(JWT 헤더 미리 인코딩, hmac.digest)

두 방식과 C++ 구현은 같은 nonce가 주어지면 바이트 단위로 같은 토큰을 만든다(tests/test_signers.py).
"""
import base64
import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
from urllib.parse import unquote, urlencode

import jwt

ORDER_TEST_PATH = "/v1/orders/test"

# 벤치마크에 쓰는 주문. order-test는 주문을 만들지 않으므로 체결되지 않는다.
# 시장가보다 한참 낮은 지정가로 둬서 실주문 경로로 잘못 보내도 체결되지 않게 한다.
ORDER = {"market": "KRW-BTC", "side": "bid", "ord_type": "limit", "price": "50000000", "volume": "0.0001"}


@dataclass
class OrderRequest:
    body: bytes            # HTTP 본문(JSON)
    authorization: str     # "Bearer <JWT>"


# ----------------------------------------------------------------------------- idiomatic
def build_idiomatic(order: dict, access_key: str, secret_key: str, nonce: str = None) -> OrderRequest:
    query = unquote(urlencode(order, doseq=True)).encode()
    payload = {
        "access_key": access_key,
        "nonce": nonce or str(uuid.uuid4()),
        "query_hash": hashlib.sha512(query).hexdigest(),
        "query_hash_alg": "SHA512",
    }
    token = jwt.encode(payload, secret_key, algorithm="HS256")
    return OrderRequest(body=json.dumps(order).encode(), authorization=f"Bearer {token}")


# ----------------------------------------------------------------------------- tuned
def _b64url(raw: bytes) -> bytes:
    return base64.urlsafe_b64encode(raw).rstrip(b"=")


_JWT_HEADER = _b64url(b'{"alg":"HS256","typ":"JWT"}')


class TunedSigner:
    """키와 JWT 헤더를 미리 준비해 두고, 주문마다 바뀌는 부분만 계산한다."""

    def __init__(self, access_key: str, secret_key: str):
        self._payload_prefix = '{"access_key":"%s","nonce":"' % access_key
        self._secret = secret_key.encode()

    def build(self, order: dict, nonce: str = None) -> OrderRequest:
        query = "&".join(f"{k}={v}" for k, v in order.items()).encode()
        payload = "%s%s\",\"query_hash\":\"%s\",\"query_hash_alg\":\"SHA512\"}" % (
            self._payload_prefix, nonce or str(uuid.uuid4()), hashlib.sha512(query).hexdigest())
        signing_input = _JWT_HEADER + b"." + _b64url(payload.encode())
        signature = _b64url(hmac.digest(self._secret, signing_input, "sha256"))
        body = json.dumps(order, separators=(", ", ": ")).encode()
        return OrderRequest(body=body, authorization="Bearer " + (signing_input + b"." + signature).decode())


# ----------------------------------------------------------------------------- 응답
@dataclass
class OrderTestResult:
    ok: bool
    uuid: str = ""
    state: str = ""
    error: str = ""


def parse_response(raw: bytes) -> OrderTestResult:
    doc = json.loads(raw)
    if "error" in doc:
        return OrderTestResult(ok=False, error=doc["error"].get("name", ""))
    return OrderTestResult(ok=True, uuid=doc.get("uuid", ""), state=doc.get("state", ""))
