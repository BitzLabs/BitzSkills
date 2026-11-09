"""閉包の参照計算（関係・トレースモデル §6.1〜§6.3・§7、ADR-071 Decision 2）。Coreの実装を読み込まない。

参照計算B（`digest_crosscheck`と`multi_crosscheck`）と、閉包を導く各fixtureの参照計算が共有する。閉包は次の3つで説明できる。

1. 下方向の出発点: 起点がREQ・TECH・ADRなら起点文書、TASKならそのTASKの`addresses`の参照先の所有文書（起点から`addresses`のエッジ1本の距離1）。
2. 下方向: 出発点の文書またはそのいずれかの規範文を`refines`する適用可能な文書を、逆向きに終端まで辿る。出発点と合わせてSとする。
   上方向で着いた文書からは、下方向へ辿らない。
3. 上方向: Sの文書から、`requires`・`refines`・`addresses`の参照先を、辺の種類を区別せず終端まで辿る。辺がSの文書へ戻る場合は、その文書へ着いたとはみなさず、
   到達したエッジも距離も記録しない。閉包はSとSの上方向の閉包の和集合である。

TASKを起点にする場合は、起点のTASK自身も上方向の出発点にし、その`requires`を辿る（目的`interpret`と`implement`）。目的`verify`は辿らず、起点の`requires`の
上方向の範囲を、コンテキストへ含めずに適用可能性の検査だけを行う範囲（`outside`）として返す。目的`interpret`は、Sの文書またはその規範文を`refines`する状態`draft`の文書を
役割`advisory`として含め（その文書からは辿らない）、置換済みの起点（有効な後継が1件）の後継を距離1で含める。目的`implement`で起点がTASKでなければ、
対象規範文を`addresses`する状態`open`のTASKを、その規範文を所有する文書から`addresses`のエッジ1本の距離で加える（そのTASKからは辿らない）。

入力は、種別ごとの文書の索引`documents`（`kind`、`status`、`rel`、`statements`）である。`rel`は関係名ごとの[(参照先の文書ID, 参照先の規範文ID（文書の参照なら`None`）, 宣言どおりの参照)]、
`statements`は文書が所有する規範文のID（参照の表記と同じ）の集合である。規則で説明できない強いエッジが閉包に触れていれば、黙って取り込まずに拒否する。
"""

UPWARD = ("requires", "refines", "addresses")
ALL_STRONG = ("requires", "refines", "addresses", "supersedes")
APPLICABLE = {"approved", "accepted", "open", "done"}


