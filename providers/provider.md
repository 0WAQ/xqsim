# Provider：公共数据贡献说明

普通因子研究通常直接读取已有共享缓存，不需要在研究 XML 中额外注册 Provider。只有在以下场景中，才需要新增 Provider：

- 新增公共数据字段；
- 修复或重建已有公共数据；
- 将外部数据源加工成 qsim 可读取的统一缓存格式。

共享数据构建应由维护者使用审核过的配置和部署流程执行；个人研究不应直接覆盖共享缓存目录。

---

## 一、提交 Provider 时建议说明的内容

贡献说明至少应包含：

1. **数据源与可用时点**
   - 数据来自哪里；
   - 字段在什么时间点可用；
   - 是否存在未来函数风险。

2. **输出定义**
   - 输出字段名；
   - `dtype`；
   - `shape`；
   - 缺失值约定。

3. **写入方式**
   - 是全量写入、增量写入，还是静态写入；
   - 写入覆盖的日期范围；
   - 是否允许覆盖已有缓存。

4. **验证方式**
   - 如何校验行数、字段值、日期范围、缺失率；
   - 如何与源数据或历史缓存对比。

5. **凭据管理**
   - 凭据文件放在哪里；
   - 源码中不得硬编码账号、密码等敏感信息。

---

## 二、XML 中的 Provider 配置

示例：

```xml
<Providers>
    <Local dir_name="DemoProvider"/>
    <Provider id="SimpleProvider" file_path="${MODULES}/simple_provider.py"/>
    <Provider id="SimpleProvider1" file_path="${MODULES}/simple_provider.py"/>
</Providers>
```

### 1. `<Providers>`

`<Providers>` 是 Provider 配置容器，本身不承载额外业务逻辑，主要用于组织 `<Local>` 和多个 `<Provider>` 节点。

### 2. `<Local .../>`

`<Local>` 表示 Provider 的公共配置。其属性会被合并到下面每个 `<Provider>` 的配置中。若没有公共字段，可以不写。

当前项目中常见字段有：

#### `dir_name`

表示 Provider 输出缓存使用的目录名。实际输出目录为：

```text
${output_cache_dir}/Data/{dir_name}
```

如果不写，`ProviderBase` 默认使用当前 Provider 的 `id` 作为目录名。

#### `mysql_config`

表示 MySQL 连接配置文件名，例如：

```xml
mysql_config="mysql.json"
```

#### `mysql_config_dir`

表示 MySQL 连接配置文件所在目录，例如：

```xml
mysql_config_dir="/home/hyh/xqsim/providers"
```

对继承 `StaticProvider` 的 Provider，最终会按如下方式拼接配置文件路径：

```text
mysql_config_dir + "/" + mysql_config
```

#### 其他字段

其余字段可以按具体 Provider 的需求自定义，框架会将这些字段透传到 `self.cfg` 中，供 Provider 自行读取。

> 注意：当前代码中的合并顺序是“全局配置 + Local + Provider 自身配置再注入到 Provider”。文档层面建议把公共字段统一写在 `<Local>` 中，避免和单个 `<Provider>` 写同名字段后产生歧义。

### 3. `<Provider .../>`

`<Provider>` 表示一个具体的 Provider 实例。

其中：

- `id`：必填。Provider 的逻辑名称，可自定义，不要求和 Python 类名相同；
- `file_path`：必填。Provider 源码文件路径；
- 其余字段：按具体 Provider 需要可选添加。

运行时框架会根据 `file_path` 动态加载该文件中的 `Provider` 类。

---

## 三、Provider 实现类的基本写法

最小示例：

```python
import numpy as np

from qsim.provider_base import ProviderBase


class Provider(ProviderBase):
    # 初始化
    def __init__(self, *args):
        super().__init__(*args)
        self.dir_name = self.cfg.get("dir_name", self.id)

    # 具体业务逻辑
    def generate(self):
        print("Provider generate done, output dir is %s" % self.output_cache_dir)
```

说明：

- 类名固定写为 `Provider`；
- 框架会根据 `file_path` 动态导入文件，并查找其中名为 `Provider` 的类；
- `generate()` 是具体业务执行入口，框架运行时会自动调用。

---

## 四、在 Provider 中读取配置参数

XML 中写入的参数，最终都会进入 `self.cfg`。

例如：

```xml
<Local dir_name="DemoProvider"/>
```

在 Provider 中可以这样读取：

```python
self.cfg.get("dir_name")
```

也可以指定默认值：

```python
self.cfg.get("dir_name", "default_dir")
```

含义是：

- 如果配置中存在 `dir_name`，返回其值；
- 如果不存在，则返回默认值 `"default_dir"`。

此外，`ProviderBase` 已经预先处理了一些常用字段，可以直接使用：

- `self.id`
- `self.dir_name`
- `self.output_cache_dir`
- `self.output_dir`

---

## 五、在 Provider 中写出缓存数据

最常用的写法是：

```python
self.write_data("数据名", numpy数组)
```

例如：

```python
data = np.full((self.meta.di_size, self.meta.ii_size), 1.0, dtype=np.float64)
self.write_data("demo.signal", data)
```

其含义是：

- 将 `numpy` 数组写入当前 Provider 对应的缓存目录；
- 输出目录通常为：

```text
${output_cache_dir}/Data/{dir_name}
```

- `"数据名"` 表示缓存中的逻辑数据名，例如：
  - `k.close`
  - `uv.hs300`
  - `demo.signal`

### 重要说明

1. `self.write_data()` 是将数据写到磁盘缓存，不是直接往 `dr` 的内存索引里手工注册；
2. Provider 运行完成后，框架会调用 `dr.scan_all()` 重新扫描缓存目录；
3. 扫描完成后，后续模块即可通过：

```python
self.dr.get_data("数据名")
```

读取对应数据。

因此，Provider → `dr` 的标准链路是：

```text
self.write_data(...) → 写入缓存目录 → dr.scan_all() → self.dr.get_data(...)
```

### 数组要求

通常写入的数组为：

- 日频二维数据：`(di_size, ii_size)`
- 日内三维数据：`(di_size, ti_size, ii_size)`

其中第一维必须与本次运行的交易日范围匹配。

> 原文中的“numpy数组为写入的数据库”表述不准确，建议改为“numpy 数组为写入的缓存数据”。

---

## 六、如需使用 MySQL：继承 `StaticProvider`

如果 Provider 需要从 MySQL 读取数据，建议继承 `StaticProvider`：

```python
from static_provider import StaticProvider


class Provider(StaticProvider):
    def __init__(self, *args):
        super().__init__(*args)

    def generate(self):
        rows = self.exec_sql_fetchall("SELECT ...")
        # 处理 rows 后再 self.write_data(...)
```

`StaticProvider` 相比 `ProviderBase` 额外提供：

- `mysql_config`
- `mysql_config_dir`
- `exec_sql_fetchall()`
- 若干 SQL / 表结构转矩阵的辅助方法

如果 Provider 不需要连接数据库，只做本地计算或文件加工，直接继承 `ProviderBase` 即可。