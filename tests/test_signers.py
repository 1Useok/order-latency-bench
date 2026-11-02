"""세 구현(Python idiomatic / tuned, C++)이 같은 주문에 대해 같은 요청을 만드는지 확인한다.

측정 대상이 '같은 일'을 하는지 보장하는 테스트다. 고정 nonce를 주면 Authorization과 본문이 바이트 단위로 같아야 하고,
토큰은 PyJWT로 검증되며 query_hash는 업비트 방식(unquote(urlencode(params)))의 SHA-512와 같아야 한다.
"""
import hashlib
import json
import pathlib
import subprocess
import sys
from urllib.parse import unquote, urlencode

import jwt
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from upbit_order import ORDER, TunedSigner, build_idiomatic, parse_response  # noqa: E402

AK, SK, NONCE = "A" * 40, "S" * 40, "11111111-2222-4333-8444-555555555555"
CPP_BENCH = ROOT / "build" / "upbit_bench.exe"


def test_tuned_matches_idiomatic_byte_for_byte():
    a = build_idiomatic(ORDER, AK, SK, nonce=NONCE)
    b = TunedSigner(AK, SK).build(ORDER, nonce=NONCE)
    assert a.authorization == b.authorization
    assert a.body == b.body


@pytest.mark.skipif(not CPP_BENCH.exists(), reason="C++ build missing (scripts/build.bat)")
def test_cpp_matches_python_byte_for_byte(tmp_path):
    env = tmp_path / ".env"
    env.write_text(f"UPBIT_ACCESS_KEY={AK}\nUPBIT_SECRET_KEY={SK}\n")
    out = subprocess.run([str(CPP_BENCH), "--env", str(env), "--print-token", NONCE],
                         capture_output=True, text=True, check=True, cwd=CPP_BENCH.parent).stdout.splitlines()
    py = TunedSigner(AK, SK).build(ORDER, nonce=NONCE)
    assert out[0] == "Authorization: " + py.authorization
    assert out[1].encode() == py.body


def test_token_is_valid_upbit_jwt():
    token = TunedSigner(AK, SK).build(ORDER).authorization.removeprefix("Bearer ")
    claims = jwt.decode(token, SK, algorithms=["HS256"])
    expected = hashlib.sha512(unquote(urlencode(ORDER)).encode()).hexdigest()
    assert claims["access_key"] == AK and claims["query_hash"] == expected and claims["query_hash_alg"] == "SHA512"
    assert json.loads(TunedSigner(AK, SK).build(ORDER).body) == ORDER


def test_nonce_is_unique_per_request():
    s = TunedSigner(AK, SK)
    nonces = {jwt.decode(s.build(ORDER).authorization[7:], SK, algorithms=["HS256"])["nonce"] for _ in range(1000)}
    assert len(nonces) == 1000


def test_parse_error_response():
    r = parse_response(b'{"error":{"name":"no_authorization_ip","message":"..."}}')
    assert not r.ok and r.error == "no_authorization_ip"
