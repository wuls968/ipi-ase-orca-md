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

## 仓库里有什么

- `ipi_ase_orca_template.py`
  主模板，绝大多数情况下你只需要改这个文件
- `tests/test_template.py`
  回归测试
- `examples/native_xtb2_wtmetad_5ps.py`
  一个可直接生成 `Native-XTB2 + WT-Metad` 作业的示例脚本
- `examples/native_xtb2_distance_restraint.py`
  一个 `PLUMED DISTANCE + RESTRAINT` 的轻量示例
- `examples/native_xtb2_distance_metad.py`
  一个 `PLUMED DISTANCE + METAD` 的轻量示例
- `examples/native_xtb2_angle_windows.py`
  一个 `PLUMED ANGLE + LOWER/UPPER_WALLS` 的轻量示例
- `examples/README.md`
  所有示例脚本的说明、适用场景和命令
- `examples/generated_jobs/native_xtb2_wtmetad_example/`
  一个已经实际跑过、并且整理过的标准示例目录

## 代表性例子从哪里开始看

如果你不想一上来就手改完整模板，建议先直接看：

- `examples/README.md`

这里已经把代表性例子分成了几类：

- 最简单的 `DISTANCE + RESTRAINT`
- 最小 metadynamics 的 `DISTANCE + METAD`
- 角度有界采样的 `ANGLE + WALLS`
- 更完整的 `WT-Metad` 参考例子

建议研究人员按下面顺序上手：

1. 先跑 `distance_restraint --run --smoke`
2. 再跑 `distance_metad --run --smoke`
3. 再跑 `angle_windows --run --smoke`
4. 最后再看 `wtmetad_5ps --run --hill-smoke`

这样可以先确认耦合链路，再逐步进入真正的增强采样设置。

## 可移植性和隐私

仓库现在默认不再写死任何个人机器专属路径。

- 默认 `orca_command` 是 `orca`
- `submit_job.sh` 会优先自动探测 `conda.sh`
- 示例目录里的结果和日志已经做过路径清理

如果你的 `orca` 不在 `PATH` 上，可以：

- 在配置里把 `orca_command` 改成真实路径
- 或者运行前设置环境变量 `ORCA_COMMAND=/path/to/orca`

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

## 先看这里：你实际要改哪里

打开 `ipi_ase_orca_template.py` 后，直接看文件顶部的 `USER TUNING SECTION`。

绝大多数研究场景只需要改这里，不需要往下改模板逻辑：

- `USER_JOB_NAME`
- `USER_STRUCTURE_XYZ_PATH`
- `USER_CHARGE` / `USER_MULTIPLICITY`
- `USER_SIMULATION_KIND`
- `USER_ENSEMBLE`
- `USER_NBEADS`
- `USER_TEMPERATURE_K`
- `USER_TIMESTEP_FS`
- `USER_TOTAL_STEPS`
- `USER_THERMOSTAT_MODE`
- `USER_ORCA_COMMAND`
- `USER_ORCA_SIMPLEINPUT`
- `USER_ORCA_NPROCS`
- `USER_ORCA_MAXCORE_MB`
- `USER_ORCA_BLOCKS`
- `USER_PLUMED_ENABLED`

### `USER TUNING SECTION` 逐项详细说明

下面这些就是研究人员最常需要自己改的参数。建议先看完这一节，再开始改模板。

#### 1. `USER_JOB_NAME`

作用：
- 作业名字
- 生成目录名默认就是 `jobs/<USER_JOB_NAME>/`
- 输出文件前缀、日志阅读、后续归档时都会经常看到它

什么时候要改：
- 几乎每次新任务都建议改
- 你想区分不同方法、不同温度、不同体系时一定要改

建议写法：
- 用简短、稳定、可搜索的名字
- 推荐包含体系 + 方法 + 任务类型

示例：
- `h2o_aimd_test`
- `glycine_pimd_300k`
- `reaction1_metad_window_a`

#### 2. `USER_WORK_ROOT`

作用：
- 所有生成作业目录的父目录

什么时候要改：
- 默认 `jobs` 就够用时不用改
- 如果你想把所有结果集中放到别的目录，可以改

示例：
- `Path("jobs")`
- `Path("production_jobs")`

#### 3. `USER_STRUCTURE_XYZ_PATH`

