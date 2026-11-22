# 规则集：个人信息保护法 · 单独同意相关（v2.5）

> 本文件供 `tools/yaml_audit.py` 做机械质检（它从 ```yaml 代码块提取规则）。
> 引擎读取的是同目录的 `pipl-separate-consent_v2.5.yaml`，两者由同一份数据生成。
> 法条基准：`data/laws/个人信息保护法.md`（自官方 docx 逐字提取）。

---

## PIPL-13-01 · 处理个人信息的合法性基础与基本告知（第十三条）

```yaml
rule_id: PIPL-13-01
title: 处理个人信息的合法性基础与基本告知
law: 中华人民共和国个人信息保护法
article: 第十三条
rule_type: obligation
strength: 方可
layer: baseline
description: 任何个人信息处理行为都必须具备第十三条第一款所列情形之一的合法性基础，并按第十七条履行基本告知；无合法性基础即构成第十条所称「非法提供/使用」。
condition:
  all:
  - field: 存在个人信息处理行为
    operator: equals
    value: true
action:
- type: obligation
  id: legal_basis
  label: 合法性基础（第十三条第一款）
  mode: any
  options:
  - field: 已取得个人同意
    missing_label: 个人同意记录
  - field: 属于第13条第二至七项情形
    missing_label: 第十三条第一款第二至七项法定情形依据（并注明具体项）
- type: obligation
  id: notice_basic
  label: 基本告知（第十七条·处理者维度）
  mode: all
  options:
  - field: 已告知处理者名称或姓名和联系方式
    missing_label: 处理者名称或姓名与联系方式
  - field: 已告知处理目的、处理方式、信息种类
    missing_label: 处理目的、处理方式、信息种类
  - field: 已告知保存期限
    missing_label: 保存期限
  - field: 已告知个人行使权利的方式和程序
    missing_label: 个人行使权利的方式和程序
  note: 第17条第一款第(二)项在法条上是一项，但四件事可分别遗漏，故拆为两个字段
legal_basis:
  article: 第十三条
  quote: 符合下列情形之一的，个人信息处理者方可处理个人信息
  supporting_quotes:
  - article: 第十七条
    quote: 个人信息处理者在处理个人信息前，应当以显著方式、清晰易懂的语言真实、准确、完整地向个人告知下列事项
exceptions:
- description: 第十三条第一款第二至七项情形下，不需取得个人同意
  applies_to: legal_basis
not_applicable:
- 自然人因个人或者家庭事务处理个人信息（第七十二条第一款）
consequences:
  if_fulfilled: 合规（合法性基础与告知均已满足）
  if_unmet: 不合规：缺合法性基础 → 构成第十条「非法提供/使用」；缺告知 → 违反第十七条
required_evidence:
- 同意记录或法定情形依据
- 处理者名称或姓名与联系方式的告知记录
- 处理目的、处理方式、信息种类
- 行权方式和程序的告知记录
- 保存期限
verification:
  status: pending
  note: 待人工核对：第十三条第二至七项在具体场景的适用判断
test_cases:
- S1
- S2
- S3
- S4
- S6
- S7
- S8
- S9
- S10
- S11
- S12
- S13
notes: 基线规则。与第十七条合并建模；单独同意由 23/29/39 条决定，本条不重复要求。
```

## PIPL-23-01 · 向其他处理者提供：告知接收方并取得单独同意（第二十三条）

```yaml
rule_id: PIPL-23-01
title: 向其他处理者提供：告知接收方并取得单独同意
law: 中华人民共和国个人信息保护法
article: 第二十三条
rule_type: obligation
strength: 应当
layer: special
description: 个人信息处理者向其他个人信息处理者提供个人信息时，须告知接收方的名称或姓名、联系方式、处理目的、处理方式、信息种类，并取得单独同意。
condition:
  all:
  - field: 对外提供
    operator: equals
    value: true
  - field: 接收方为其他个人信息处理者
    operator: equals
    value: true
  - field: 信息属于个人信息
    operator: equals
    value: true
