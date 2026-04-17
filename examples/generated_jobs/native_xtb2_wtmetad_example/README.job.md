# native_xtb2_wtmetad_example

这是仓库里唯一保留的标准生成示例。

- simulation kind: aimd
- ensemble: nvt
- thermostat: langevin
- beads: 1
- timestep: 1.0 fs
- total steps: 120
- socket mode: unix
- ORCA command: orca
- ORCA method: Native-XTB2
- PLUMED enabled: True
- PLUMED input: plumed.dat
- CV: `ANGLE ATOMS=2,1,3`
- bias: WT-Metad

## 推荐先看

- `input.xml`
  i-PI 主输入，已经接好 `ffsocket`、`ffplumed`、`bias` 和 `smotion`
- `plumed.dat`
  这里定义了角度 CV、`METAD` 和 `PRINT`
- `submit_job.sh`
  最接近真实使用场景的启动方式
- `logs/ipi.log`
  i-PI + PLUMED 侧日志
- `logs/client.log`
  ASE + ORCA 客户端日志
- `native_xtb2_wtmetad_example.out`
  i-PI 主输出
- `COLVAR`
  CV 和 bias 输出
- `HILLS`
  第一颗 hill 已经写入
- `orca_native_xtb2/orca.inp`
  实际写出的 ORCA 输入
- `orca_native_xtb2/orca.out`
  实际 ORCA 输出

## Commands

```sh
sh run_all.sh
sh submit_job.sh
```

## 说明

- 这个目录里的日志和结果已经做过路径脱敏，不包含本机用户名和绝对安装路径。
- 我只保留了最主要的输入、脚本、结果和日志，删掉了不利于阅读的中间文件。
