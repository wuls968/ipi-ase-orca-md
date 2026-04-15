# i-PI ASE ORCA MD

这是一个给 ORCA 做 AIMD / PIMD 用的单文件模板项目。

你主要只需要改一个文件：

- `ipi_ase_orca_template.py`

这个脚本会帮你生成一整套可运行的作业目录，包括：

- `input.xml`
- `ase_orca_client.py`
- `submit_job.sh`
- `run_all.sh`
- `job_config.json`
- `README.job.md`

项目采用的执行链路是：

`i-PI -> ASE SocketClient -> ASE ORCA calculator -> ORCA`

也就是说：

- `i-PI` 负责分子动力学主循环
- `ASE` 负责把 i-PI 的力请求转给 ORCA
- `ORCA` 真正做电子结构单点能和力计算

这套模板的目标不是把所有 i-PI 功能都包完，而是把“绝大多数用 ORCA 跑分子 AIMD / PIMD 的常见配置”尽量做得简单、透明、容易改。

## 这个项目适合什么

适合：

- 气相或大真空盒分子体系的 AIMD
- 气相或大真空盒分子体系的 PIMD
- `NVE` 和 `NVT`
- 本地测试
- 服务器或集群上通过一个 `.sh` 脚本启动

当前不主打：

- 多力场组合
- MTS / RPC / 高级分层力
- NPT / barostat
- 固体周期体系的大规模生产计算自动化

## 5 分钟上手

### 1. 准备环境

建议使用你现在已经在用的 `conda` 环境 `ipi`。

最少需要：

- `i-pi`
- `ase`
- 本地可执行的 `orca`

如果 `ase` 没装：

```sh
conda activate ipi
python -m pip install ase
```

或者：

```sh
conda install -n ipi -c conda-forge ase
```

如果你想跑测试，再装：

```sh
conda run -n ipi python -m pip install pytest
```

### 2. 改模板文件

打开：

- `ipi_ase_orca_template.py`

然后修改 `build_default_config()` 里各个配置项。

对初学者来说，最先要改的通常只有这几处：

- `structure.xyz_path` 或 `structure.xyz_string`
- `orca.orca_command`
- `orca.orcasimpleinput`
- `orca.orcablocks`
- `simulation.simulation_kind`
- `simulation.nbeads`
- `simulation.temperature`
- `simulation.total_steps`

### 3. 只生成作业，不启动

第一次建议先这样做：

```sh
python ipi_ase_orca_template.py --write-only
```

默认会在：

- `jobs/h2o_pimd_demo/`

下面生成一套文件。

### 4. 本地直接启动

如果只是做一个很小的 smoke test，可以：

```sh
python ipi_ase_orca_template.py --run
```

或者进入作业目录后手动运行：

```sh
cd jobs/h2o_pimd_demo
sh run_all.sh
```

### 5. 用提交辅助脚本启动

更推荐的方式是进入生成目录后运行：

```sh
cd jobs/h2o_pimd_demo
sh submit_job.sh
```

这个脚本会：

- 激活 `conda` 环境
- 检查 `ase`
- 检查 `ORCA`
- 启动 `i-pi`
- 等待 socket 就绪
- 启动 ASE + ORCA 客户端

## 新手最重要的修改点

如果你只想先跑起来，优先理解下面 4 件事就够了。

### 1. 结构从哪里来

你可以二选一：

- 用 `xyz_path`
- 用 `xyz_string`

例子 1：直接读现成 xyz 文件

```python
structure=StructureSettings(
    xyz_path=Path("/absolute/path/to/your_structure.xyz"),
    xyz_string=None,
    charge=0,
    multiplicity=1,
    cell=None,
    pbc=False,
)
```

例子 2：直接把 xyz 写进脚本

```python
structure=StructureSettings(
    xyz_path=None,
    xyz_string="""3
water
O 0.000000 0.000000 0.000000
H 0.758602 0.000000 0.504284
H -0.758602 0.000000 0.504284
""",
    charge=0,
    multiplicity=1,
    cell=None,
    pbc=False,
)
```

### 2. ORCA 可执行文件在哪里

改这里：