action:
- type: obligation
  id: notice_recipient
  label: 接收方维度告知（第二十三条）
  mode: all
  options:
  - field: 已告知接收方名称或姓名
    missing_label: 接收方名称或姓名
  - field: 已告知接收方联系方式
    missing_label: 接收方联系方式
  - field: 已告知接收方的处理目的
    missing_label: 接收方的处理目的
  - field: 已告知接收方的处理方式
    missing_label: 接收方的处理方式
  - field: 已告知接收方的信息种类
    missing_label: 接收方的信息种类
- type: obligation
  id: separate_consent
  label: 单独同意
  mode: all
  options:
  - field: 已取得单独同意
    missing_label: 单独同意记录
legal_basis:
  article: 第二十三条
  quote: 个人信息处理者向其他个人信息处理者提供其处理的个人信息的，应当向个人告知接收方的名称或者姓名、联系方式、处理目的、处理方式和个人信息的种类，并取得个人的单独同意。
exceptions: []
not_applicable:
- 非向其他个人信息处理者提供
- 不属于个人信息
consequences:
  if_fulfilled: 合规
  if_unmet: 不合规：缺接收方维度告知或单独同意，逐项列出缺失
required_evidence:
- 接收方名称或姓名与联系方式
- 接收方的处理目的、方式、信息种类
- 单独同意记录
verification:
  status: pending
  note: 接收方身份判定需人工确认
test_cases:
- S1
- S4
- S10
notes: 告知项属于「接收方维度」，与第十七条的「处理者维度」不重复。
```

## PIPL-23-02 · 接收方应在告知范围内处理（第二十三条）

```yaml
rule_id: PIPL-23-02
title: 接收方应在告知范围内处理
law: 中华人民共和国个人信息保护法
article: 第二十三条
rule_type: obligation
strength: 应当
layer: special
subject: 接收方
description: 接收方应当在处理目的、处理方式和个人信息的种类等范围内处理个人信息。
condition:
  all:
  - field: 对外提供
    operator: equals
    value: true
  - field: 接收方为其他个人信息处理者
    operator: equals
    value: true
action:
- type: obligation
  id: scope_compliance
  label: 接收方在告知范围内处理
  mode: all
  options:
  - field: 接收方在告知范围内处理
    missing_label: 接收方在告知目的、方式、信息种类范围内处理的证据
legal_basis:
  article: 第二十三条
  quote: 接收方应当在上述处理目的、处理方式和个人信息的种类等范围内处理个人信息。
exceptions: []
not_applicable:
- 非向其他个人信息处理者提供
consequences:
  if_fulfilled: 合规
  if_unmet: 不合规：接收方超出告知范围处理，输出整改提示
required_evidence:
- 告知范围记录
- 接收方实际处理记录
- 范围比对结果
verification:
  status: pending
  note: 接收方实际处理范围需外部证据
test_cases:
- S1
- S4
- S8
notes: 义务主体是接收方，由处理者侧输出提示；跨境场景下与第 39 条并行适用。
```

## PIPL-23-03 · 接收方变更目的或方式须重新取得同意（第二十三条）

```yaml
rule_id: PIPL-23-03
title: 接收方变更目的或方式须重新取得同意
law: 中华人民共和国个人信息保护法
article: 第二十三条
rule_type: obligation
strength: 应当
layer: special
subject: 接收方
description: 接收方变更原先的处理目的、处理方式的，应当依照本法规定重新取得个人同意。
condition:
  all:
  - field: 接收方变更处理目的或处理方式
    operator: equals
    value: true
action:
- type: obligation
  id: reconsent
  label: 重新取得个人同意
  mode: all
  options:
  - field: 已重新取得个人同意
    missing_label: 重新取得的个人同意记录
legal_basis:
  article: 第二十三条
  quote: 接收方变更原先的处理目的、处理方式的，应当依照本法规定重新取得个人同意。
exceptions: []
not_applicable:
- 接收方未变更处理目的或处理方式
consequences:
  if_fulfilled: 合规
  if_unmet: 不合规：变更后未重新取得同意
required_evidence:
- 原告知记录
- 变更后的目的或方式
- 重新同意记录
verification:
  status: pending
  note: 变更事实的认定需人工确认