def compute(documents, root_document, purpose, *, missing="raise", targets_of=None, rank=None, strict=True):
    """閉包を導く。戻り値は辞書: `distance`（文書→最短の段数）、`edges`（文書→{(関係, 宣言した文書)}）、`order`（距離、種別の順位、IDの順の文書）、`found`（見つけた順の文書）、
    `selected`（S）、`advisory`、`replacement`、`outside`（目的`verify`でTASKを起点にしたときの、コンテキストへ含めない上方向の範囲）。

    `missing`は、辿る強い関係の参照先がないときの扱い（`raise`で拒否、`skip`で無視）。`targets_of(reached)`は、目的`implement`の対象規範文の集合を返す関数
    （`reached`は閉包の文書の集合）。`rank`は種別の順位（省略時は種別の名前）。
    `strict`が偽のときは、規則で説明できない強いエッジが閉包に触れていても拒否しない（閉包と無関係な文書を含むcorpusの参照計算が使う）。
    """
    root = documents[root_document]
    is_task = root["kind"] == "task"
    closure, selected, advisory, replacement, outside = {root_document}, set(), set(), set(), set()
    reached, labels, accounted, found = set(), {}, set(), [root_document]

    def include(name):
        if name not in closure:
            closure.add(name)
            found.append(name)

    def reach(source, target, relation, declaring):
        reached.add((source, target))
        labels.setdefault(target, set()).add((relation, declaring))
        include(target)

    def present(target):
        if target in documents:
            return True
        if missing == "raise":
            raise ValueError("強いエッジがこのcorpusの外を指しています")
        return False

    def refines_into(document, members):
        """`document`の`refines`のうち、`members`の文書またはその規範文を指す参照。"""
        return [(target, raw) for target, statement, raw in document["rel"]["refines"]
                if target in members and (statement is None or statement in documents[target]["statements"])]

    # 1. 下方向の出発点
    starts = []
    if is_task:
        for target, _statement, raw in root["rel"]["addresses"]:
            accounted.add((root_document, "addresses", raw))
            if target not in documents:
                raise ValueError("`addresses`の先がこのcorpusに存在しません")
            if target not in starts:
                starts.append(target)
                reach(root_document, target, "addresses", root_document)
    else:
        starts.append(root_document)
    selected.update(starts)

    # 2. 下方向
    queue = list(starts)
    while queue:
        parent = queue.pop(0)
        for name in sorted(documents):
            candidate = documents[name]
            if (name == root_document or candidate["kind"] not in ("requirement", "technical")
                    or candidate["status"] not in APPLICABLE):
                continue
            matches = refines_into(candidate, {parent})
            if not matches:
                continue
            for _target, raw in matches:
                accounted.add((name, "refines", raw))
            reach(parent, name, "refines", name)
            if name not in selected:
                selected.add(name)
                queue.append(name)

    # 3. 上方向（Sへ戻る辺は着いたとみなさない）。目的`verify`でTASKを起点にするときは、起点のTASKからは辿らない。
    walk = list(selected) + ([root_document] if is_task and purpose != "verify" else [])
    walked = set()
    while walk:
        current = walk.pop(0)
        if current in walked:
            continue
        walked.add(current)
        for key in UPWARD:
            for target, _statement, raw in documents[current]["rel"][key]:
                accounted.add((current, key, raw))
                if not present(target) or target in selected:
                    continue
                reach(current, target, key, current)
                walk.append(target)
    if is_task and purpose == "verify":
        for target, _statement, raw in root["rel"]["requires"]:
            accounted.add((root_document, "requires", raw))
        walk = [target for target, _statement, _raw in root["rel"]["requires"] if target in documents]
        while walk:
            current = walk.pop(0)
            if current in closure or current in outside:
                continue
            outside.add(current)
            for key in ALL_STRONG:
                for target, _statement, raw in documents[current]["rel"][key]:
                    accounted.add((current, key, raw))
                    if key in UPWARD and target in documents:
                        walk.append(target)

    # 目的`interpret`: 状態`draft`の文書のうちSの文書またはその規範文を`refines`するものは、役割`advisory`として含め、その文書からは辿らない。
    for name in sorted(documents):
        candidate = documents[name]
        if name in closure or candidate["kind"] not in ("requirement", "technical") or candidate["status"] != "draft":
            continue
        matches = refines_into(candidate, selected)
        if matches and purpose == "interpret":
            advisory.add(name)
            include(name)
            for target, _raw in matches:
                reached.add((target, name))
            labels.setdefault(name, set()).add(("refines", name))
            for key in ALL_STRONG:
                for _target, _statement, raw in candidate["rel"][key]:
                    accounted.add((name, key, raw))

    # 置換済みの起点（目的`interpret`）。
    if purpose == "interpret" and root["kind"] in ("requirement", "technical"):
        successors = sorted(name for name, document in documents.items()
                            if document["kind"] == root["kind"] and document["status"] in APPLICABLE
                            and any(target == root_document for target, _s, _r in document["rel"]["supersedes"]))
        if len(successors) > 1:
            raise ValueError("有効な後継が複数あるcorpusはこの閉包の対象外です")
        if successors:
            advisory.add(root_document)
            replacement.add(successors[0])
            for _target, _statement, raw in documents[successors[0]]["rel"]["supersedes"]:
                accounted.add((successors[0], "supersedes", raw))
            reach(root_document, successors[0], "supersedes", successors[0])

    # 目的`implement`: 対象規範文を`addresses`する状態`open`のTASK（起点がTASKのときは加えない）。
    if purpose == "implement" and not is_task:
        targets = targets_of(set(selected)) if targets_of is not None else set()
        for name in sorted(documents):
            candidate = documents[name]
            if candidate["kind"] != "task" or candidate["status"] != "open":
                continue
            for target, _statement, raw in candidate["rel"]["addresses"]:
                if raw in targets:
                    accounted.add((name, "addresses", raw))
                    reach(target, name, "addresses", name)
                    # 加えたTASKからは辿らない（役割`work`）。そのTASKが宣言する強いエッジは、辿らない辺として記録する。
                    for key in ALL_STRONG:
                        for _target, _statement, other in candidate["rel"][key]:
                            accounted.add((name, key, other))

    # 閉包に含めない適用可能な文書または状態`draft`の文書が、閉包内の文書を`refines`する辺は、下方向へ辿らない辺として記録する。
    for name in sorted(documents):
        candidate = documents[name]
        if name in closure or candidate["kind"] not in ("requirement", "technical"):
            continue
        if candidate["status"] in APPLICABLE or candidate["status"] == "draft":
            for target, statement, raw in candidate["rel"]["refines"]:
                if target in closure and (statement is None or statement in documents[target]["statements"]):
                    accounted.add((name, "refines", raw))

    # TASKを起点にした閉包は、ほかのTASKを`addresses`で加えない（目的`implement`も同じ。ADR-071 Decision 2の4.）。閉包に含めないTASKの`addresses`は、
    # 辿らない辺として記録する。REQ・TECHを起点にしたときは、閉包の外のTASKの`addresses`が閉包に触れれば拒否する。
    if is_task:
        for name, candidate in documents.items():
            if candidate["kind"] == "task" and name not in closure:
                for _target, _statement, raw in candidate["rel"]["addresses"]:
                    accounted.add((name, "addresses", raw))

    # 最短の段数（到達したエッジ1本を1段とする）。
    adjacent = {}
    for source, target in reached:
        adjacent.setdefault(source, set()).add(target)
    distance, queue = {root_document: 0}, [root_document]
    while queue:
        current = queue.pop(0)
        for target in sorted(adjacent.get(current, ())):
            if target not in distance:
                distance[target] = distance[current] + 1
                queue.append(target)
    if set(distance) != closure:
        raise ValueError("到達したエッジから閉包の全文書の距離を導けません")

    # この閉包に触れる強いエッジは、すべて説明されていなければならない。
    for name, document in documents.items() if strict else ():
        for key in ALL_STRONG:
            for target, statement, raw in document["rel"][key]:
                if target not in documents or (statement is not None and statement not in documents[target]["statements"]):
                    continue
                if (name in closure or target in closure or name in outside) and (name, key, raw) not in accounted:
                    raise ValueError("corpusにレビュー済みの閉包の外の強いエッジがあります")

    ranking = rank or (lambda kind: kind)
    order = sorted(distance, key=lambda name: (distance[name], ranking(documents[name]["kind"]), name))
    return {"distance": distance, "edges": labels, "order": order, "found": found, "selected": selected, "advisory": advisory,
            "replacement": replacement, "outside": outside}