```python
orca_command="/Users/a0000/Library/orca_6_1_0/orca"
```

你应该把它改成你机器上真实的 ORCA 主程序路径。

如果不确定，可以在终端里先查：

```sh
which orca
```

或者直接写完整路径。

### 3. ORCA 方法、基组在哪里选

最重要的是这项：

```python
orcasimpleinput="B3LYP def2-SVP TightSCF"
```

这一行就是 ORCA 输入文件里 `!` 后面的内容。

也就是说：

- 方法在这里选
- 基组在这里选
- SCF 精度等常用关键词也在这里选

例如：

```python
orcasimpleinput="B3LYP def2-SVP TightSCF"
```

或者：

```python
orcasimpleinput="wB97X-D3 def2-TZVP TightSCF"
```

或者：

```python
orcasimpleinput="r2SCAN-3c TightSCF"
```

你平时在 ORCA 输入里会放在 `!` 后面的那一串，基本就放这里。

### 4. ORCA 核数和内存怎么改

对新手最重要的一句：

> 当前模板里，真正控制 ORCA 并行核数和每核内存的是 `orca.orcablocks`，不是 `nprocs` / `maxcore` 这两个数字本身。

你应该重点改这里：

```python
orcablocks="%pal nprocs 8 end\n%maxcore 4000"
```

这表示：

- 用 `8` 个核
- 每核 `4000 MB` 内存

一个更完整的例子：

```python
orca=OrcaSettings(
    orca_command="/path/to/orca",
    orcasimpleinput="B3LYP def2-SVP TightSCF",
    orcablocks="%pal nprocs 8 end\n%maxcore 4000",
    nprocs=8,
    maxcore=4000,
    label="orca_run",
    extra_keywords="",
)
```

建议你把：

- `orcablocks` 里的 `nprocs`
- `nprocs`
- `maxcore`

这几处保持一致，虽然当前真正写入 ORCA 输入的是 `orcablocks`。

## 一套典型工作流

下面给你一个从零开始的推荐流程。

### 第一步：先做一个最小 AIMD

把配置改成：

- `simulation_kind="aimd"`
- `ensemble="nvt"`
- `nbeads=1`
- `thermostat_mode="svr"`
- `total_steps=20` 或更小

这是最适合第一次测试链路是否通的方式。

### 第二步：确认 ORCA 设置没问题

至少确认：

- `orca_command` 路径正确
- `orcasimpleinput` 是你想要的方法
- `orcablocks` 里的核数和内存合理
- `charge` 和 `multiplicity` 正确

### 第三步：先生成，不启动

```sh
python ipi_ase_orca_template.py --write-only
```

然后进入生成目录看看：

```sh
cd jobs/你的作业名
ls
```

### 第四步：检查生成文件

至少看这几个：

- `input.xml`
- `ase_orca_client.py`
- `submit_job.sh`
- `job_config.json`

如果你想确认 ORCA 方法有没有写对，可以直接打开：

- `ase_orca_client.py`

看里面的：

- `orcasimpleinput=...`
- `orcablocks=...`

### 第五步：做本地 smoke test

```sh
cd jobs/你的作业名
sh run_all.sh
```

如果只是试链路，建议：

- `nbeads=1`
- `total_steps=1`
- 小体系
- 小基组

### 第六步：正式启动

正式跑时更推荐：

```sh
cd jobs/你的作业名
sh submit_job.sh
```

## AIMD 和 PIMD 分别怎么设

### 普通 AIMD

最常见设置：

```python
simulation=SimulationSettings(
    simulation_kind="aimd",
    ensemble="nvt",
    nbeads=1,
    temperature=300.0,
    timestep_fs=0.5,
    total_steps=1000,
    seed=12345,
    thermostat_mode="svr",
    tau_fs=100.0,
    properties_stride=1,
    trajectory_stride=10,
    checkpoint_stride=50,
    prefix="simulation",
)
```

常用经验：

- `AIMD` 基本就是 `nbeads=1`
- `NVT` 下可用 `svr` 或 `langevin`
- 如果要 `NVE`，把 `ensemble="nve"`，并且不需要 thermostat