作用：
- 指向结构 xyz 文件的绝对路径
- 这是现在唯一允许的结构输入方式

什么时候要改：
- 几乎每次换体系都要改

硬性要求：
- 必须是绝对路径
- 必须指向真实存在的 `.xyz` 文件
- xyz 文件里的元素顺序就是后续 PLUMED 原子编号对应的顺序

建议：
- 先用已经优化过或至少合理的初始结构
- 如果后面要写 PLUMED，先确认原子编号

示例：
- `Path("/absolute/path/to/h2o.xyz")`
- `Path("/absolute/path/to/reactant_conf01.xyz")`

#### 4. `USER_CHARGE`

作用：
- 体系总电荷

什么时候要改：
- 中性体系通常用 `0`
- 阳离子、阴离子体系必须改对

常见示例：
- `0`：中性分子
- `1`：单正离子
- `-1`：单负离子

#### 5. `USER_MULTIPLICITY`

作用：
- 自旋多重度

什么时候要改：
- 闭壳层体系通常是 `1`
- 开壳层体系必须按电子自旋状态设置

常见示例：
- `1`：singlet
- `2`：doublet
- `3`：triplet

注意：
- 这个值必须和你的体系电子态一致
- 如果这里错了，ORCA 结果可能完全不对

#### 6. `USER_SIMULATION_KIND`

作用：
- 选择跑 `aimd` 还是 `pimd`

可选值：
- `"aimd"`
- `"pimd"`

如何选：
- 只想做普通从头分子动力学：`aimd`
- 想考虑核量子效应：`pimd`

建议：
- 第一次通链路请先用 `aimd`

#### 7. `USER_ENSEMBLE`

作用：
- 选择动力学系综

可选值：
- `"nve"`
- `"nvt"`

如何选：
- 只想守恒能量、做最简单动力学：`nve`
- 想稳定温度、最适合大多数新手测试：`nvt`

建议：
- 第一次 smoke test 用 `nvt`

#### 8. `USER_NBEADS`

作用：
- bead 数

如何理解：
- `aimd` 通常应设为 `1`
- `pimd` 需要 `>= 2`

建议：
- 链路测试：`1`
- 轻量 PIMD：`8` 或 `16`
- 生产计算根据温度和体系再定

#### 9. `USER_TEMPERATURE_K`

作用：
- 温度，单位 Kelvin

什么时候要改：
- 几乎所有正式计算都要确认

常见值：
- `300.0`
- `200.0`
- `500.0`

#### 10. `USER_TIMESTEP_FS`

作用：
- 时间步长，单位飞秒 fs

如何选：
- 太大可能积分不稳定
- 太小会让计算特别慢

经验建议：
- 普通小分子 AIMD 常从 `0.5` fs 开始
- 更激烈的体系可以更小
- 不确定时优先保守一点

#### 11. `USER_TOTAL_STEPS`

作用：
- 总步数

如何选：
- 纯 smoke test：`1` 到 `20`
- 小测试：`50` 到 `200`
- 正式动力学：按目标物理时间换算

提示：
- 总物理时间约等于 `USER_TOTAL_STEPS × USER_TIMESTEP_FS`

#### 12. `USER_THERMOSTAT_MODE`

作用：
- thermostat 模式

常见组合：
- `aimd + nvt`：通常用 `"svr"` 或 `"langevin"`
- `pimd + nvt`：通常用 `"pile_g"` 或 `"pile_l"`

建议：
- 第一次 AIMD 测试：`svr`
- 现有默认 PIMD：`pile_g`

#### 13. `USER_ORCA_COMMAND`

作用：
- ORCA 可执行程序路径或命令名

什么时候要改：
- 如果 `orca` 已经在 PATH 上，可以不改
- 如果不在 PATH 上，改成绝对路径

示例：
- `"orca"`
- `"/Users/a0000/Library/orca_6_1_0/orca"`

#### 14. `USER_ORCA_SIMPLEINPUT`

作用：
- ORCA 输入文件中 `!` 后面的主方法字符串

这里通常决定：
- 方法
- 基组
- SCF 精度
- 是否加一些简单关键词

示例：
- `"B3LYP def2-SVP TightSCF"`
- `"r2SCAN-3c TightSCF"`
- `"Native-XTB2 TightSCF"`

