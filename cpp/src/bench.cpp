// C++ 주문 경로 지연 측정. 인자와 CSV 형식은 python/bench.py와 같다.
//
//   upbit_bench --mode live --n 50 --out results/raw/x.csv
//   upbit_bench --print-token <nonce>    (테스트용: 고정 nonce로 만든 Authorization/본문 출력)
#include <curl/curl.h>
#include <openssl/crypto.h>

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <thread>
#include <vector>

#include "upbit_order.hpp"

namespace {

using Clock = std::chrono::steady_clock;

int64_t now_ns() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now().time_since_epoch()).count();
}

constexpr const char* kSampleResponse =
    R"({"market":"KRW-BTC","uuid":"cdd92199-2897-4e14-9448-f923320408ad","side":"bid","ord_type":"limit",)"
    R"("price":"50000000","state":"wait","created_at":"2026-11-02T14:00:00+09:00","volume":"0.0001",)"
    R"("remaining_volume":"0.0001","reserved_fee":"2.5","remaining_fee":"2.5","paid_fee":"0",)"
    R"("locked":"5002.5","executed_volume":"0","prevented_volume":"0","prevented_locked":"0",)"
    R"("trades_count":0})";

struct Args {
    std::string mode, out, env = ".env", print_nonce;
    int n = 1000, port = 18080;
    double interval_ms = 0;
    bool spin = false;  // 요청 간격을 sleep 대신 busy-wait로 기다린다
    bool warm = false;  // busy-wait 동안 더미 주문을 계속 만들어 캐시를 데워 둔다(전송하지 않음)
};

Args parse_args(int argc, char** argv) {
    Args a;
    for (int i = 1; i < argc; ++i) {
        std::string k = argv[i];
        auto v = [&]() -> std::string {
            if (i + 1 >= argc) { std::cerr << "missing value for " << k << "\n"; std::exit(2); }
            return argv[++i];
        };
        if (k == "--mode") a.mode = v();
        else if (k == "--n") a.n = std::stoi(v());
        else if (k == "--interval-ms") a.interval_ms = std::stod(v());
        else if (k == "--spin") a.spin = true;
        else if (k == "--warm") a.warm = true;
        else if (k == "--port") a.port = std::stoi(v());
        else if (k == "--env") a.env = v();
        else if (k == "--out") a.out = v();
        else if (k == "--print-token") a.print_nonce = v();
        else if (k == "--version") {
            std::cout << curl_version() << " | " << OpenSSL_version(OPENSSL_VERSION) << "\n";
            std::exit(0);
        }
        else { std::cerr << "unknown arg " << k << "\n"; std::exit(2); }
    }
    return a;
}

void load_keys(const std::string& path, std::string& ak, std::string& sk) {
    std::ifstream f(path);
    std::string line;
    while (std::getline(f, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        auto eq = line.find('=');
        if (eq == std::string::npos || line[0] == '#') continue;
        std::string k = line.substr(0, eq), v = line.substr(eq + 1);
        if (k == "UPBIT_ACCESS_KEY") ak = v;
        else if (k == "UPBIT_SECRET_KEY") sk = v;
    }
}

size_t on_body(char* p, size_t size, size_t n, void* user) {
    static_cast<std::string*>(user)->append(p, size * n);
    return size * n;
}

// libcurl easy 핸들 하나를 계속 써서 연결을 재사용한다(fresh면 요청마다 새 연결).
class HttpClient {
public:
    HttpClient(std::string url, bool fresh) : url_(std::move(url)) {
        h_ = curl_easy_init();
        curl_easy_setopt(h_, CURLOPT_URL, url_.c_str());
        curl_easy_setopt(h_, CURLOPT_POST, 1L);
        curl_easy_setopt(h_, CURLOPT_HTTP_VERSION, CURL_HTTP_VERSION_1_1);  // Python 클라이언트와 같은 HTTP/1.1
        curl_easy_setopt(h_, CURLOPT_TCP_NODELAY, 1L);
        curl_easy_setopt(h_, CURLOPT_WRITEFUNCTION, on_body);
        curl_easy_setopt(h_, CURLOPT_WRITEDATA, &resp_);
        if (fresh) {
            curl_easy_setopt(h_, CURLOPT_FRESH_CONNECT, 1L);
            curl_easy_setopt(h_, CURLOPT_FORBID_REUSE, 1L);
        }
        resp_.reserve(4096);
    }
    ~HttpClient() { curl_easy_cleanup(h_); }

    long post(const upbit::OrderRequest& req, std::string_view& body_out) {
        curl_slist* headers = curl_slist_append(nullptr, req.authorization.c_str());
        headers = curl_slist_append(headers, "Content-Type: application/json");
        curl_easy_setopt(h_, CURLOPT_HTTPHEADER, headers);
        curl_easy_setopt(h_, CURLOPT_POSTFIELDS, req.body.data());
        curl_easy_setopt(h_, CURLOPT_POSTFIELDSIZE, static_cast<long>(req.body.size()));
        resp_.clear();
        long status = 0;
        CURLcode rc = curl_easy_perform(h_);
        if (rc == CURLE_OK) curl_easy_getinfo(h_, CURLINFO_RESPONSE_CODE, &status);
        else std::cerr << "[cpp] curl error: " << curl_easy_strerror(rc) << "\n";
        curl_slist_free_all(headers);
        body_out = resp_;
        return status;
    }

private:
    std::string url_, resp_;
    CURL* h_ = nullptr;
};

struct Row {
    int seq;
    bool cold;
    long status;
    int64_t sign, http, parse, total;
};

}  // namespace