### PIMD

典型设置：

```python
simulation=SimulationSettings(
    simulation_kind="pimd",
    ensemble="nvt",
    nbeads=16,
    temperature=300.0,
    timestep_fs=0.5,
    total_steps=1000,
    seed=12345,
    thermostat_mode="pile_g",
    tau_fs=100.0,
    properties_stride=1,
    trajectory_stride=10,
    checkpoint_stride=50,
    prefix="simulation",
)
```

常用经验：

- `PIMD` 必须 `nbeads >= 2`
- 模板当前要求 `PIMD` 的 thermostat 用 `pile_g` 或 `pile_l`
- 第一次测试建议先用 `nbeads=8` 或 `16`

## 参数分组说明

下面这部分适合在你已经能跑通一次之后再细看。

### `JobSettings`

- `job_name`
  生成目录名
- `work_root`
  作业根目录，默认是 `jobs`
- `clean_existing`
  如果作业目录已存在，是否覆盖
- `socket_mode`
  `unix` 或 `inet`
- `socket_address`
  unix socket 名称或 inet 主机名
- `socket_port`
  inet 模式下的端口

说明：

- 本地最推荐 `unix`
- 如果你是跨节点或特殊网络环境，再考虑 `inet`

### `StructureSettings`

- `xyz_path`
  从 xyz 文件读取结构
- `xyz_string`
  直接把 xyz 写进脚本
- `charge`
  总电荷
- `multiplicity`
  自旋多重度
- `cell`
  盒子大小，格式如 `(20.0, 20.0, 20.0)`
- `pbc`
  是否周期性

说明：

- 对非周期分子，通常设 `pbc=False`
- 当 `pbc=False` 且 `cell=None` 时，模板会自动补一个 `15 x 15 x 15 Å` 真空盒，方便 i-PI 初始化
- 如果你体系更大，建议手动给一个更大的 `cell`
- 当 `pbc=True` 时，必须显式提供 `cell`

### `SimulationSettings`

- `simulation_kind`
  `aimd` 或 `pimd`
- `ensemble`
  `nve` 或 `nvt`
- `nbeads`
  bead 数
- `temperature`
  温度
- `timestep_fs`
  时间步，单位 fs
- `total_steps`
  总步数
- `seed`
  随机种子
- `thermostat_mode`
  thermostat 类型
- `tau_fs`
  thermostat 时间常数
- `properties_stride`
  性质输出频率
- `trajectory_stride`
  轨迹输出频率
- `checkpoint_stride`
  checkpoint 输出频率
- `prefix`
  输出文件前缀

### `OrcaSettings`

- `orca_command`
  ORCA 可执行文件路径
- `orcasimpleinput`
  ORCA `!` 后面的输入
- `orcablocks`
  ORCA `%...end` 块
- `nprocs`
  记录用的核数
- `maxcore`
  记录用的每核内存
- `label`
  ORCA 工作目录名
- `extra_keywords`
  额外补在 `orcasimpleinput` 后面的关键词

说明：

- 模板会自动给 ORCA 加上 `Engrad`，这样 MD 需要的力默认会请求
- `extra_keywords` 会直接拼到 `orcasimpleinput` 后面
- 真正控制核数/内存的是 `orcablocks`

### `AdvancedSettings`

- `fix_com`
  是否固定质心
- `ffsocket_pbc`
  socket 力场层面的 PBC 开关
- `latency`
  socket 轮询延迟
- `timeout`
  socket / 运行等待超时
- `initial_velocities`
  是否热初始化速度
- `velocity_temperature`
  初始速度温度
- `custom_xml_overrides`
  自定义附加 XML 片段
- `job_launcher_prefix`
  启动作业前缀，比如 `srun`

## 生成目录里每个文件是干什么的

- `input.xml`
  i-PI 主输入文件
- `init.xyz`
  初始结构
- `ase_orca_client.py`
  ASE 客户端脚本，负责连接 i-PI 并调用 ORCA
- `job_config.json`
  当前作业配置快照，方便复现
- `run_ipi.sh`
  只启动 i-PI
- `run_client.sh`
  只启动 ASE + ORCA 客户端
