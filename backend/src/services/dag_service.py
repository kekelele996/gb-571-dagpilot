"""算法 1：Kahn 拓扑排序 + 环检测 + EST/EFT 递推 + 关键路径（P50 / P90 两套口径）。

纯函数式实现，输入是已序列化的作业/依赖列表，不碰 ORM，便于单测与复现：
  - jobs:  [{id, code, name, layer, owner, p50_seconds, p90_seconds}]
  - edges: [{upstream_id, downstream_id, dep_type, lag_minutes}]

口径：
  EST(j) = max(EFT(p) + lag(p->j))        前驱为空则 0
  EFT(j) = EST(j) + dur(j)                dur 取 P50 或 P90 秒数 / 60
  LFT(j) = min(LST(s) - lag(j->s))        后继为空则取链路总时长
  LST(j) = LFT(j) - dur(j)
  总浮时 = LST - EST；总浮时 = 0 的作业落在关键路径上
  链路总时长 = max(EFT) = 关键路径上各作业时长之和（含 lag）
"""
from __future__ import annotations

import heapq
from typing import Any

from src.constants.enums import JobStatus, RunMode
from src.constants.limits import MAX_JOBS_PER_SIMULATION
from src.utils.errors import AppError
from src.utils.timeutil import human_duration, minutes_to_clock


def duration_seconds(job: dict, mode: str) -> int:
    if mode == RunMode.P90.value:
        return int(job.get("p90_seconds") or 0)
    return int(job.get("p50_seconds") or 0)


def duration_minutes(job: dict, mode: str) -> int:
    seconds = duration_seconds(job, mode)
    return max(1, round(seconds / 60))


def _index(jobs: list[dict], edges: list[dict]) -> tuple[dict[str, dict], dict[str, list[dict]], dict[str, list[dict]]]:
    by_code: dict[str, dict] = {}
    for job in jobs:
        by_code[job["code"]] = job
    preds: dict[str, list[dict]] = {code: [] for code in by_code}
    succs: dict[str, list[dict]] = {code: [] for code in by_code}
    for edge in edges:
        up = edge["upstream_code"]
        down = edge["downstream_code"]
        if up not in by_code or down not in by_code:
            continue
        preds[down].append(edge)
        succs[up].append(edge)
    return by_code, preds, succs


def _find_cycle(by_code: dict[str, dict], succs: dict[str, list[dict]], suspects: list[str]) -> list[str]:
    """剩余入度非零的点里做 DFS，返回一条真实存在的环路径（首尾同点）。"""
    suspect_set = set(suspects)
    color: dict[str, int] = {code: 0 for code in by_code}  # 0 未访问 1 在栈上 2 完成
    stack: list[str] = []

    def dfs(node: str) -> list[str] | None:
        color[node] = 1
        stack.append(node)
        for edge in succs[node]:
            nxt = edge["downstream_code"]
            if nxt not in suspect_set:
                continue
            if color[nxt] == 1:
                start = stack.index(nxt)
                return stack[start:] + [nxt]
            if color[nxt] == 0:
                found = dfs(nxt)
                if found:
                    return found
        stack.pop()
        color[node] = 2
        return None

    for code in suspects:
        if color[code] == 0:
            found = dfs(code)
            if found:
                return found
    return []


def topological_sort(jobs: list[dict], edges: list[dict]) -> dict:
    """Kahn 拓扑排序；有环则返回 ok=False + 一条环路径。"""
    if not jobs:
        return {
            "ok": False,
            "reason": "DAG_EMPTY",
            "message": "该链路还没有作业",
            "order": [],
            "cycle_path": [],
            "layers": {},
        }
    if len(jobs) > MAX_JOBS_PER_SIMULATION:
        raise AppError(
            "VALIDATION",
            422,
            detail=f"作业数 {len(jobs)} 超过单次计算上限 {MAX_JOBS_PER_SIMULATION}",
        )
    by_code, preds, succs = _index(jobs, edges)
    indeg = {code: len(preds[code]) for code in by_code}
    ready = [code for code, degree in indeg.items() if degree == 0]
    heapq.heapify(ready)  # 编码字典序，保证同一份图每次输出完全一致
    order: list[str] = []
    while ready:
        code = heapq.heappop(ready)
        order.append(code)
        for edge in succs[code]:
            nxt = edge["downstream_code"]
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                heapq.heappush(ready, nxt)

    if len(order) != len(by_code):
        suspects = [code for code in by_code if code not in set(order)]
        cycle_path = _find_cycle(by_code, succs, suspects)
        return {
            "ok": False,
            "reason": "DAG_CYCLE",
            "message": "依赖存在环，无法生成排期",
            "order": order,
            "cycle_path": cycle_path,
            "cycle_text": " → ".join(cycle_path),
            "cycles": [cycle_path],
            "settled": len(order),
            "total": len(by_code),
            "layers": {},
        }

    # 拓扑分层：层号 = 最长前驱链长度，用于 SVG 分层布局（自绘地铁图的 x 轴）
    layers: dict[str, int] = {}
    for code in order:
        if not preds[code]:
            layers[code] = 0
        else:
            layers[code] = 1 + max(layers[edge["upstream_code"]] for edge in preds[code])
    layer_widths: dict[str, int] = {}
    for code, depth in layers.items():
        layer_widths[str(depth)] = layer_widths.get(str(depth), 0) + 1
    return {
        "ok": True,
        "reason": None,
        "order": order,
        "cycle_path": [],
        "layers": layers,
        "layer_count": (max(layers.values()) + 1) if layers else 0,
        "layer_widths": layer_widths,
        "settled": len(order),
        "total": len(by_code),
    }


