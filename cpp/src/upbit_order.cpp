#include "upbit_order.hpp"

#include <openssl/hmac.h>

#include <stdexcept>

namespace upbit {
namespace {

constexpr char kB64Url[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
constexpr char kHex[] = "0123456789abcdef";

// base64url(패딩 없음)을 out 뒤에 붙인다.
void append_b64url(std::string& out, const unsigned char* p, size_t n) {
    size_t i = 0;
    for (; i + 3 <= n; i += 3) {
        uint32_t v = (p[i] << 16) | (p[i + 1] << 8) | p[i + 2];
        out += kB64Url[v >> 18];
        out += kB64Url[(v >> 12) & 63];
        out += kB64Url[(v >> 6) & 63];
        out += kB64Url[v & 63];
    }
    if (n - i == 1) {
        uint32_t v = p[i] << 16;
        out += kB64Url[v >> 18];
        out += kB64Url[(v >> 12) & 63];
    } else if (n - i == 2) {
        uint32_t v = (p[i] << 16) | (p[i + 1] << 8);
        out += kB64Url[v >> 18];
        out += kB64Url[(v >> 12) & 63];
        out += kB64Url[(v >> 6) & 63];
    }
}

void append_b64url(std::string& out, std::string_view s) {
    append_b64url(out, reinterpret_cast<const unsigned char*>(s.data()), s.size());
}

const std::string& jwt_header() {
    static const std::string h = [] {
        std::string s;
        append_b64url(s, R"({"alg":"HS256","typ":"JWT"})");
        return s;
    }();
    return h;
}

}  // namespace

OrderParams benchmark_order() { return {"KRW-BTC", "bid", "limit", "50000000", "0.0001"}; }

Signer::Signer(std::string access_key, std::string secret_key)
    : payload_prefix_(R"({"access_key":")" + access_key + R"(","nonce":")"),
      secret_(std::move(secret_key)),
      rng_(std::random_device{}()) {
    sha512_ = EVP_MD_fetch(nullptr, "SHA512", nullptr);
    sha256_ = EVP_MD_fetch(nullptr, "SHA256", nullptr);
    if (!sha512_ || !sha256_) throw std::runtime_error("EVP_MD_fetch failed");
}

Signer::~Signer() {
    EVP_MD_free(sha512_);
    EVP_MD_free(sha256_);
}

void Signer::make_nonce(char out[36]) {
    // UUID v4 형식. nonce는 요청마다 겹치지만 않으면 되므로 암호학적 난수가 아니어도 된다.
    unsigned char b[16];
    uint64_t hi = rng_(), lo = rng_();
    for (int i = 0; i < 8; ++i) b[i] = static_cast<unsigned char>(hi >> (56 - 8 * i));
    for (int i = 0; i < 8; ++i) b[8 + i] = static_cast<unsigned char>(lo >> (56 - 8 * i));
    b[6] = (b[6] & 0x0f) | 0x40;
    b[8] = (b[8] & 0x3f) | 0x80;
    int o = 0;
    for (int i = 0; i < 16; ++i) {
        if (i == 4 || i == 6 || i == 8 || i == 10) out[o++] = '-';
        out[o++] = kHex[b[i] >> 4];
        out[o++] = kHex[b[i] & 15];
    }
}

void Signer::build(const OrderParams& order, OrderRequest& out, std::string_view nonce) {
    // 1) query string -> SHA-512 hex
    std::string& q = out.query;
    q.clear();
    q.append("market=").append(order.market)
     .append("&side=").append(order.side)
     .append("&ord_type=").append(order.ord_type)
     .append("&price=").append(order.price)
     .append("&volume=").append(order.volume);
    unsigned char digest[EVP_MAX_MD_SIZE];
    unsigned int dlen = 0;
    EVP_Digest(q.data(), q.size(), digest, &dlen, sha512_, nullptr);

    // 2) JWT payload
    std::string& p = out.payload;
    p.assign(payload_prefix_);
    if (nonce.empty()) {
        char buf[36];
        make_nonce(buf);
        p.append(buf, 36);
    } else {
        p.append(nonce);
    }
    p.append(R"(","query_hash":")");
    for (unsigned int i = 0; i < dlen; ++i) {
        p += kHex[digest[i] >> 4];
        p += kHex[digest[i] & 15];
    }
    p.append(R"(","query_hash_alg":"SHA512"})");

