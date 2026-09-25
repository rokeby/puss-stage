// go1_remote_bridge.cpp
//
// Runs on the GO1's internal head Raspberry Pi. Reads the handheld remote's
// state from the robot via the Unitree Legged SDK and forwards it as small
// JSON packets over UDP to the UE host.
//
// Written against the SDK that ships on the dog itself
// (~/Unitree/sdk/unitree_legged_sdk, firmware 1.3.8), NOT the newer public
// v3.8 release — the struct layouts differ. Notes on that copy:
//   * HighCmd uses velocity[2] / yawSpeed / mode (NOT the forwardSpeed,
//     sideSpeed, rotateSpeed fields used by its own stale example_wifi_joy.cpp).
//   * wirelessRemote is std::array<uint8_t,40>, so .data() is needed.
//   * Its CMakeLists.txt lists example sources that don't exist, so cmake
//     cannot configure it. We build with a direct g++ call instead and never
//     modify anything inside ~/Unitree.
//
// Usage:
//   ./go1_remote_bridge <ue_host_ip> [ue_port=9876] [rate_hz=50]
//                       [robot_ip=192.168.123.10] [robot_port=8007]
//                       [local_port=8090]
//
// local_port must be free on the Pi; the dog's own services sometimes hold
// 8090. The SDK only warns ("Bind client ip&port failed") and then silently
// fails to receive, so if every packet reads source_lost, try another port.
//
// Safety: the HighCmd sent to the robot is explicitly zeroed every tick and
// left in mode 0 (idle). It solicits state replies and commands no motion.
// The dog stays under normal handheld-remote control while this runs.

#include "unitree_legged_sdk/unitree_legged_sdk.h"
#include "unitree_legged_sdk/joystick.h"

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <thread>

using namespace UNITREE_LEGGED_SDK;

static float Sanitize(float v)
{
    if (std::isnan(v) || std::isinf(v)) return 0.0f;
    if (v > 1.0f) return 1.0f;
    if (v < -1.0f) return -1.0f;
    return v;
}

static int64_t NowMs()
{
    using namespace std::chrono;
    return duration_cast<milliseconds>(system_clock::now().time_since_epoch()).count();
}

// Zero every motion-bearing field. Called each tick so no stale value can
// ever reach the robot, even if InitCmdData's defaults change.
static void MakeIdle(HighCmd& cmd)
{
    cmd.mode = 0;              // 0 = idle / default stand
    cmd.gaitType = 0;
    cmd.speedLevel = 0;
    cmd.footRaiseHeight = 0.0f;
    cmd.bodyHeight = 0.0f;
    cmd.postion[0] = 0.0f;     // sic: SDK spells it "postion"
    cmd.postion[1] = 0.0f;
    cmd.euler[0] = 0.0f;
    cmd.euler[1] = 0.0f;
    cmd.euler[2] = 0.0f;
    cmd.velocity[0] = 0.0f;
    cmd.velocity[1] = 0.0f;
    cmd.yawSpeed = 0.0f;
}