def _scanline(intervals: list[tuple[int, int]]) -> tuple[int, int | None, list[dict]]:
    """扫描线：求同一时刻并发运行作业数最大值。

    同一分钟先处理结束（-1）再处理开始（+1）：这样 A 结束时刻 == B 开始时刻
    不会被算成并发，符合调度器「串行接续」的真实口径。
    """
    events: list[tuple[int, int]] = []
    for start, end in intervals:
        events.append((start, 1))
        events.append((end, -1))
    events.sort(key=lambda item: (item[0], item[1]))  # 同一分钟：先结束(-1)再开始(+1)
    running = 0
    peak = 0
    peak_at: int | None = None
    series: list[dict] = []
    for minute, delta in events:
        running += delta
        if delta == 1 and running > peak:
            peak = running
            peak_at = minute
        if not series or series[-1]["minute"] != minute:
            series.append({"minute": minute, "running": running})
        else:
            series[-1]["running"] = running
    return peak, peak_at, series


def compute_schedule(jobs: list[dict], edges: list[dict], mode: str = RunMode.P90.value) -> dict:
    """完整排期：拓扑序 + 前后向递推 + 关键路径 + 并发曲线。"""
    topo = topological_sort(jobs, edges)
    if not topo["ok"]:
        raise AppError(
            topo["reason"],
            422,
            detail={
                "cycle_path": topo.get("cycle_path") or [],
                "cycle_text": topo.get("cycle_text"),
                "settled": topo.get("settled"),
                "total": topo.get("total"),
            },
        )
    by_code, preds, succs = _index(jobs, edges)
    order = topo["order"]
    dur = {code: duration_minutes(by_code[code], mode) for code in by_code}

    est: dict[str, int] = {}
    eft: dict[str, int] = {}
    driver: dict[str, str | None] = {}
    for code in order:
        best = 0
        best_pred: str | None = None
        for edge in preds[code]:
            up = edge["upstream_code"]
            finish = eft[up] + int(edge.get("lag_minutes") or 0)
            if finish > best:
                best = finish
                best_pred = up
        est[code] = best
        eft[code] = best + dur[code]
        driver[code] = best_pred

    total = max(eft.values()) if eft else 0

    lft: dict[str, int] = {}
    lst: dict[str, int] = {}
    for code in reversed(order):
        followers = succs[code]
        if not followers:
            lft[code] = total
        else:
            lft[code] = min(
                lst[edge["downstream_code"]] - int(edge.get("lag_minutes") or 0) for edge in followers
            )
        lst[code] = lft[code] - dur[code]

    floats = {code: lst[code] - est[code] for code in by_code}
    critical_codes = {code for code, value in floats.items() if value == 0}

    # 关键路径：从 EFT 最大的作业沿「决定 EST 的前驱」回溯
    end_code = max(order, key=lambda code: (eft[code], code))
    path: list[str] = []
    cursor: str | None = end_code
    guard = 0
    while cursor is not None and guard <= len(order):
        path.append(cursor)
        cursor = driver[cursor]
        guard += 1
    path.reverse()
    path_total = sum(dur[code] for code in path)
    for index in range(len(path) - 1):
        for edge in succs[path[index]]:
            if edge["downstream_code"] == path[index + 1]:
                path_total += int(edge.get("lag_minutes") or 0)

    peak, peak_at, series = _scanline([(est[code], eft[code]) for code in by_code])

    rows = []
    for code in order:
        job = by_code[code]
        rows.append(
            {
                "code": code,
                "name": job.get("name", code),
                "layer": job.get("layer", ""),
                "owner": job.get("owner", ""),
                "status": job.get("status", JobStatus.ACTIVE.value),
                "duration_minutes": dur[code],
                "es_minutes": est[code],
                "ef_minutes": eft[code],
                "ls_minutes": lst[code],
                "lf_minutes": lft[code],
                "total_float_minutes": floats[code],
                "on_critical": floats[code] == 0,
                "start_clock": minutes_to_clock(est[code]),
                "end_clock": minutes_to_clock(eft[code]),
            }
        )
    rows.sort(key=lambda row: (row["es_minutes"], row["code"]))

    return {
        "mode": mode,
        "valid": True,
        "order": order,
        "layers": topo["layers"],
        "layer_count": topo.get("layer_count", 0),
        "layer_widths": topo.get("layer_widths", {}),
        "job_count": len(by_code),
        "edge_count": sum(len(succs[code]) for code in succs),
        "total_minutes": total,
        "total_clock": human_duration(total),
        "critical_path": path,
        "critical_path_text": " → ".join(path),
        "critical_minutes": path_total,
        "critical_conservation": path_total == total,
        "jobs": rows,
        "critical_jobs": [row for row in rows if row["on_critical"]],
        "peak_concurrency": peak,
        "peak_at_minute": peak_at,
        "peak_at_clock": minutes_to_clock(peak_at) if peak_at is not None else None,
        "concurrency_series": series,
    }