    // 3) header.payload 서명(HS256)
    std::string& si = out.signing_input;
    si.assign(jwt_header()).append(".");
    append_b64url(si, p);
    unsigned char mac[EVP_MAX_MD_SIZE];
    unsigned int mlen = 0;
    HMAC(sha256_, secret_.data(), static_cast<int>(secret_.size()),
         reinterpret_cast<const unsigned char*>(si.data()), si.size(), mac, &mlen);

    out.authorization.assign("Authorization: Bearer ").append(si).append(".");
    append_b64url(out.authorization, mac, mlen);

    // 4) 본문. Python json.dumps 기본 구분자(", ", ": ")와 같은 모양으로 만든다.
    std::string& b = out.body;
    b.assign(R"({"market": ")").append(order.market)
     .append(R"(", "side": ")").append(order.side)
     .append(R"(", "ord_type": ")").append(order.ord_type)
     .append(R"(", "price": ")").append(order.price)
     .append(R"(", "volume": ")").append(order.volume)
     .append(R"("})");
}

// ----------------------------------------------------------------------------- 응답 파싱
namespace {

struct Cursor {
    std::string_view s;
    size_t i = 0;
    void ws() {
        while (i < s.size() && (s[i] == ' ' || s[i] == '\n' || s[i] == '\r' || s[i] == '\t')) ++i;
    }
    bool eat(char c) {
        ws();
        if (i < s.size() && s[i] == c) { ++i; return true; }
        return false;
    }
    // 문자열 하나를 읽는다. 이 응답에는 이스케이프가 거의 없으므로 \x는 문자 그대로 옮긴다.
    bool str(std::string_view& out) {
        ws();
        if (i >= s.size() || s[i] != '"') return false;
        size_t b = ++i;
        while (i < s.size() && s[i] != '"') i += (s[i] == '\\') ? 2 : 1;
        if (i >= s.size()) return false;
        out = s.substr(b, i - b);
        ++i;
        return true;
    }
    // 문자열이 아닌 값(숫자, true/false/null)을 건너뛴다.
    void scalar() {
        while (i < s.size() && s[i] != ',' && s[i] != '}') ++i;
    }
};

// 객체 하나를 읽으며 (key, 문자열 값)마다 on_field를 부른다. 중첩 객체는 on_object로 넘긴다.
template <class F, class G>
bool walk_object(Cursor& c, F&& on_field, G&& on_object) {
    if (!c.eat('{')) return false;
    if (c.eat('}')) return true;
    do {
        std::string_view key, val;
        if (!c.str(key) || !c.eat(':')) return false;
        c.ws();
        if (c.i < c.s.size() && c.s[c.i] == '"') {
            if (!c.str(val)) return false;
            on_field(key, val);
        } else if (c.i < c.s.size() && c.s[c.i] == '{') {
            if (!on_object(key, c)) return false;
        } else {
            c.scalar();
        }
    } while (c.eat(','));
    return c.eat('}');
}

}  // namespace

bool parse_order_test(std::string_view json, OrderTestResult& out) {
    Cursor c{json};
    out = OrderTestResult{};
    bool has_error = false;
    auto none = [](std::string_view, Cursor&) { return false; };
    bool parsed = walk_object(
        c,
        [&](std::string_view k, std::string_view v) {
            if (k == "uuid") out.uuid.assign(v);
            else if (k == "state") out.state.assign(v);
        },
        [&](std::string_view k, Cursor& inner) {
            if (k != "error") return false;
            has_error = true;
            return walk_object(
                inner, [&](std::string_view ek, std::string_view ev) { if (ek == "name") out.error.assign(ev); },
                none);
        });
    out.ok = parsed && !has_error;
    return parsed;
}

}  // namespace upbit
