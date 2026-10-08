"""動詞の世界（委任書 2026-10-04、土台 3380344）。

世界と研究者の台帳だけを外側から包む。abm/・模型の選び方・学習は変えない。
名前と attach は shopworld のシールと link の位置に置く。シールは置かない。
Schuler の項目別頻度は出典確認済みの表を別ファイルで受け取る。推測では埋めない。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from hashlib import sha256
from math import isclose
from pathlib import Path
from random import Random

REG, ATTACH, PAST_PATH = "REG", "attach", "0.0.0"
NAMES = tuple(f"V{i:02d}" for i in range(1, 49))
NOVEL_NAMES = NAMES[40:]
PAST_PREDICATES = (REG, *(f"IRR_{k}" for k in range(1, 9)))
NEW_PREDICATES = (*NAMES, *PAST_PREDICATES, ATTACH)
EXTRA_KEYS = ("verb_name", "verb_class", "correct_past", "held_out_is_past")
INFO: dict = {}
IDS: dict = {}
CFG: dict = {}
CTX: dict = {}
STATS: dict = {}


@dataclass(frozen=True)
class Verb:
    name: str
    verb_class: str
    past: str
    probability: float


def training_items(variant="default", frequency_file=None) -> tuple[Verb, ...]:
    """模型の設定・状態を受け取らない、事前固定の刺激分布。"""
    if variant == "default":
        h32 = sum(1 / k for k in range(1, 33))
        h8 = sum(1 / k for k in range(1, 9))
        return tuple(Verb(f"V{j:02d}", "regular", REG, .30 / (h32 * j)) for j in range(1, 33)) + tuple(
            Verb(f"V{k + 32:02d}", "irregular", f"IRR_{k}", .70 / (h8 * k)) for k in range(1, 9))
    if variant not in ("schuler54", "schuler36"):
        raise ValueError(f"未知の動詞の変種: {variant}")
    if frequency_file is None:
        raise ValueError("Schuler の項目別出現数は未確定。出典を確かめた --verb-frequencies の表が必要（2016年本文と後年の表が不一致）")
    data = json.loads(Path(frequency_file).read_text(encoding="utf-8"))
    if not isinstance(data.get("source"), str) or not data["source"].strip():
        raise ValueError("Schuler の頻度表には source が必要")
    counts = data.get(variant)
    if not isinstance(counts, list) or len(counts) != 9 or any(type(n) is not int or n <= 0 for n in counts):
        raise ValueError("Schuler の頻度表は、頻度順位の順に9個の正の整数を指定する")
    if counts != sorted(counts, reverse=True):
        raise ValueError("Schuler の頻度表は頻度の降順で指定する")
    nreg = 5 if variant == "schuler54" else 3
    target = .75 if nreg == 5 else 28 / 48
    if not isclose(sum(counts[:nreg]) / sum(counts), target, abs_tol=5e-5):
        raise ValueError("Schuler の頻度表の REG 比が委任書の75%／58.3%に合わない")
    total = sum(counts)
    return tuple(Verb(f"V{j:02d}", "regular" if j <= nreg else "irregular",
                      REG if j <= nreg else f"IRR_{j - nreg}", n / total)
                 for j, n in enumerate(counts, 1))


def verb_rng(run_seed, trial_index) -> Random:
    """世界の乱数とは別の流れ。一試行一抽選。"""
    return Random(int.from_bytes(sha256(f"{run_seed}\x1f{trial_index}\x1fverb".encode()).digest(), "big"))


def draw_verb(run_seed, trial_index, items=None) -> Verb:
    items = CFG["items"] if items is None else items
    u = verb_rng(run_seed, trial_index).random()
    cumulative = 0.0
    for item in items:
        cumulative += item.probability
        if u < cumulative:
            return item
    if not isclose(cumulative, 1.0, abs_tol=1e-12):
        raise ValueError("動詞の確率の合計が1でない")
    return items[-1]


def build(tr, run_seed, trial_index, *, verb: Verb):
    """元の M1 場面に名前・link・過去形を置く。ほかの関係と乱数は変えない。"""
    import abm.world as w
    from abm.domains import Relation, RelationGraph
    if tr.motif != "M1":
        raise ValueError("動詞の世界の種は M1 一型だけにする")
    if verb.name not in NAMES or verb.past not in PAST_PREDICATES:
        raise ValueError("動詞の名前か過去形が固定辞書にない")
    past_id = w.opaque_id(run_seed, trial_index, f"relation:tree:{PAST_PATH}")
    root_id = w.opaque_id(run_seed, trial_index, "relation:tree:root")
    a_id = w.opaque_id(run_seed, trial_index, "entity:a")
    by_id = {r.relation_id: r for r in tr.G_star.relations}
    if past_id not in by_id or by_id[past_id].predicate != "hold" or root_id not in by_id:
        raise ValueError("過去形（0.0.0 の hold）か根が元の場面にない")
    # 関係 ID の役割も shopworld と同じ。意味の識別に名前や正解を渡さない。
    name_id = w.opaque_id(run_seed, trial_index, "relation:shop:sig")
    link_id = w.opaque_id(run_seed, trial_index, "relation:shop:link")
    relations = tuple(Relation(r.relation_id, verb.past, r.arguments, r.attributes)
                      if r.relation_id == past_id else r for r in tr.G_star.relations) + (
        Relation(name_id, verb.name, (a_id,)), Relation(link_id, ATTACH, (name_id, root_id)))
    held_id = tr.held_out_edge.relation_id
    held = next(r for r in relations if r.relation_id == held_id)
    graph = RelationGraph(tr.G_star.graph_id, tr.G_star.entities, relations)
    visible = tuple(r for r in relations if r.relation_id != held_id)
    if tuple(r.relation_id for r in visible[:-2]) != tuple(r.relation_id for r in tr.target_graph_partial.relations):
        raise ValueError("見えている関係の順序が元の世界と違う")
    ids = frozenset(r.relation_id for r in visible)
    entities = {e.entity_id for e in graph.entities}
    reachable = frozenset(a for r in visible for a in r.arguments if a not in ids and a in entities)
    partial = RelationGraph(tr.target_graph_partial.graph_id,
                            tuple(e for e in graph.entities if e.entity_id in reachable), visible)
    info = dict(verb_name=verb.name, verb_class=verb.verb_class, correct_past=verb.past,
                held_out_is_past=held_id == past_id, past_id=past_id, name_id=name_id, link_id=link_id, root_id=root_id)
    return replace(tr, G_star=graph, target_graph_partial=partial, held_out_edge=held), info


def verb_trial(original, run_seed, trial_index, agent_ids, *, seed, holdout_include_second_order=False):
    tr = original(run_seed, trial_index, agent_ids, seed=seed, holdout_include_second_order=holdout_include_second_order)
    if CFG.get("door_p") is not None:
        # 名前を足す前に、お店と同じ候補・別乱数で伏せ辺を選ぶ。
        if holdout_include_second_order:
            raise ValueError("--shop-door-p は二階を伏せない設定（hide1）で使う")
        import shopworld
        tr = shopworld.rehide(tr, run_seed, trial_index, CFG["door_p"])
    out, info = build(tr, run_seed, trial_index, verb=draw_verb(run_seed, trial_index))
    INFO[out.G_star.graph_id] = info
    IDS[info["name_id"]] = "name"
    IDS[info["link_id"]] = "link"
    STATS["trials"] = STATS.get("trials", 0) + 1
    STATS["held_out_is_past"] = STATS.get("held_out_is_past", 0) + int(info["held_out_is_past"])
    return out


def install(*, variant="default", frequency_file=None, door_p=None):
    """v39・選び方の旗の後、probe-world の前に入れる。"""
    import abm.ledger as ledger
    import abm.loop as loop
    import abm.seed as seedmod
    import abm.world as w
    INFO.clear()
    IDS.clear()
    CTX.clear()
    STATS.clear()
    CFG.clear()
    CFG.update(items=training_items(variant, frequency_file), variant=variant, door_p=door_p)
    original = w.generate_trial
    CTX["orig_gen"] = original

    def generate_trial(run_seed, trial_index, agent_ids, *, seed, holdout_include_second_order=False):
        return verb_trial(original, run_seed, trial_index, agent_ids, seed=seed,
                          holdout_include_second_order=holdout_include_second_order)

    w.generate_trial = generate_trial
    real_hop = seedmod.higher_order_predicates

    def higher_order_predicates(seed):
        return frozenset(real_hop(seed)) | {ATTACH}

    seedmod.higher_order_predicates = higher_order_predicates
    import sweep
    if getattr(sweep, "higher_order_predicates", None) is real_hop:
        sweep.higher_order_predicates = higher_order_predicates
    real_record = loop._ledger_record

    def _ledger_record(agent_id, trial, *a, **kw):
        rec, snapshot, fingerprint = real_record(agent_id, trial, *a, **kw)
        info = INFO[trial.G_star.graph_id]
        return {**rec, **{key: info[key] for key in EXTRA_KEYS}}, snapshot, fingerprint

    loop._ledger_record = _ledger_record
    real_append = ledger.Ledger.append

    def append(self, record):
        extra = {key: record[key] for key in EXTRA_KEYS if key in record}
        if not extra:
            return real_append(self, record)
        base = {key: val for key, val in record.items() if key not in extra}
        expected = frozenset(ledger.LEDGER_FIELDS)
        if frozenset(base) != expected or len(extra) != len(EXTRA_KEYS):
            raise ValueError("動詞の台帳の欄が不一致")
        if any(base[key] is None for key in ledger.NON_NULL_FIELDS):
            raise ValueError("動詞の台帳の必須欄が null")
        self._write_line({"record_type": "trial", **base, **extra})

    ledger.Ledger.append = append


def extend_dictionary():
    """shopworld.extend_dictionary と同じ。既存の辞書番号は保つ。"""
    import v39
    if not v39.CFG.get("dict_index"):
        return
    idx = dict(v39.CFG["dict_index"])
    for predicate in NEW_PREDICATES:
        if predicate not in idx:
            idx[predicate] = len(idx)
    v39.CFG["dict_index"] = idx
    v39.CFG["D"] = len(idx)


def prepare_probe_snapshot(pw):
    """固定試験の場面を最初に生成する前から、動詞の研究者記録も保存・復元する。"""
    for module in ("verbworld", "selectn3", "useforget"):
        if module not in pw.SNAP_MODULES:
            pw.SNAP_MODULES += (module,)
    if "IDS" not in pw.SNAP_ATTRS:
        pw.SNAP_ATTRS += ("IDS",)


def add_probes(pst, *, run_seed, agent_ids, holdout_second):
    """同じ固定場面で学習語・新語の過去形を問う。新語の正誤は採点しない。"""
    import probeworld as pw
    if tuple(pst["sd"].data["motif_structure"]) != ("M1",):
        raise ValueError("動詞の試験には M1 一型の種が必要")
    prs = f"probe\x1f{run_seed}"
    tr0 = CTX["orig_gen"](prs, 0, agent_ids, seed=pst["sd"], holdout_include_second_order=holdout_second)
    paths, _ = pw._paths(pst["sd"].data, prs, 0, "M1")
    role = [(paths[parent][2], position) for parent, position in paths[PAST_PATH][3]]
    items = (*CFG["items"], *(Verb(name, "novel", REG, 0.0) for name in NOVEL_NAMES))
    probes = []
    for item in items:
        tr, info = build(tr0, prs, 0, verb=item)
        # 新語の REG は生成用の仮の値。伏せるので入力には現れず、正誤の基準にも使わない。
        probes.append(dict(motif="M1", path=PAST_PATH, level=1, truth=None if item.verb_class == "novel" else item.past,
                           role=role, hid=info["past_id"], G=tr.G_star, partial=pw._partial(tr.G_star, info["past_id"]),
                           facts={(r.predicate, tuple(r.arguments)) for r in tr.G_star.relations}, verb_name=item.name,
                           score_truth=item.verb_class != "novel",
                           extra=dict(verb_probe="past", verb_name=item.name, verb_class=item.verb_class)))
    pst["probes"] = probes
    prepare_probe_snapshot(pw)


def seen(pst, t_limit, verb_name):
    """研究者の経験表。見えていた、又は問いの後で開示された正しい形だけ。"""
    from collections import Counter
    names, last = Counter(), None
    for t in range(t_limit):
        tr = pst["trials"].get(t)
        if tr is None:
            continue
        info = INFO[tr.G_star.graph_id]
        if verb_name is not None and info["verb_name"] != verb_name:
            continue
        if not info["held_out_is_past"] or pst["disclosed"].get(t):
            names[info["correct_past"]] += 1
            last = info["correct_past"]
    return names, last