建议：
- 先用轻量方法通链路，再换正式方法

#### 15. `USER_ORCA_NPROCS`

作用：
- 希望使用的 ORCA 核数

注意：
- 这个字段应该和 `USER_ORCA_BLOCKS` 里的 `%pal nprocs` 保持一致

建议：
- 本地轻量测试：`1`
- 正式任务按机器资源调整

#### 16. `USER_ORCA_MAXCORE_MB`

作用：
- ORCA 每核可用内存，单位 MB

注意：
- 这个字段也应该和 `USER_ORCA_BLOCKS` 里的 `%maxcore` 保持一致

建议：
- 轻量测试可先用 `800`、`1000` 或 `2000`
- 正式任务按真实机器内存调整

#### 17. `USER_ORCA_BLOCKS`

作用：
- ORCA 输入文件中的 block 文本
- 真正写进 ORCA 输入文件的是这里

最常见内容：
- `%pal nprocs ... end`
- `%maxcore ...`

示例：
```python
USER_ORCA_BLOCKS = "%pal nprocs 4 end\n%maxcore 2000"
```

重要提醒：
- 实际并行核数和内存设置，以这里为准
- 所以 `USER_ORCA_NPROCS` / `USER_ORCA_MAXCORE_MB` 最好只是和这里保持同步，方便人读

#### 18. `USER_JOB_LAUNCHER_PREFIX`

作用：
- 给客户端启动命令前面加前缀
- 常用于集群绑定 CPU、NUMA、任务调度器包装器等场景

什么时候要改：
- 本地测试通常不用改，留空即可
- 特殊 HPC 环境再改

示例：
- `""`
- `"taskset -c 0-7"`

#### 19. `USER_PLUMED_ENABLED`

作用：
- 是否启用 PLUMED 偏置/增强采样接口

可选值：
- `False`
- `True`

什么时候要改：
- 普通 AIMD / PIMD 不加偏置时：`False`
- 你要做 metad / restraint / walls / umbrella 类工作时：`True`

注意：
- 打开后请检查生成目录中的 `plumed.dat`
- 真正的 CV 和 bias 细节主要还是在 `plumed.dat` 里改

如果你只是想先做一个最小链路 smoke test，建议先把顶部参数改成下面这样：

- `USER_SIMULATION_KIND="aimd"`
- `USER_ENSEMBLE="nvt"`
- `USER_NBEADS=1`
- `USER_THERMOSTAT_MODE="svr"`
- `USER_TOTAL_STEPS=1`
- 用一个很小的分子和轻量方法/基组

## 5 分钟上手

### 1. 准备环境

建议直接使用 `conda` 环境 `ipi`：

```sh
conda activate ipi
```

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

### 2. 改顶部 `USER TUNING SECTION`

打开：

- `ipi_ase_orca_template.py`

然后只改文件最上面的 `USER TUNING SECTION`。

第一次建议至少确认下面这些值：

- `USER_JOB_NAME`
- `USER_STRUCTURE_XYZ_PATH`
- `USER_ORCA_COMMAND`
- `USER_ORCA_SIMPLEINPUT`
- `USER_ORCA_BLOCKS`
- `USER_SIMULATION_KIND`
- `USER_NBEADS`
- `USER_TOTAL_STEPS`

### 3. 先打印配置，再做 doctor

```sh
conda activate ipi
python ipi_ase_orca_template.py --print-config
python ipi_ase_orca_template.py --doctor
```

`--print-config` 会把当前脚本配置直接打印成 JSON，方便确认最终值。

`--doctor` 会做这几件事：

- 检查当前配置能否通过验证
- 检查 `i-pi` 是否可执行
- 检查 `orca` 是否可执行
- 检查当前 Python 环境是否能导入 `ase`（启用 PLUMED 时也会检查 `plumed`）

如果失败，脚本现在会直接告诉你：

- 对应的 `job dir`
- 应该先改哪类配置
- 应该先看哪个日志
- 相关错误摘录

### 4. 只生成作业，不启动

第一次建议先这样做：

```sh
conda activate ipi
python ipi_ase_orca_template.py --write-only
```

默认会在：

- `jobs/<USER_JOB_NAME>/`

下面生成一套文件。

### 5. 本地 smoke test

