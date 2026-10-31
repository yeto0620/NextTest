"""NextTest historical replay UI. Scientific state stays in the P2 project store."""

from __future__ import annotations

from html import escape
import math

import pandas as pd
import pydeck as pdk
import streamlit as streamlit

from nexttest.app import nexttest_adapter as ADAPTER


CSS = """
<style>
:root { --nt-ink:#0B1F33; --nt-blue:#175CD3; --nt-teal:#087E8B; --nt-paper:#F6F9FB; --nt-amber:#C77900; --nt-red:#B42318; --nt-line:#CEDAE3; }
.stApp { background:var(--nt-paper); color:var(--nt-ink); }
.block-container { max-width:1120px; padding-top:3.8rem; }
.nt-hero { display:grid; grid-template-columns:minmax(0,1.55fr) minmax(265px,.75fr); gap:1.3rem; align-items:stretch; background:#fff; border:1px solid var(--nt-line); border-top:5px solid var(--nt-blue); padding:1.65rem; margin:.35rem 0 .8rem; }
.nt-hero .eyebrow,.nt-kicker,.nt-window-label { font:700 .74rem Bahnschrift,"Segoe UI",sans-serif; letter-spacing:.12em; color:#075D66; }
.nt-hero h1 { font-family:Bahnschrift,"Microsoft YaHei UI",sans-serif; font-size:clamp(2rem,4vw,3.35rem); line-height:1.18; margin:.5rem 0 .85rem; color:var(--nt-ink); letter-spacing:-.025em; }
.nt-hero p { max-width:650px; font-size:1.02rem; line-height:1.75; margin:0; color:#31465c; }
.nt-badge { display:inline-block; background:#e7f4f3; border:1px solid #a9d1ce; color:#075d66; padding:.33rem .58rem; font-size:.8rem; margin-top:1.1rem; }
.nt-hero-window { border:1px solid #cad7e3; background:linear-gradient(145deg,#f4f8fb,#fff); padding:1rem; display:flex; flex-direction:column; justify-content:space-between; min-height:220px; }
.nt-hero-window .nt-window-title { font:700 .78rem Bahnschrift,"Segoe UI",sans-serif; color:#52677a; letter-spacing:.09em; }
.nt-hero-window .nt-window-question { font:700 1.35rem Bahnschrift,"Microsoft YaHei UI",sans-serif; line-height:1.35; color:var(--nt-ink); margin:.55rem 0; }
.nt-hero-window .nt-window-rule { border-top:1px solid #cbd9e4; margin:.65rem 0; }
.nt-hero-window .nt-window-seal { border:1px dashed #a9701c; background:#fff9eb; color:#77500d; padding:.52rem .65rem; font-size:.82rem; }
.nt-rail { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:.45rem; margin:1.15rem 0 1.45rem; }
.nt-stop { min-width:0; background:#fff; border:1px solid var(--nt-line); border-top:3px solid #b8c8d6; padding:.72rem .75rem; }
.nt-stop strong { display:block; color:var(--nt-ink); font-size:.87rem; }
.nt-stop span { display:block; color:#52677a; font-size:.74rem; margin-top:.3rem; }
.nt-stop.done { border-top-color:var(--nt-teal); }
.nt-stop.current { border-top-color:var(--nt-blue); background:#eef4ff; }
.nt-stop.blocked { border-top-color:var(--nt-red); }
.nt-panel { background:#fff; border:1px solid var(--nt-line); padding:1.18rem 1.3rem; margin:.7rem 0 1rem; }
.nt-panel h3 { margin:.3rem 0 .65rem; font-size:1.22rem; color:var(--nt-ink); }
.nt-panel p { margin:.4rem 0; color:#31465c; line-height:1.7; }
.nt-evidence-window { display:grid; grid-template-columns:1fr 1fr; gap:.55rem; margin:.7rem 0 1rem; }
.nt-evidence-cell { background:#fff; border:1px solid var(--nt-line); border-top:3px solid var(--nt-blue); padding:1rem 1.1rem; min-height:130px; }
.nt-evidence-cell.sealed { border-top-color:var(--nt-amber); background:#fff9eb; }
.nt-evidence-cell.revealed { border-top-color:var(--nt-teal); background:#eef8f6; }
.nt-evidence-cell strong { display:block; color:var(--nt-ink); font:700 clamp(1.35rem,3vw,2rem) Bahnschrift,"Microsoft YaHei UI",sans-serif; margin:.42rem 0; }
.nt-evidence-cell small { display:block; color:#52677a; line-height:1.5; font-size:.78rem; }
.nt-warning { border-left:4px solid var(--nt-amber); background:#fff9eb; padding:.75rem .95rem; line-height:1.65; }
.nt-good { border-left:4px solid var(--nt-teal); background:#eef8f6; padding:.75rem .95rem; line-height:1.65; }
div[data-testid="stForm"] { border-color:var(--nt-line); background:#fff; padding:1.1rem 1.25rem; }
button[kind="primary"], button[kind="primaryFormSubmit"], div[data-testid="stFormSubmitButton"] button { background:var(--nt-blue)!important; border-color:var(--nt-blue)!important; color:#fff!important; }
button { min-height:42px; }
button:focus-visible, input:focus-visible, [role="tab"]:focus-visible { outline:3px solid var(--nt-amber)!important; outline-offset:2px; }
@media (prefers-reduced-motion:reduce) { *,*::before,*::after { animation-duration:.01ms!important; transition-duration:.01ms!important; scroll-behavior:auto!important; } }
@media (max-width:760px) { .nt-hero { grid-template-columns:1fr; padding:1.1rem; } .nt-hero-window { min-height:0; padding:.8rem; display:block; } .nt-hero-window .nt-window-question { font-size:1.05rem; margin:.3rem 0; } .nt-hero-window .nt-window-rule,.nt-hero-window .nt-window-label { display:none; } .nt-hero-window .nt-window-seal { margin-top:.45rem; } .nt-rail { grid-template-columns:repeat(2,minmax(0,1fr)); } .nt-stop:last-child { grid-column:span 2; } }
@media (max-width:450px) { .nt-evidence-window { grid-template-columns:1fr; } .nt-evidence-cell { min-height:105px; } }
.block-container { max-width:1380px; padding-top:2.15rem; }
.nt-hero { position:relative; overflow:hidden; border:1px solid #14526A; border-top:4px solid #52E0D2; border-radius:18px; background:radial-gradient(circle at 74% 34%,#14506A 0%,#0A2941 33%,#061828 78%); padding:2.1rem 2.3rem; box-shadow:0 22px 60px rgba(7,33,52,.18); }
.nt-hero::after { content:""; position:absolute; width:430px; height:430px; right:-120px; top:-210px; border:1px solid rgba(96,229,220,.24); border-radius:50%; box-shadow:0 0 0 62px rgba(96,229,220,.035),0 0 0 126px rgba(96,229,220,.025); pointer-events:none; }
.nt-hero .eyebrow { color:#79E6DF; }
.nt-hero h1 { color:#F8FCFF; font-size:clamp(2.4rem,4.8vw,4.4rem); max-width:750px; }
.nt-hero p { color:#D2E4EF; max-width:690px; }
.nt-hero .nt-badge { color:#C3F4EC; background:#124A59; border-color:#2F8690; border-radius:999px; }
.nt-hero-window { position:relative; z-index:1; min-height:245px; color:#E9F8FA; background:linear-gradient(135deg,rgba(24,74,93,.8),rgba(12,35,59,.72)); border:1px solid rgba(119,222,224,.36); border-radius:14px; backdrop-filter:blur(8px); }
.nt-hero-window .nt-window-title,.nt-hero-window .nt-window-label { color:#9BDDDD; }
.nt-hero-window .nt-window-question { color:#F4FCFE; font-size:1.6rem; }
.nt-hero-window .nt-window-rule { border-color:rgba(158,218,223,.35); }
.nt-hero-window .nt-window-seal { color:#FFE4A8; background:rgba(155,101,28,.19); border-color:#C99B51; border-radius:8px; }
.nt-visual-head { display:flex; align-items:flex-end; justify-content:space-between; gap:1rem; margin:1.6rem 0 .5rem; }
.nt-visual-head h2 { margin:.2rem 0; color:#09253C; font:700 clamp(1.35rem,2.4vw,2rem) Bahnschrift,"Microsoft YaHei UI",sans-serif; }
.nt-visual-head p { margin:0; color:#4C6476; font-size:.91rem; }
.nt-visual-kicker { color:#087E8B; font:700 .73rem Bahnschrift,"Segoe UI",sans-serif; letter-spacing:.16em; }
.nt-visual-note { background:#E7F3F5; border-left:3px solid #0C8293; padding:.66rem .82rem; color:#24485A; font-size:.86rem; line-height:1.6; margin:.25rem 0 1rem; }
div[data-testid="stDeckGlJsonChart"] { border:1px solid #B9D6DB; border-radius:16px; overflow:hidden; box-shadow:0 12px 30px rgba(7,45,70,.1); background:#0B2637; }
@media (max-width:760px) { .nt-hero { padding:1.4rem; } .nt-visual-head { display:block; } }
</style>
"""

