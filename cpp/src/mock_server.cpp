// loopback 측정용 mock 서버: POST /v1/orders/test에 고정된 201 응답을 keep-alive로 돌려준다.
//
// 서버 처리 시간을 거의 0으로 만들어, 측정값에 남는 것이 클라이언트 쪽 HTTP 스택 비용이 되게 한다.
// 측정은 한 번에 한 클라이언트만 붙으므로 단일 스레드로 충분하다.
//
//   mock_server [port]     (기본 18080)
#include <winsock2.h>
#include <ws2tcpip.h>

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

#pragma comment(lib, "ws2_32.lib")

namespace {

constexpr const char* kBody =
    R"({"market":"KRW-BTC","uuid":"cdd92199-2897-4e14-9448-f923320408ad","side":"bid","ord_type":"limit",)"
    R"("price":"50000000","state":"wait","created_at":"2026-11-02T14:00:00+09:00","volume":"0.0001",)"
    R"("remaining_volume":"0.0001","reserved_fee":"2.5","remaining_fee":"2.5","paid_fee":"0",)"
    R"("locked":"5002.5","executed_volume":"0","prevented_volume":"0","prevented_locked":"0",)"
    R"("trades_count":0})";

size_t content_length(const std::string& head) {
    // 헤더 이름은 대소문자를 가리지 않는다.
    std::string lower(head);
    for (char& c : lower) c = static_cast<char>(tolower(static_cast<unsigned char>(c)));
    size_t p = lower.find("\r\ncontent-length:");
    return p == std::string::npos ? 0 : std::strtoul(head.c_str() + p + 17, nullptr, 10);
}

void serve(SOCKET s, const std::string& response) {
    std::string buf;
    char chunk[8192];
    for (;;) {
        size_t head_end;
        while ((head_end = buf.find("\r\n\r\n")) == std::string::npos) {
            int n = recv(s, chunk, sizeof(chunk), 0);
            if (n <= 0) return;
            buf.append(chunk, n);
        }
        size_t need = head_end + 4 + content_length(buf.substr(0, head_end + 2));
        while (buf.size() < need) {
            int n = recv(s, chunk, sizeof(chunk), 0);
            if (n <= 0) return;
            buf.append(chunk, n);
        }
        buf.erase(0, need);
        if (send(s, response.data(), static_cast<int>(response.size()), 0) <= 0) return;
    }
}

}  // namespace

int main(int argc, char** argv) {
    int port = argc > 1 ? std::atoi(argv[1]) : 18080;
    WSADATA wsa;
    WSAStartup(MAKEWORD(2, 2), &wsa);

    const std::string body = kBody;
    const std::string response = "HTTP/1.1 201 Created\r\nContent-Type: application/json; charset=utf-8\r\n"
                                 "Content-Length: " + std::to_string(body.size()) +
                                 "\r\nConnection: keep-alive\r\n\r\n" + body;

    SOCKET ls = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    BOOL yes = TRUE;
    setsockopt(ls, SOL_SOCKET, SO_REUSEADDR, reinterpret_cast<const char*>(&yes), sizeof(yes));
    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(static_cast<u_short>(port));
    inet_pton(AF_INET, "127.0.0.1", &addr.sin_addr);
    if (bind(ls, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0 || listen(ls, 16) != 0) {
        std::fprintf(stderr, "mock_server: cannot listen on 127.0.0.1:%d\n", port);
        return 1;
    }
    std::printf("mock_server listening on 127.0.0.1:%d\n", port);
    std::fflush(stdout);

    for (;;) {
        SOCKET s = accept(ls, nullptr, nullptr);
        if (s == INVALID_SOCKET) continue;
        setsockopt(s, IPPROTO_TCP, TCP_NODELAY, reinterpret_cast<const char*>(&yes), sizeof(yes));
        serve(s, response);
        closesocket(s);
    }
}