test_cases:
- S4
- S7
notes: 与 23-01 分拆，便于引擎独立执行。
```

## PIPL-25-01 · 公开个人信息须单独同意，否则禁止（第二十五条）

```yaml
rule_id: PIPL-25-01
title: 公开个人信息须单独同意，否则禁止
law: 中华人民共和国个人信息保护法
article: 第二十五条
rule_type: obligation
strength: 不得
layer: special
description: 个人信息处理者不得公开其处理的个人信息；取得个人单独同意的除外。但书成立时仍须输出本规则并标注「依第二十五条但书」，不得因已同意而消失。
condition:
  all:
  - field: 公开其处理的个人信息
    operator: equals
    value: true
action:
- type: prohibition
  id: no_publication
  label: 不得公开其处理的个人信息
  mode: all
  options:
  - field: 已取得单独同意
    missing_label: 单独同意记录（如主张但书）
  exception_note: 取得个人单独同意的除外；成立时输出「依第二十五条但书」并留存证据
legal_basis:
  article: 第二十五条
  quote: 个人信息处理者不得公开其处理的个人信息，取得个人单独同意的除外。
exceptions:
- description: 取得个人单独同意的除外
  applies_to: no_publication
not_applicable:
- 未公开其处理的个人信息
consequences:
  if_fulfilled: 允许公开（依第二十五条但书），须留存同意证据并显式标注
  if_unmet: 不得公开（违反第二十五条）
required_evidence:
- 公开行为证据
- 单独同意记录（如主张但书）
verification:
  status: pending
  note: 「公开」的认定范围需人工确认
test_cases:
- S2
- S6
notes: 规则类型为 obligation，禁止通过 action.type=prohibition 表达；触发只看是否公开。
```

## PIPL-29-01 · 处理敏感个人信息须取得单独同意（第二十九条）

```yaml
rule_id: PIPL-29-01
title: 处理敏感个人信息须取得单独同意
law: 中华人民共和国个人信息保护法
article: 第二十九条
rule_type: obligation
strength: 应当
layer: special
description: 处理敏感个人信息应当取得个人的单独同意；法律、行政法规规定应当取得书面同意的，从其规定。
condition:
  all:
  - field: 处理敏感个人信息
    operator: equals
    value: true
action:
- type: obligation
  id: separate_consent
  label: 单独同意
  mode: all
  options:
  - field: 已取得单独同意
    missing_label: 单独同意记录
- type: obligation
  id: written_consent_if_required
  label: 法定要求书面同意时的书面同意
  mode: conditional_all
  condition:
    field: 法律行政法规要求书面同意
    operator: equals
    value: true
  options:
  - field: 已取得书面同意
    missing_label: 书面同意文件
legal_basis:
  article: 第二十九条
  quote: 处理敏感个人信息应当取得个人的单独同意；法律、行政法规规定处理敏感个人信息应当取得书面同意的，从其规定。
exceptions:
- description: 法律、行政法规规定应当取得书面同意的，从其规定
not_applicable:
- 非敏感个人信息
consequences:
  if_fulfilled: 合规
  if_unmet: 不合规：缺单独同意，或法定应取得书面同意而未取得
required_evidence:
- 单独同意记录
- 如适用，书面同意文件
- 敏感个人信息识别依据
verification:
  status: pending
  note: 敏感个人信息识别标准待人工确认
test_cases:
- S3
- S10
notes: 独立于接收方身份；向自然人提供敏感信息同样触发。
```

## PIPL-30-01 · 敏感个人信息的额外告知（第三十条）

```yaml
rule_id: PIPL-30-01
title: 敏感个人信息的额外告知
law: 中华人民共和国个人信息保护法
article: 第三十条
rule_type: obligation
strength: 应当
layer: special
description: 处理敏感个人信息的，除第十七条第一款规定的事项外，还应当告知处理敏感个人信息的必要性以及对个人权益的影响；依照本法规定可以不向个人告知的除外。
condition:
  all:
  - field: 处理敏感个人信息
    operator: equals
    value: true