STRATEGY_LABELS = {
    "random": "随机选一组（对照）",
    "greedy_prediction": "优先试预测最好的",
    "max_disagreement": "优先试模型意见最不一致的",
}
GOAL_LABELS = {"maximize": "尽量提高强度", "minimize": "尽量降低目标值"}
CONTROL_LABELS = {
    "Cement": "水泥", "BlastFurnaceSlag": "矿渣", "FlyAsh": "粉煤灰",
    "Water": "水", "Superplasticizer": "减水剂", "CoarseAggregate": "粗骨料",
    "FineAggregate": "细骨料", "Age": "养护龄期",
}
STATUS_LABELS = {
    "ready": "可生成下一次建议", "awaiting_user_confirmation": "建议已生成，等待揭示历史结果",
    "budget_exhausted": "预算已用完", "candidate_pool_empty": "可选历史方案已用完",
    "release_uncertain": "结果释放状态不确定", "update_uncertain": "模型更新状态不确定",
    "update_failed": "模型更新失败",
}
STOP_STATES = {"release_uncertain", "update_uncertain", "update_failed"}


@streamlit.cache_data(show_spinner=False)
def _observed_landscape() -> dict:
    return ADAPTER.observed_landscape()


def _landscape(st, pending: dict | None = None) -> None:
    """Show only measured training rows; hidden candidate and test labels stay absent."""
    try:
        payload = _observed_landscape()
        if payload.get("scope") != "observed_training_only" or payload.get("count") != 252:
            raise ValueError("Observed data contract changed")
        rows = payload["rows"]
    except Exception:  # noqa: BLE001
        st.warning("三维配方空间暂不可用。历史回放功能仍可继续。")
        return

    st.markdown('<div class="nt-visual-head"><div><span class="nt-visual-kicker">OBSERVED MATERIAL SPACE / 252 RECORDS</span>'
                '<h2>转动配方空间，先看已有证据</h2></div>'
                '<p>拖动旋转 · 滚轮缩放 · 悬停查看实测</p></div>', unsafe_allow_html=True)
    choices = {
        "Cement": "水泥", "Water": "水", "BlastFurnaceSlag": "矿渣", "FlyAsh": "粉煤灰",
        "Superplasticizer": "减水剂", "CoarseAggregate": "粗骨料", "FineAggregate": "细骨料",
    }
    x_col, y_col, filter_col = st.columns(3)
    with x_col:
        x_key = st.selectbox("横轴 · 配方变量", list(choices), index=0, format_func=choices.get, key="nt_3d_x")
    with y_col:
        y_key = st.selectbox("纵轴 · 配方变量", list(choices), index=1, format_func=choices.get, key="nt_3d_y")
    with filter_col:
        minimum_strength = st.slider(
            "筛选实测强度 ≥ (MPa)", 0, int(math.ceil(max(float(r["CompressiveStrength"]) for r in rows) / 5) * 5),
            0, step=5, key="nt_3d_min_strength",
        )
    if x_key == y_key:
        st.info("横轴与纵轴请选择不同原料，才能看到配方之间的差异。")
        return
    x_values = [float(row[x_key]) for row in rows]
    y_values = [float(row[y_key]) for row in rows]
    strengths = [float(row["CompressiveStrength"]) for row in rows]
    x_min, x_max = min(x_values), max(x_values)
    y_min, y_max = min(y_values), max(y_values)
    s_min, s_max = min(strengths), max(strengths)
    chart_rows = []
    for row, xv, yv, strength in zip(rows, x_values, y_values, strengths):
        if strength < minimum_strength:
            continue
        t = (strength - s_min) / max(s_max - s_min, 1e-9)
        color = [round(28 + 221 * t), round(113 + 92 * (1 - abs(t - .5) * 2)), round(206 - 132 * t), 215]
        chart_rows.append({
            "x": -60 + 120 * (xv - x_min) / max(x_max - x_min, 1e-9),
            "y": -60 + 120 * (yv - y_min) / max(y_max - y_min, 1e-9),
            "height": 4 + strength * .85,
            "color": color,
            "recipe": str(row["_row_id"]),
            "x_value": round(xv, 1), "y_value": round(yv, 1),
            "reading": f"历史实测 {strength:.2f} MPa",
        })
    if not chart_rows:
        st.info("这个阈值下没有已知训练记录，请调低筛选值。")
        return
    grid_rows = ([{"path": [[v, -66, 0], [v, 66, 0]]} for v in range(-60, 61, 30)]
                 + [{"path": [[-66, v, 0], [66, v, 0]]} for v in range(-60, 61, 30)])
    layers = [
        pdk.Layer("PathLayer", grid_rows, get_path="path", get_color=[49, 104, 125],
                  get_width=1, width_min_pixels=1),
        pdk.Layer("ColumnLayer", chart_rows, get_position="[x, y]", get_elevation="height",
                  get_fill_color="color", radius=1.85, disk_resolution=8, extruded=True,
                  pickable=True, auto_highlight=True, elevation_scale=1),
    ]
    suggestion_visible = False
    if pending:
        try:
            controls = pending["controls"]
            suggested_x, suggested_y = float(controls[x_key]), float(controls[y_key])
            prediction = float(pending["prediction"])
            if not all(math.isfinite(v) for v in (suggested_x, suggested_y, prediction)):
                raise ValueError("non-finite suggestion")
            suggestion = [{
                "x": -60 + 120 * (suggested_x - x_min) / max(x_max - x_min, 1e-9),
                "y": -60 + 120 * (suggested_y - y_min) / max(y_max - y_min, 1e-9),
                "height": 4 + max(0, prediction) * .85,
                "color": [255, 194, 67, 255],
                "recipe": f"待验证 · {pending['row_id']}",
                "x_value": round(suggested_x, 1), "y_value": round(suggested_y, 1),
                "reading": f"模型预测 {prediction:.2f} MPa；实测尚未揭示",
            }]
            layers.append(pdk.Layer("ColumnLayer", suggestion, get_position="[x, y]",
                                    get_elevation="height", get_fill_color="color", radius=4.1,
                                    disk_resolution=12, extruded=True, pickable=True,
                                    auto_highlight=True, elevation_scale=1))
            suggestion_visible = True
        except (KeyError, TypeError, ValueError):
            pass
    deck = pdk.Deck(
        layers=layers,
        views=[pdk.View(type="OrbitView", controller=True)],
        initial_view_state=pdk.ViewState(target=[0, 0, 25], zoom=1.85, rotation_x=43, rotation_orbit=-35),
        map_style=None,
        parameters={"clearColor": [0.025, 0.085, 0.14, 1]},
        height=430,
        tooltip={"html": "<b>{recipe}</b><br/>横轴 {x_value} kg/m³ · 纵轴 {y_value} kg/m³<br/>{reading}",
                 "style": {"backgroundColor": "#0A2941", "color": "#F8FCFF", "fontSize": "13px"}},
    )
    st.pydeck_chart(deck, width="stretch", height=430)
    suggestion_note = ' 琥珀色宽柱是待验证方案的<strong>模型预测</strong>，真实强度仍隐藏；筛选只作用于已知记录。' if suggestion_visible else ''
    st.markdown(f'<div class="nt-visual-note">当前显示 {len(chart_rows)} / 252 条已知记录 · 横轴：{choices[x_key]}（kg/m³） · 纵轴：{choices[y_key]}（kg/m³） · 柱高与颜色：历史实测强度（MPa）。'
                f'{suggestion_note}已知图层只含训练记录；独立测试的真实强度不进入图中。图展示关联，不表示因果关系。</div>',
                unsafe_allow_html=True)


