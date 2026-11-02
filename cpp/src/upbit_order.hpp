// 업비트 주문 요청 생성(파라미터 직렬화 + query_hash + JWT HS256 서명)과 응답 파싱.
//
// 핫패스에서 힙 할당을 줄이기 위해 출력 버퍼(OrderRequest)를 호출자가 들고 재사용한다.
// 같은 nonce가 주어지면 Python 구현(python/upbit_order.py)과 바이트 단위로 같은 토큰을 만든다.
#pragma once

#include <openssl/evp.h>

#include <cstdint>
#include <random>
#include <string>
#include <string_view>

namespace upbit {

inline constexpr const char* kOrderTestPath = "/v1/orders/test";

struct OrderParams {
    std::string market, side, ord_type, price, volume;
};

// 벤치마크 주문. order-test는 주문을 만들지 않으며, 가격도 시장가보다 한참 낮다.
OrderParams benchmark_order();

struct OrderRequest {
    std::string body;           // HTTP 본문(JSON)
    std::string authorization;  // "Authorization: Bearer <JWT>" 헤더 한 줄
    // 내부 작업 버퍼
    std::string query, payload, signing_input;
};

class Signer {
public:
    Signer(std::string access_key, std::string secret_key);
    ~Signer();
    Signer(const Signer&) = delete;
    Signer& operator=(const Signer&) = delete;

    // nonce가 비어 있으면 UUID v4를 새로 만든다(테스트에서만 고정 nonce를 넘긴다).
    void build(const OrderParams& order, OrderRequest& out, std::string_view nonce = {});

private:
    void make_nonce(char out[36]);

    std::string payload_prefix_;  // {"access_key":"...","nonce":"
    std::string secret_;
    std::mt19937_64 rng_;
    EVP_MD* sha512_ = nullptr;  // 매 호출 implicit fetch를 피하려고 미리 가져온다
    EVP_MD* sha256_ = nullptr;
};

struct OrderTestResult {
    bool ok = false;
    std::string uuid, state, error;
};

// order-test 응답(평평한 객체) 또는 오류 응답({"error":{"name":..,"message":..}})을 읽는다.
// 범용 JSON 파서가 아니라 이 응답 모양만 다루는 스키마 전용 파서다.
bool parse_order_test(std::string_view json, OrderTestResult& out);

}  // namespace upbit