- `run_all.sh`
  本地串起来一起跑
- `submit_job.sh`
  更适合正式启动的辅助脚本
- `README.job.md`
  当前作业的简要说明

## `submit_job.sh` 怎么用

生成作业后：

```sh
cd jobs/你的作业名
sh submit_job.sh
```

这个脚本顶部有几个你最可能改的变量：

- `CONDA_SH`
- `CONDA_ENV`
- `ORCA_COMMAND`
- `JOB_LAUNCHER_PREFIX`

### 如果你在本机直接跑

通常只要保证：

- `CONDA_SH` 正确
- `CONDA_ENV=ipi`

然后直接：

```sh
sh submit_job.sh
```

### 如果你在集群上跑

你可以把：

```sh
JOB_LAUNCHER_PREFIX=srun
```

或者：

```sh
JOB_LAUNCHER_PREFIX=mpirun
```

也可以在外部包一层你自己的 batch 脚本，再在里面调用：

```sh
sh submit_job.sh
```

## 最常见的 3 类修改

### 场景 1：我只想换方法和基组

改：

```python
orcasimpleinput="B3LYP def2-SVP TightSCF"
```

例如换成：

```python
orcasimpleinput="wB97X-D3 def2-TZVP TightSCF"
```

### 场景 2：我只想多开几个核

改：

```python
orcablocks="%pal nprocs 8 end\n%maxcore 4000"
```

如果你要 16 核：

```python
orcablocks="%pal nprocs 16 end\n%maxcore 4000"
```

同时建议把：

```python
nprocs=16
maxcore=4000
```

也同步掉。

### 场景 3：我想从 AIMD 换成 PIMD

把：

```python
simulation_kind="aimd"
nbeads=1
thermostat_mode="svr"
```

改成：

```python
simulation_kind="pimd"
nbeads=16
thermostat_mode="pile_g"
```

## 常见问题

### 1. ORCA 核数改了但好像没生效

先检查你是不是只改了：

- `nprocs`

但没改：

- `orcablocks`

当前模板里，真正写进 ORCA 输入的是：

- `orcablocks`

### 2. 报 `orca executable was not found`

说明：

- `orca_command` 路径不对
- 或者这个路径没有可执行权限

先在终端检查：

```sh
ls -l /你的/orca/路径
```

### 3. 非周期分子能不能跑

能跑。

模板对 `pbc=False` 且 `cell=None` 的情况，会自动给一个默认真空盒，避免 i-PI 初始化失败。

如果你的分子比较大，建议手动把：

```python
cell=(20.0, 20.0, 20.0)
```

或者更大。

### 4. 为什么客户端里会自动出现 `Engrad`

因为 MD 需要力，ORCA 需要能返回 gradient。

模板会自动补 `Engrad`，这样更适合 AIMD / PIMD。

### 5. `submit_job.sh` 里 `conda activate` 失败

最常见原因是：

- `CONDA_SH` 路径不对

把脚本顶部的：

```sh
CONDA_SH=...
```

改成你机器上真实的 `conda.sh` 路径。

### 6. 中断后重跑失败

模板已经会清理常见的旧 unix socket。

如果你自己手动拆开跑过 `i-pi` 和客户端，仍然出问题，可以手动检查：

```sh
ls /tmp/ipi_*
```

## 测试

在项目根目录下：

```sh
python -m pytest -q
```

或者在目标环境里：

```sh
conda run -n ipi python -m pytest -q
```

## 对初学者的推荐

如果你是第一次用，最稳的顺序是：

1. 先做 `AIMD`
2. 先用 `nbeads=1`
3. 先把 `total_steps=1` 或 `10`
4. 先用小体系和小基组
5. 先执行 `--write-only`
6. 再去看生成目录里的 `ase_orca_client.py` 和 `input.xml`
7. 最后才做正式长时间计算

这样最容易定位问题到底出在：

- ORCA 路径
- ORCA 方法设置
- i-PI 配置
- socket 启动
- 结构文件

## 相关文件

- 主模板：`ipi_ase_orca_template.py`
- 示例预设：`examples/README.md`