def layered_layout(jobs: list[dict], edges: list[dict]) -> dict:
    """SVG 分层布局：x 轴 = 拓扑层，y 轴 = 层内序号（前端只画不算）。"""
    topo = topological_sort(jobs, edges)
    by_code = {job["code"]: job for job in jobs}
    if not topo["ok"]:
        return {
            "ok": False,
            "reason": topo["reason"],
            "cycle_path": topo.get("cycle_path", []),
            "stations": [],
            "edges": [],
        }
    layers: dict[str, int] = topo["layers"]
    pred_codes: dict[str, list[str]] = {job["code"]: [] for job in jobs}
    for edge in edges:
        up = edge.get("upstream_code")
        down = edge.get("downstream_code")
        if up in pred_codes and down in pred_codes:
            pred_codes[down].append(up)

    raw_buckets: dict[int, list[str]] = {}
    for code, depth in layers.items():
        raw_buckets.setdefault(depth, []).append(code)
    max_depth = max(raw_buckets) if raw_buckets else 0
    max_width = max((len(codes) for codes in raw_buckets.values()), default=1)

    # 层内排序：重心法（barycenter）——按前驱所在行号的均值排，减少交叉线
    row_of: dict[str, int] = {}
    buckets: dict[int, list[str]] = {}
    for depth in sorted(raw_buckets):
        codes = raw_buckets[depth]
        if depth == 0:
            ordered = sorted(codes)
        else:
            def _bary(code: str) -> tuple[float, str]:
                rows = [row_of[up] for up in pred_codes[code] if up in row_of]
                return (sum(rows) / len(rows) if rows else 1e9, code)

            ordered = sorted(codes, key=_bary)
        for index, code in enumerate(ordered):
            row_of[code] = index
        buckets[depth] = ordered

    step_x, step_y = 210, 118
    stations = []
    for depth in sorted(buckets):
        codes = sorted(buckets[depth])
        for index, code in enumerate(codes):
            stations.append(
                {
                    "code": code,
                    "name": by_code[code].get("name", code),
                    "layer": by_code[code].get("layer", ""),
                    "owner": by_code[code].get("owner", ""),
                    "layer_index": depth,
                    "row_index": index,
                    "x": 120 + depth * step_x,
                    "y": 90 + index * step_y,
                    "p50_minutes": duration_minutes(by_code[code], RunMode.P50.value),
                    "p90_minutes": duration_minutes(by_code[code], RunMode.P90.value),
                }
            )
    position = {item["code"]: item for item in stations}
    layout_edges = []
    for edge in edges:
        up = edge.get("upstream_code")
        down = edge.get("downstream_code")
        if up in position and down in position:
            layout_edges.append(
                {
                    "id": edge.get("id"),
                    "from": up,
                    "to": down,
                    "dep_type": edge.get("dep_type", "data"),
                    "lag_minutes": int(edge.get("lag_minutes") or 0),
                    "x1": position[up]["x"],
                    "y1": position[up]["y"],
                    "x2": position[down]["x"],
                    "y2": position[down]["y"],
                }
            )
    return {
        "ok": True,
        "pipeline_code": jobs[0].get("pipeline_code") if jobs else None,
        "layer_count": max_depth + 1,
        "width": 120 + max_depth * step_x + 220,
        "height": max(90 + max_width * step_y, 260),
        "stations": stations,
        "edges": layout_edges,
        "order": topo["order"],
        "layers": layers,
    }