def _audit_ok(view: dict) -> bool:
    snapshot, audit = view["snapshot"], view["audit"]
    return (audit.get("test_unchanged") is True and audit.get("models_present") is True
            and audit.get("status") == snapshot["status"])


def _rail(status: str | None, revealed: int) -> str:
    steps = ["已有证据", "目标与预算", "下一次建议", "历史反馈", "证据更新"]
    if status is None:
        current = 0
    elif status == "awaiting_user_confirmation":
        current = 3
    elif revealed:
        current = 4
    else:
        current = 2
    cards = []
    for index, label in enumerate(steps):
        kind = "done" if index < current else "current" if index == current else "waiting"
        if status in STOP_STATES and index == current:
            kind = "blocked"
        state = "已完成" if kind == "done" else "当前" if kind == "current" else "需人工核查" if kind == "blocked" else "等待"
        cards.append(f'<div class="nt-stop {kind}"><strong>{index+1:02d} {label}</strong><span>{state}</span></div>')
    return '<div class="nt-rail">' + "".join(cards) + "</div>"


def _technical(st, view: dict) -> None:
    snapshot, audit = view["snapshot"], view["audit"]
    with st.expander("科研详情与数据来源", expanded=False):
        st.write("数据：UCI Concrete，固定 Age=28 历史子集；许可 CC BY 4.0。")
        st.write(f"训练记录 {snapshot['observed_count']} 条 · 剩余历史候选 {snapshot['candidate_count']} 条 · 独立留出 {snapshot['test_count']} 条")
        st.caption("留出集不参与推荐或反馈；模型是 CPU 上的随机森林回归。分歧值是树间预测标准差，不是概率或置信区间。")
        st.code(f"项目 {snapshot['project_id']}\n数据 SHA {snapshot['source_canonical_sha256']}\n切分 SHA {snapshot['split_sha256']}\n模型 SHA {snapshot['current_model_sha']}\n事件链 SHA {audit['event_chain_sha256']}")