int main(int argc, char** argv)
{
    if (argc < 2) {
        std::fprintf(stderr,
            "usage: %s <ue_host_ip> [ue_port=9876] [rate_hz=50] "
            "[robot_ip=192.168.123.10] [robot_port=8007]\n", argv[0]);
        return 1;
    }
    const char* destIp    = argv[1];
    const int   destPort  = (argc > 2) ? std::atoi(argv[2]) : 9876;
    const int   rateHz    = (argc > 3) ? std::atoi(argv[3]) : 50;
    const char* robotIp   = (argc > 4) ? argv[4] : "192.168.123.10";
    const int   robotPort = (argc > 5) ? std::atoi(argv[5]) : 8007;
    const int   localPort = (argc > 6) ? std::atoi(argv[6]) : 8090;

    if (destPort <= 0 || destPort > 65535 || rateHz < 1 || rateHz > 200) {
        std::fprintf(stderr, "bad port or rate\n");
        return 1;
    }

    // --- Outbound socket to the UE host -------------------------------------
    int sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (sock < 0) { std::perror("socket"); return 1; }
    sockaddr_in dest{};
    dest.sin_family = AF_INET;
    dest.sin_port = htons(static_cast<uint16_t>(destPort));
    if (inet_pton(AF_INET, destIp, &dest.sin_addr) != 1) {
        std::fprintf(stderr, "bad UE host ip: %s\n", destIp);
        return 1;
    }

    // --- Robot high-level channel -------------------------------------------
    UDP robot(static_cast<uint16_t>(localPort), robotIp, static_cast<uint16_t>(robotPort),
              HIGH_CMD_LENGTH, HIGH_STATE_LENGTH);
    HighCmd cmd = {0};
    HighState state = {0};
    robot.InitCmdData(cmd);

    xRockerBtnDataStruct keyData;
    std::memset(&keyData, 0, sizeof(keyData));

    // Source-loss detection: HighState always jitters (IMU noise), so bytes
    // that stop changing entirely mean the feed is dead.
    HighState prevState = {0};
    int64_t lastChangeMs = 0;

    uint32_t seq = 0;
    uint64_t sockErrors = 0;
    // Diagnostics: how often the source actually changes, vs how often we poll.
    // Sending faster than stateChanges/sec just duplicates values.
    uint32_t stateChanges = 0;   // HighState bytes differed (IMU noise => ~publish rate)
    uint32_t remoteChanges = 0;  // wirelessRemote bytes differed (=> stick update rate)
    uint8_t prevRemote[40] = {0};
    const auto tick = std::chrono::microseconds(1000000 / rateHz);
    auto nextTick = std::chrono::steady_clock::now();

    std::printf("go1_remote_bridge: robot %s:%d (local %d) -> UE host %s:%d at %d Hz\n",
                robotIp, robotPort, localPort, destIp, destPort, rateHz);
    std::fflush(stdout);

    while (true) {
        MakeIdle(cmd);
        robot.SetSend(cmd);
        robot.Send();
        robot.Recv();
        robot.GetRecv(state);

        const int64_t t = NowMs();
        if (std::memcmp(&state, &prevState, sizeof(HighState)) != 0) {
            std::memcpy(&prevState, &state, sizeof(HighState));
            lastChangeMs = t;
            ++stateChanges;
        }
        if (std::memcmp(prevRemote, state.wirelessRemote.data(), 40) != 0) {
            std::memcpy(prevRemote, state.wirelessRemote.data(), 40);
            ++remoteChanges;
        }
        const bool sourceLost = (lastChangeMs == 0) || (t - lastChangeMs > 1000);

        std::memcpy(&keyData, state.wirelessRemote.data(), sizeof(keyData));

        const float lx = sourceLost ? 0.0f : Sanitize(keyData.lx);
        const float ly = sourceLost ? 0.0f : Sanitize(keyData.ly);
        const float rx = sourceLost ? 0.0f : Sanitize(keyData.rx);
        const float ry = sourceLost ? 0.0f : Sanitize(keyData.ry);
        const unsigned keys = sourceLost ? 0u : keyData.btn.value;

        // Dog's own mode/gait, so UE can mirror its real state rather than
        // counting button presses (which drift if an edge is ever missed).
        const unsigned dogMode = sourceLost ? 0u : static_cast<unsigned>(state.mode);
        const unsigned dogGait = sourceLost ? 0u : static_cast<unsigned>(state.gaitType);

        char buf[256];
        const int n = std::snprintf(buf, sizeof(buf),
            "{\"v\":1,\"seq\":%u,\"t\":%lld,\"lx\":%.4f,\"ly\":%.4f,"
            "\"rx\":%.4f,\"ry\":%.4f,\"keys\":%u,\"mode\":%u,\"gait\":%u,"
            "\"source_lost\":%s}",
            ++seq, static_cast<long long>(t), lx, ly, rx, ry, keys,
            dogMode, dogGait, sourceLost ? "true" : "false");

        if (sendto(sock, buf, n, 0, reinterpret_cast<sockaddr*>(&dest), sizeof(dest)) < 0) {
            ++sockErrors;  // keep trying; keep sequencing
        }

        if (seq % static_cast<uint32_t>(rateHz) == 0) {
            std::printf("[stats] seq=%u lost=%d sock_err=%llu poll/s=%d "
                        "state_chg/s=%u remote_chg/s=%u mode=%u gait=%u "
                        "lx=%+.2f ly=%+.2f rx=%+.2f ry=%+.2f keys=0x%04x\n",
                        seq, sourceLost ? 1 : 0,
                        static_cast<unsigned long long>(sockErrors), rateHz,
                        stateChanges, remoteChanges, dogMode, dogGait,
                        lx, ly, rx, ry, keys);
            std::fflush(stdout);
            stateChanges = 0;
            remoteChanges = 0;
        }

        nextTick += tick;
        std::this_thread::sleep_until(nextTick);
    }

    close(sock);
    return 0;
}