action:
- type: obligation
  id: extra_notice
  label: 额外告知（必要性 + 对个人权益的影响）
  mode: all
  options:
  - field: 已告知处理必要性
    missing_label: 处理敏感个人信息必要性的说明
  - field: 已告知对个人权益的影响
    missing_label: 对个人权益影响的告知记录
  exception_note: 「属于可不告知情形」为 true 时豁免，但须显式标注豁免依据，不得静默通过
legal_basis:
  article: 第三十条
  quote: 个人信息处理者处理敏感个人信息的，除本法第十七条第一款规定的事项外，还应当向个人告知处理敏感个人信息的必要性以及对个人权益的影响；依照本法规定可以不向个人告知的除外。
exceptions:
- description: 依照本法规定可以不向个人告知的除外
  field: 属于可不告知情形
  equals: true
  behavior: 豁免，但须显式标注豁免依据
not_applicable:
- 非敏感个人信息
consequences:
  if_fulfilled: 合规
  if_unmet: 不合规：缺额外告知
required_evidence:
- 必要性说明
- 对个人权益影响的告知记录
- 可不告知情形的依据（如主张豁免）
verification:
  status: pending
  note: 「可不告知情形」的具体列举待确认
test_cases:
- S3
- S10
notes: 「额外告知」的基准是第十七条第一款，已由 PIPL-13-01 建模。
```

## PIPL-39-01 · 向境外提供：告知境外接收方并取得单独同意（第三十九条）

```yaml
rule_id: PIPL-39-01
title: 向境外提供：告知境外接收方并取得单独同意
law: 中华人民共和国个人信息保护法
article: 第三十九条
rule_type: obligation
strength: 应当
layer: special
description: 向中华人民共和国境外提供个人信息的，应当告知境外接收方的名称或姓名、联系方式、处理目的、处理方式、信息种类，以及个人向境外接收方行使权利的方式和程序，并取得单独同意。本条不限定接收方身份；接收方为个人信息处理者时另行叠加第二十三条。
condition:
  all:
  - field: 向境外提供个人信息
    operator: equals
    value: true
action:
- type: obligation
  id: notice_overseas
  label: 境外接收方维度告知（第三十九条）
  mode: all
  options:
  - field: 已告知境外接收方名称或姓名
    missing_label: 境外接收方名称或姓名
  - field: 已告知境外接收方联系方式
    missing_label: 境外接收方联系方式
  - field: 已告知境外接收方的处理目的
    missing_label: 境外接收方的处理目的
  - field: 已告知境外接收方的处理方式
    missing_label: 境外接收方的处理方式
  - field: 已告知境外接收方的信息种类
    missing_label: 境外接收方的信息种类
  - field: 已告知向境外接收方行使权利的方式和程序
    missing_label: 个人向境外接收方行使权利的方式和程序
- type: obligation
  id: separate_consent
  label: 单独同意
  mode: all
  options:
  - field: 已取得单独同意
    missing_label: 单独同意记录
legal_basis:
  article: 第三十九条
  quote: 个人信息处理者向中华人民共和国境外提供个人信息的，应当向个人告知境外接收方的名称或者姓名、联系方式、处理目的、处理方式、个人信息的种类以及个人向境外接收方行使本法规定权利的方式和程序等事项，并取得个人的单独同意。
exceptions: []
not_applicable:
- 未向境外提供个人信息
consequences:
  if_fulfilled: 合规
  if_unmet: 不合规：缺境外接收方维度告知或单独同意
required_evidence:
- 境外接收方名称或姓名与联系方式
- 境外接收方的处理目的、方式、信息种类
- 向境外接收方行权的方式和程序
- 单独同意记录
verification:
  status: pending
  note: 「境外提供」的认定（含访问情形）需人工确认
test_cases:
- S4
- S9
notes: 触发条件只要求「向境外提供个人信息」，与 Excel v2.3 的差异已在 v2.4 修正。
overlay_hint:
  combines_with:
  - PIPL-23-01
  - PIPL-23-02
  - PIPL-23-03
  when:
    field: 境外接收方为个人信息处理者
    operator: equals
    value: true
  rule: 叠加时告知按对象分层、单独同意只算一次、接收方义务保留
```