def _history(st, view: dict) -> None:
    history = view["history"]
    st.markdown("### 已揭示的历史结果")
    if not history:
        st.info("还没有揭示结果。预测值只是模型估计，不能计作已验证结果。")
        return
    rows = [{"第几次": x["round"], "历史方案": x["row_id"], "揭示前预测 (MPa)": round(x["prediction"], 2),
             "历史实测 (MPa)": round(x["revealed_target"], 2), "本次绝对误差 (MPa)": round(x["absolute_error"], 2)} for x in history]
    last = history[-1]
    st.markdown(
        '<div class="nt-evidence-window" aria-label="最近一次历史回放的预测与实测对照">'
        f'<div class="nt-evidence-cell"><span class="nt-window-label">揭示前的模型预测</span><strong>{last["prediction"]:.2f} MPa</strong>'
        '<small>这是事先保存的估计，不是测量结果。</small></div>'
        f'<div class="nt-evidence-cell revealed"><span class="nt-window-label">已揭示的历史实测</span><strong>{last["revealed_target"]:.2f} MPa</strong>'
        '<small>这条历史记录已加入后续训练。</small></div></div>', unsafe_allow_html=True,
    )
    st.caption(f'第 {last["round"]} 次回放 · 绝对误差 {last["absolute_error"]:.2f} MPa。单次误差不能证明推荐方法更优。')
    with st.expander("查看每一次历史回放", expanded=False):
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def _report(view: dict) -> str:
    snap, audit = view["snapshot"], view["audit"]
    lines = ["# NextTest 历史数据回放记录", "", "本报告仅记录 UCI Concrete Age=28 历史数据回放，不代表新做的物理试验。", "",
             f"- 项目：`{snap['project_id']}`", f"- 状态：{STATUS_LABELS.get(snap['status'], snap['status'])}",
             f"- 目标：{GOAL_LABELS[snap['goal']]}", f"- 方法：{STRATEGY_LABELS[snap['strategy']]}",
             f"- 预算：{snap['budget']} 次；已揭示：{snap['revealed_count']} 次", "",
             "| 轮次 | 历史方案 | 揭示前预测 MPa | 历史实测 MPa | 绝对误差 MPa |",
             "|---:|---|---:|---:|---:|"]
    for row in view["history"]:
        lines.append(f"| {row['round']} | {row['row_id']} | {row['prediction']:.3f} | {row['revealed_target']:.3f} | {row['absolute_error']:.3f} |")
    lines += ["", f"- 数据 SHA：`{snap['source_canonical_sha256']}`", f"- 切分 SHA：`{snap['split_sha256']}`",
              f"- 事件链 SHA：`{audit['event_chain_sha256']}`", "", "边界：这是固定历史数据上的探索性回放；没有新物理实验、策略优越性或工业部署验证。", ""]
    return "\n".join(lines)