如果你已经把顶部参数改成一个最小测试配置，可以直接：

```sh
conda activate ipi
python ipi_ase_orca_template.py --run
```

或者先生成再进目录：

```sh
conda activate ipi
python ipi_ase_orca_template.py --write-only
cd jobs/<USER_JOB_NAME>
sh run_all.sh
```

运行失败时，终端报错现在会带上：

- `job dir`
- `logs/client.log`
- `logs/ipi.log`
- 最近几行日志摘录

### 6. 用提交辅助脚本启动

更推荐的方式是进入生成目录后运行：

```sh
conda activate ipi
cd jobs/<USER_JOB_NAME>
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

现在模板只保留一种方式：

- 通过 xyz 文件的绝对路径读取

例子：

```python
structure=StructureSettings(
    xyz_path=Path("/absolute/path/to/your_structure.xyz"),
    charge=0,
    multiplicity=1,
    cell=None,
    pbc=False,
)
```

注意：

- 必须是绝对路径
- 必须指向真实存在的 `.xyz` 文件
- 模板不再支持把 xyz 坐标直接内嵌在脚本里

### 2. ORCA 可执行文件在哪里

改这里：

```python
orca_command="orca"
```

如果你的 `orca` 已经在 `PATH` 上，直接用这个默认值就可以。

如果没有在 `PATH` 上，你再把它改成你机器上的真实路径。

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

## PLUMED 增强采样怎么用

模板现在已经支持 `i-PI + PLUMED` 的直连模式。

你需要做的事情非常简单：

1. 在配置里把 `plumed.enabled` 设成 `True`
2. 生成作业目录
3. 打开生成出来的 `plumed.dat`
4. 把你自己的 `CV / METAD / OPES / RESTRAINT / PRINT` 写进去
5. 直接运行 `sh submit_job.sh` 或 `python ... --run`

也就是说，Python 模板负责把：

- `ffplumed`
- `ensemble/bias`
- 可选 `smotion metad`

这些 `i-PI` 侧连接都提前接好；你主要改的还是 `plumed.dat` 本身。

### 最小配置长什么样

如果你希望启用增强采样，至少需要：

```python
plumed=PlumedSettings(
    enabled=True,
    input_filename="plumed.dat",
    source_path=None,
    source_string=None,
    bias_name="plumed",
    bias_nbeads=1,
    plumed_step=0,
    compute_work=True,
    use_metad_smotion=True,
    plumed_extras=(),
)
```

生成作业后，你会看到一个：

- `plumed.dat`

它可以直接改。

### 一个现成例子

项目里已经带了一个可直接参考的示例：

- `examples/native_xtb2_wtmetad_5ps.py`

这个例子使用：

- `ORCA Native-XTB2`
- `H2O`
- `WT-Metad`
- `ANGLE ATOMS=2,1,3` 作为 CV

建议这样验证：

```sh
conda run -n ipi python examples/native_xtb2_wtmetad_5ps.py --run --smoke
```

如果你想确认第一颗 hill 已经写入：

```sh
conda run -n ipi python examples/native_xtb2_wtmetad_5ps.py --run --hill-smoke
```

因为这个例子的默认 `PACE=100`，所以 `120` 步短跑足够看到第一条 `HILLS` 记录。

仓库里现在也只保留了一个整理好的生成示例目录：

- `examples/generated_jobs/native_xtb2_wtmetad_example`

这个目录不是调试残留，而是一个已经实际跑过、适合直接参考文件结构和结果格式的标准示例。

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
  通过 xyz 文件的绝对路径读取结构
- `charge`
  总电荷
- `multiplicity`
  自旋多重度
- `cell`
  盒子大小，格式如 `(20.0, 20.0, 20.0)`
- `pbc`
  是否周期性

说明：

- `xyz_path` 必须是绝对路径
- `xyz_path` 必须指向真实存在的 `.xyz` 文件
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

- `CONDA_ENV`
- `ORCA_COMMAND`
- `JOB_LAUNCHER_PREFIX`

### 如果你在本机直接跑

通常只要保证：

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

- 当前 shell 环境里找不到 `conda`

现在脚本会先自动探测 `conda.sh`。

如果你的环境比较特殊，再手动指定：

```sh
CONDA_SH=/path/to/conda.sh sh submit_job.sh
```

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