int main(int argc, char** argv) {
    Args a = parse_args(argc, argv);
    std::string ak, sk;
    load_keys(a.env, ak, sk);
    if (!a.print_nonce.empty() || (a.mode == "sign" && ak.empty())) {
        if (ak.empty()) { ak.assign(40, 'A'); sk.assign(40, 'S'); }
    }

    upbit::Signer signer(ak, sk);
    const upbit::OrderParams order = upbit::benchmark_order();
    upbit::OrderRequest req, scratch;

    if (!a.print_nonce.empty()) {
        signer.build(order, req, a.print_nonce);
        std::cout << req.authorization << "\n" << req.body << "\n";
        return 0;
    }
    if (a.mode != "sign" && a.mode != "loopback" && a.mode != "live" && a.mode != "live-cold") {
        std::cerr << "--mode sign|loopback|live|live-cold\n";
        return 2;
    }

    // HttpClient보다 먼저 만들어 나중에 정리되게 한다(easy 핸들 정리 후 global cleanup).
    struct CurlGlobal {
        CurlGlobal() { curl_global_init(CURL_GLOBAL_DEFAULT); }
        ~CurlGlobal() { curl_global_cleanup(); }
    } curl_global;
    std::string url = a.mode == "loopback" ? "http://127.0.0.1:" + std::to_string(a.port) + upbit::kOrderTestPath
                                           : std::string("https://api.upbit.com") + upbit::kOrderTestPath;
    HttpClient http(url, a.mode == "live-cold");
    upbit::OrderTestResult result;

    std::vector<Row> rows;
    rows.reserve(a.n);
    int64_t next_at = now_ns();
    for (int seq = 0; seq < a.n; ++seq) {
        if (a.interval_ms > 0) {
            if (a.warm) {
                while (now_ns() < next_at) signer.build(order, scratch);
            } else if (a.spin) {
                while (now_ns() < next_at) {
                }
            } else {
                int64_t wait = next_at - now_ns();
                if (wait > 0) std::this_thread::sleep_for(std::chrono::nanoseconds(wait));
            }
            next_at += static_cast<int64_t>(a.interval_ms * 1e6);
        }
        int64_t t0 = now_ns();
        signer.build(order, req);
        int64_t t1 = now_ns();
        long status = 201;
        std::string_view body = kSampleResponse;
        if (a.mode != "sign") status = http.post(req, body);
        int64_t t2 = now_ns();
        upbit::parse_order_test(body, result);
        int64_t t3 = now_ns();
        if (a.mode != "sign" && seq == 0 && !result.ok)
            std::cerr << "[cpp-curl] first response " << status << ": " << result.error << "\n";
        bool cold = a.mode == "live-cold" || (a.mode != "sign" && seq == 0);
        rows.push_back({seq, cold, status, t1 - t0, t2 - t1, t3 - t2, t3 - t0});
    }

    std::filesystem::path out(a.out);
    if (out.has_parent_path()) std::filesystem::create_directories(out.parent_path());
    std::ofstream f(out);
    f << "impl,mode,seq,conn,status,sign_ns,http_ns,parse_ns,total_ns\n";
    for (const Row& r : rows)
        f << "cpp-curl," << a.mode << ',' << r.seq << ',' << (r.cold ? "cold" : "warm") << ',' << r.status << ','
          << r.sign << ',' << r.http << ',' << r.parse << ',' << r.total << '\n';
    return 0;
}
