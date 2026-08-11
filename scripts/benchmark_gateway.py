from __future__ import annotations

import argparse
import getpass
import json
import math
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen


DEFAULT_PATHS = (
    "/dashboard/summary",
    "/ports?page=1&page_size=50",
    "/routes?page=1&page_size=50",
    "/voyages?page=1&page_size=50",
    "/cargo-listings?page=1&page_size=50",
    "/bookings?page=1&page_size=50",
)


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, math.ceil(p * len(ordered)) - 1))
    return ordered[rank]


def login(base_url: str, username: str, password: str, timeout: float) -> str:
    jar = CookieJar()
    opener = build_opener(HTTPCookieProcessor(jar))
    payload = json.dumps({"username_or_email": username, "password": password}).encode("utf-8")
    req = Request(
        base_url.rstrip("/") + "/auth/login",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with opener.open(req, timeout=timeout) as response:
        response.read()
    cookies = [f"{cookie.name}={cookie.value}" for cookie in jar]
    if not cookies:
        raise RuntimeError("Login succeeded but no session cookies were returned")
    return "; ".join(cookies)


def one_request(url: str, cookie: str, timeout: float) -> tuple[int, float, int]:
    started = time.perf_counter()
    req = Request(url, method="GET", headers={"Accept": "application/json", "Cookie": cookie})
    try:
        with urlopen(req, timeout=timeout) as response:
            body = response.read()
            return int(response.status), time.perf_counter() - started, len(body)
    except HTTPError as exc:
        body = exc.read()
        return int(exc.code), time.perf_counter() - started, len(body)
    except URLError:
        return 0, time.perf_counter() - started, 0


def benchmark_path(
    *,
    base_url: str,
    path: str,
    cookie: str,
    requests: int,
    concurrency: int,
    timeout: float,
) -> dict[str, object]:
    url = base_url.rstrip("/") + path
    durations: list[float] = []
    statuses: dict[int, int] = {}
    bytes_total = 0
    wall_started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(one_request, url, cookie, timeout) for _ in range(requests)]
        for future in as_completed(futures):
            status, duration, size = future.result()
            statuses[status] = statuses.get(status, 0) + 1
            durations.append(duration)
            bytes_total += size
    wall = time.perf_counter() - wall_started
    ok = sum(count for status, count in statuses.items() if 200 <= status < 300)
    return {
        "path": path,
        "requests": requests,
        "ok": ok,
        "statuses": statuses,
        "wall_seconds": wall,
        "rps": requests / wall if wall > 0 else 0.0,
        "avg_ms": statistics.fmean(durations) * 1000 if durations else 0.0,
        "p50_ms": percentile(durations, 0.50) * 1000,
        "p95_ms": percentile(durations, 0.95) * 1000,
        "p99_ms": percentile(durations, 0.99) * 1000,
        "bytes": bytes_total,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only OptiCargo Gateway benchmark")
    parser.add_argument("--base-url", default="http://localhost:8000/api/v1")
    parser.add_argument("--username", default="umkm.demo")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument(
        "--path",
        action="append",
        dest="paths",
        help="Relative GET path to benchmark. Repeat for multiple paths; defaults to common FE collections.",
    )
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1:
        parser.error("--requests and --concurrency must be >= 1")

    password = os.getenv("OPTICARGO_BENCHMARK_PASSWORD") or getpass.getpass(
        f"Password for {args.username}: "
    )
    try:
        cookie = login(args.base_url, args.username, password, args.timeout)
    except Exception as exc:  # noqa: BLE001 - CLI should report a concise login failure
        print(f"LOGIN_FAILED: {exc}")
        return 2

    paths = tuple(args.paths or DEFAULT_PATHS)
    print(
        f"Gateway benchmark user={args.username} requests/path={args.requests} "
        f"concurrency={args.concurrency}"
    )
    print("=" * 88)
    print(f"{'PATH':42s} {'OK':>7s} {'RPS':>8s} {'AVG':>9s} {'P50':>9s} {'P95':>9s} {'P99':>9s}")
    exit_code = 0
    for path in paths:
        result = benchmark_path(
            base_url=args.base_url,
            path=path,
            cookie=cookie,
            requests=args.requests,
            concurrency=args.concurrency,
            timeout=args.timeout,
        )
        ok = int(result["ok"])
        if ok != args.requests:
            exit_code = 1
        print(
            f"{path[:42]:42s} "
            f"{ok:4d}/{args.requests:<2d} "
            f"{float(result['rps']):8.1f} "
            f"{float(result['avg_ms']):8.1f}ms "
            f"{float(result['p50_ms']):8.1f}ms "
            f"{float(result['p95_ms']):8.1f}ms "
            f"{float(result['p99_ms']):8.1f}ms"
        )
        statuses = result["statuses"]
        if statuses != {200: args.requests}:
            print(f"  statuses={statuses}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
