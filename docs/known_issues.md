# Known Issues

记录代码走查中发现的待修问题。每条注明位置、现象、影响。修复后删除对应条目。

## load_xml / load_yaml（xqsim/common_utils.py）

### 1. load_xml 全文本替换 "@" 误伤数据值 — line 82

```python
xml_dict = json.loads(json.dumps(xmltodict.parse(data)).replace("@", ""))["QSim"]
```

xmltodict 用 `@` 前缀表示 XML 属性，这里想去掉前缀，但 `replace("@", "")` 是对整个
JSON 文本做替换，**值里含的 `@` 也会被删掉**（如路径、邮箱、带 @ 的字符串参数）。
属于静默数据损坏，最坑的一类。

修法方向：递归遍历 dict 只改 key（strip 掉 key 首字符的 @），不动 value。

### 2. load_xml 用 eval 解析 dict 字面量 — line 90

```python
data = str(xml_dict)
...
xml_dict = eval(data)
```

`eval` 对配置内容做代码执行，安全隐患；且依赖 `str(dict)` 的 repr 往返，脆弱。
至少改 `ast.literal_eval`；更好的做法是直接在 dict 上做宏替换（递归遍历 value 替换
`${...}`），不经过 str/eval 这一遭。

### 3. load_xml 单个 Module 时崩溃 — line 113
```python
for module_dict in xml_dict["Modules"]["Module"]:
```

xmltodict 的规则：同名元素多个 → list，单个 → dict。`Alpha`、`Cache` 都做了
`isinstance(..., dict)` 单元素兼容，`Module` 没做。XML 里只写一个 Module 时，
for 迭代 dict 拿到的是字符串 key，随后 `module_dict["handler"]` 报 TypeError。

### 4. load_xml 空 Stats 节点未判 None — line 162-166

```python
if k == "Stats":
    v["id"] = ...
```

`Operations` 分支判了 `if v is None: continue`，`Stats` 没判。XML 里写空
`<Stats/>` 时 `v` 是 None，`v["id"]` 直接 TypeError。

### 5. load_yaml 宏值为非 str 时崩溃 — line 72

```python
data = data.replace(macro_key, macro_value)
```

`macro_value` 来自 YAML 解析结果。YAML 里宏值写成整数/布尔（如 `year: 2025`）
时不是 str，`str.replace` 报 TypeError。应 `macro_value = str(v)`。

### 6. load_yaml 空配置文件崩溃 — line 66

`yaml.load` 对空文件返回 None，`config_dict.get("macro", {})` 报
AttributeError。应 `config_dict = yaml.load(...) or {}`。

## load_xml 大写 key 残留（Operations/Stats）— line 141-167

翻译循环里 `id` / `moduleId` 处理完有 `continue`，`Operations` / `Stats` 处理完
**没有 `continue`**，于是漏到 167 行兜底 `dic[k] = v`，把大写原始值也塞进 alpha
配置。结果同一 dict 里 `Operations`（XML 原始形态）和 `operation`（归一化形态）
并存，`Stats` / `stats` 同理。下游只读小写（simulator.py:155,161、alpha_manager
MODULE_TYPE pop "stats"），大写 key 无任何消费者，是随 cfg 传入 `self.cfg` 并
被 checkpoint 多序列化一份的死重量。

修法方向：两个分支处理完各补 `continue`（修时注意与第 4 条的 None 判断一起改）。

## dynamic_save_csv 默认 None 屏蔽 alpha 级 save_csv — simulator.py / alpha_manager.py

`init_base` 无条件执行 `set_para("dynamic_save_csv", simcfg.get(base_config,
"dynamic_save_csv", None))`——配置里不写时 para 键存在但值为 `None`。
`AlphaTask.save_csv` 第一行 `get_para_default("dynamic_save_csv",
self.__alpha.save_csv_dir)` 因键已存在返回 `None`，直接 return。

后果：alpha 配置里的 `save_csv="csv"` 被静默忽略，不产出任何 csv
（2026-08-09 跑 AlphaWbaiHotMomentum 实证）。因子 `.fac` 文件保存
（`save="true"`）不受影响。

修法方向：`init_base` 只在配置显式给出时才 `set_para`（或默认 `""` 并在
save_csv 侧把 None 当未配置处理）。

## utils.pnl_scale 与新版 pandas 不兼容（LossySetitemError）— xqsim/utils.py

`pnl_scale` 里 `df.loc[:, 'Date'] = [pd.Timestamp(str(x)) for ...]` 把 Timestamp
列表赋给 int64 的 Date 列。旧版 pandas 静默换列 dtype，pandas 2.x 抛
`LossySetitemError`（2026-08-10 跑 stats_futures 实证）。`stats_general` 走同
一函数，同样会炸。

绕过（stats_futures.save_pnl 已采用）：调用方先
`df["Date"] = pd.to_datetime(df["Date"], format="%Y%m%d")` 再传入。
修法方向：在 `pnl_scale` 内部做 `pd.to_datetime` 转换，不依赖调用方。

## 备注

- line 127 `alpha_dict_list.append(portfolio_dict)` 把 portfolio 容器塞进了自己的子列表
  （多 Alpha 时 `alpha_dict_list` 就是 `portfolio_dict["Alpha"]` 本体），构造出循环引用：
  `portfolio_dict["Alpha"]` 列表里包含 `portfolio_dict` 自身，再经 167 行兜底拷贝带进
  `config_dict["alpha"][pid]["Alpha"]`。后果：`json.dumps` 配置时报
  `ValueError: Circular reference detected`；`print`（repr 显示 `[...]`）和 pickle
  （checkpoint 路径）能容忍，所以平时不炸。单 Alpha 配置因 `isinstance(dict)` 分支包了
  新 list 而不触发。该机制同时是 portfolio 识别的既定行为（simulator 靠
  `if "Alpha" in config` 判断 portfolio_task），修时要保留这一语义：建议 append 前
  `alpha_dict_list = list(alpha_dict_list)` 拷贝一份打断共享，同时消掉 `v2["module_id"]=...`
  就地改共享对象的别名风险。