def render(st) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<div class="nt-hero"><div class="nt-hero-copy"><div class="eyebrow">NEXTTEST / 历史数据回放</div>'
                '<h1>让下一次试验更有价值</h1>'
                '<p>预算有限时，先验证哪一组配方？NextTest 根据已有记录提出建议；揭示历史结果后，再更新下一次选择。</p>'
                '<span class="nt-badge">当前可体验：UCI 混凝土强度 · 28 天 · 历史回放</span></div>'
                '<div class="nt-hero-window"><div><span class="nt-window-title">一张实验决策单</span>'
                '<div class="nt-window-question">先看建议，<br>再看结果。</div></div>'
                '<div><div class="nt-window-rule"></div><span class="nt-window-label">可见：配方与预测</span><br>'
                '<span class="nt-window-label">揭示后：历史实测</span>'
                '<div class="nt-window-seal">结果在确认前保持隐藏</div></div></div></div>', unsafe_allow_html=True)
    st.caption("演示使用已公开的历史数据；“揭示结果”不等于完成新试验。目前尚不支持自有 CSV 上传或现场采集。")
    pid = st.session_state.get("nexttest_project_id")
    view = None
    if pid:
        try:
            view = ADAPTER.inspect(pid)
        except Exception:  # noqa: BLE001
            st.error("项目记录暂时无法通过只读核查。请核对项目编号和本地计算环境；页面不会自动重试或改写记录。")
    pending_for_chart = view.get("pending") if view and _audit_ok(view) else None
    _landscape(st, pending_for_chart)
    status = view["snapshot"]["status"] if view else None
    revealed = view["snapshot"]["revealed_count"] if view else 0
    st.markdown(_rail(status, revealed), unsafe_allow_html=True)

    if view is None:
        st.markdown("### 从固定示例开始")
        facts_col, setup_col = st.columns([0.84, 1.16], gap="large")
        with facts_col:
            st.markdown('<div class="nt-panel"><div class="nt-kicker">已知的事实</div><h3>混凝土配方与 28 天抗压强度</h3>'
                        '<p>252 条已有记录用于训练，89 组历史配方等待选择，84 条独立留出用于评估。推荐时看不到待选方案的真实强度。</p></div>', unsafe_allow_html=True)
            st.caption("当前演示只使用固定公开数据；留出记录不参与推荐。")
        with setup_col:
            with st.form("nexttest_create"):
                goal = st.radio("这次想做什么", ["maximize", "minimize"], format_func=lambda x: GOAL_LABELS[x], horizontal=True)
                budget = st.slider("还能验证几组配方", 1, 20, 3)
                strategy = st.selectbox("推荐方法", list(STRATEGY_LABELS), index=1, format_func=lambda x: STRATEGY_LABELS[x])
                use_threshold = st.checkbox("设置参考强度目标（可选）", value=False)
                threshold = st.number_input("参考强度 (MPa)", min_value=0.0, max_value=150.0, value=40.0, step=1.0, disabled=not use_threshold)
                submit = st.form_submit_button("开始历史回放", type="primary")
            st.caption("随机方法是对照；“预测最好”看模型估计；“意见不一致”优先补充模型最拿不准的方案。三者都是探索方法。")
        if submit:
            pid = ADAPTER.new_project_id()
            st.session_state["nexttest_project_id"] = pid
            try:
                view = ADAPTER.create(goal=goal, threshold=threshold if use_threshold else None,
                                      budget=budget, strategy=strategy, project_id=pid)
                st.success("历史回放已建立。现在可以生成第一条建议。")
            except ADAPTER.NextTestUncertain:
                st.warning("创建状态不确定。已保留项目编号；请使用只读恢复核查，勿重复创建。")
            except Exception:  # noqa: BLE001
                st.error("创建未完成。请核对本地计算环境和固定数据；不会自动重试。")
        with st.expander("继续已有历史回放", expanded=False):
            resume_id = st.text_input("输入项目编号", placeholder="p2_ 后接 32 位小写字母数字")
            if st.button("只读打开项目"):
                try:
                    view = ADAPTER.inspect(resume_id.strip())
                    st.session_state["nexttest_project_id"] = resume_id.strip()
                except Exception:  # noqa: BLE001
                    st.error("项目未找到或未通过只读核查。不会改写原记录。")
        if view is None:
            return

    snapshot = view["snapshot"]
    if not _audit_ok(view):
        st.error("项目证据检查未通过。推荐与结果展示已阻断。")
        return

    st.markdown(f"### 当前任务 · {STATUS_LABELS.get(snapshot['status'], '需人工核查')}")
    st.caption(f"项目编号：`{escape(snapshot['project_id'])}` · 复制它可在刷新页面后继续查看")
    m1, m2, m3 = st.columns(3)
    m1.markdown(f"**目标**  \n{GOAL_LABELS[snapshot['goal']]}")
    m2.markdown(f"**剩余预算**  \n{snapshot['remaining_budget']} / {snapshot['budget']} 次")
    m3.markdown(f"**推荐方法**  \n{STRATEGY_LABELS[snapshot['strategy']]}")
    st.markdown("---")

    if snapshot["status"] == "ready":
        st.markdown("### 下一次先验证哪一组？")
        st.write("系统只用已知记录训练，并从还没揭示真实结果的历史配方中选择一组。")
        if st.button("生成下一次建议", type="primary"):
            try:
                view = ADAPTER.recommend(snapshot["project_id"])
                snapshot = view["snapshot"]
                if not _audit_ok(view):
                    st.error("项目证据检查未通过。推荐与结果展示已阻断。")
                    return
                st.rerun()
            except ADAPTER.NextTestUncertain:
                st.warning("建议生成状态不确定。请只读打开项目核查；不会自动重试。")
            except Exception:  # noqa: BLE001
                st.error("建议未生成。请核查项目状态；不会自动重试。")

    if not _audit_ok(view):
        st.error("项目证据检查未通过。推荐与结果展示已阻断。")
        return

    if snapshot["status"] == "awaiting_user_confirmation":
        pending = view.get("pending")
        if not isinstance(pending, dict):
            st.error("建议记录缺失。请只读核查项目，不能揭示结果。")
            return
        st.markdown('<div class="nt-panel"><div class="nt-kicker">下一次建议</div><h3>建议先验证这组历史配方</h3></div>', unsafe_allow_html=True)
        st.markdown(f"**历史方案编号：** `{escape(pending['row_id'])}`")
        st.markdown(
            '<div class="nt-evidence-window" aria-label="建议方案的预测与尚未揭示的历史结果">'
            f'<div class="nt-evidence-cell"><span class="nt-window-label">揭示前预测强度</span><strong>{pending["prediction"]:.2f} MPa</strong>'
            '<small>模型估计，尚未验证。</small></div>'
            '<div class="nt-evidence-cell sealed"><span class="nt-window-label">历史实测强度</span><strong>尚未揭示</strong>'
            '<small>确认回放后才显示。</small></div></div>', unsafe_allow_html=True,
        )
        if pending.get("disagreement") is not None:
            st.caption(f"模型分歧指标：{pending['disagreement']:.2f} MPa；它不是成功概率或置信区间。")
        st.write("推荐依据：" + ("树模型对这组配方的估计最不一致，值得优先验证。" if snapshot["strategy"] == "max_disagreement" else
                         "模型预测的目标值在可选配方中最靠前。" if snapshot["strategy"] == "greedy_prediction" else
                         "按固定随机种子选取，用作对照。"))
        controls = pending["controls"]
        st.dataframe(pd.DataFrame([{"原料 / 条件": CONTROL_LABELS.get(k, k), "数值": round(v, 2),
                                    "单位": "天" if k == "Age" else "kg/m³"} for k, v in controls.items()]),
                     hide_index=True, width="stretch")
        st.markdown('<div class="nt-warning">这组方案的历史实测强度仍被隐藏。点击下方按钮才会揭示；这是历史数据回放，不是新的实体试验。</div>', unsafe_allow_html=True)
        if st.button("执行历史回放并揭示结果", type="primary"):
            try:
                view = ADAPTER.reveal(snapshot["project_id"], pending["recommendation_id"])
                snapshot = view["snapshot"]
                if not _audit_ok(view):
                    st.error("项目证据检查未通过。推荐与结果展示已阻断。")
                    return
                st.rerun()
            except ADAPTER.NextTestUncertain:
                st.warning("结果可能已经读取，但尚未完整保存。本次不会自动重试。请只读打开项目核查。")
            except Exception:  # noqa: BLE001
                st.error("结果揭示或模型更新未完成。请只读核查项目；不会自动重试。")

    if not _audit_ok(view):
        st.error("项目证据检查未通过。推荐与结果展示已阻断。")
        return

    if snapshot["status"] in STOP_STATES:
        st.markdown('<div class="nt-warning">本任务处于不确定或失败状态。为避免重复揭示同一历史结果，页面不会自动重试。请保留项目编号和证据记录。</div>', unsafe_allow_html=True)
    elif snapshot["status"] in {"budget_exhausted", "candidate_pool_empty"}:
        st.info("本轮历史回放结束。可下载记录，或创建一个全新任务。")

    _history(st, view)
    _technical(st, view)
    st.download_button("导出证据报告", _report(view), file_name=f"nexttest_{snapshot['project_id']}.md", mime="text/markdown")
    st.caption("项目来源与状态可核账。单次回放不证明推荐方法优于其他方法，也不代表工业场景验证。")
    if st.button("开始新的历史回放"):
        st.session_state.pop("nexttest_project_id", None)
        st.rerun()
