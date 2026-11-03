#!/usr/bin/env python3
"""Turn a prepared segment work package into a compact agent brief so segment
agents spend their context on watching and reasoning rather than parsing
generated JSON (work-package.json carries hundreds of sha256 digests).

  python scripts/segment_brief.py PROJECT_DIR SEGMENT_ID

Writes segments/SEGMENT_ID/brief.md with the scene table, the dialogue/on-screen
text timeline, the current bible summary, and a sha-free evidence index.
"""
import json
import sys
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

RULES = [
    "只描述画面里看得见的东西。对白、字幕、剧情简介和模型记忆都不是视觉证据。",
    "写每条旁白前先问：这条补充了声轨没有传达的哪一处可见信息？不要复述对白。",
    "主语+动作。人物用 bible 里的既有 id 与 safe_label；同一个人不要另起代号，在 bible_proposals 里写 aliases 合并建议。",
    "每个 observation 必须引用 work-package 里的 evidence id；连续动作要有起始/过程/结果三帧以上。",
    "本段每个 scene 至少一条 observation；相邻 observation 之间不得留下超过 90 秒的空档。",
    "画面稳定、声音已足够时写 sound_sufficient 覆盖记录（含 visible_state / stability_reason / sound_conveys），这种记录不能生成旁白。",
    "同一帧同时呈现多个主体时，允许按主体分别建立 observation（不同主体引用同一帧集不算证据回收）。",
    "只编辑 analysis-input.json，不要新建任何脚本或别的文件。",
]

def unwrap(value, key):
    if isinstance(value, dict):
        return value.get(key) or []
    return value or []

def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    root = Path(sys.argv[1]).resolve()
    seg = sys.argv[2]
    d = root / "segments" / seg
    wp = json.loads((d / "work-package.json").read_text(encoding="utf-8-sig"))
    ev = wp["evidence"]
    by_time = sorted(ev, key=lambda x: x["timestamp"])
    lines = [f"# {seg}  分析简报",
             f"区间：{wp['start']:.2f}s - {wp['end']:.2f}s（{(wp['end'] - wp['start']) / 60:.2f} 分钟），前后各 {wp.get('overlap_before', 0)}s 上下文重叠。",
             f"证据帧：{len(ev)} 张，位于 segments/{seg}/evidence/，evidence id 与文件名序号一致（ev-0007 = frame-0007-*.jpg）。",
             "", "## 联络表（每格左上角是时间码）"]
    sheets = sorted(p.name for p in (d / "sheets").glob("sheet-*.jpg")) if (d / "sheets").is_dir() else []
    lines += [f"- sheets/{s}" for s in sheets] or ["- （尚未生成，先运行 scripts/contact_sheet.py）"]
    lines += ["", "## 规则", *[f"- {r}" for r in RULES], "", "## 场景表（本段）"]
    for s in wp["shots"]:
        lines.append(f"- {s['id']}  {float(s['start']):.1f}-{float(s['end']):.1f}")
    lines += ["", "## 对白与画面文字时间轴（仅供落位与线索，不可复述）"]
    for t in wp["transcript_context"]:
        lines.append(f"- {t['id']}  {float(t['start']):.1f}-{float(t['end']):.1f}  {str(t.get('text',''))[:80]}")
    bible = wp.get("bible_snapshot") or {}
    lines += ["", "## 当前圣经（沿用这些 ID；发现同一个人不要另起代号，在 bible_proposals 里写 aliases 合并建议）"]
    for c in unwrap(bible.get("characters"), "characters"):
        lines.append(f"- {c.get('id')} {c.get('safe_label')}｜首现 {c.get('first_visual_appearance')}｜{str(c.get('visual_description'))[:150]}")
    lines.append("地点：" + "；".join(f"{l.get('id')}={l.get('safe_label')}" for l in unwrap(bible.get("locations"), "locations")))
    lines.append("物件：" + "；".join(f"{o.get('id')}={o.get('safe_label')}" for o in unwrap(bible.get("objects"), "objects")))
    state = bible.get("story-state") or {}
    if isinstance(state, dict) and state:
        lines.append("上段结束时的局面：")
        for key, value in state.items():
            lines.append(f"- {key}: {str(value)[:200]}")
    lines += ["", "## 证据帧索引", "ev-id | 时间 | 文件"]
    for e in by_time:
        lines.append(f"{e['id']} | {float(e['timestamp']):.2f} | {Path(e['path']).name}")
    (d / "brief.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"segment": seg, "brief": f"segments/{seg}/brief.md",
                      "bytes": (d / "brief.md").stat().st_size, "sheets": len(sheets),
                      "evidence": len(ev)}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
