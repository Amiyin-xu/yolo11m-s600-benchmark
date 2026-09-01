# YOLO11m ONNX转S600 HBM指南

本文只说明如何在PC端运行D-Robotics OpenExplorer，将BPU友好ONNX编译成面向S600的INT8 HBM：

```text
yolo11m.onnx（FP32）
  → 50张COCO图片校准
  → OpenExplorer INT8 PTQ
  → yolo11m_nashp_640x640_nv12.hbm
```

固定条件：YOLO11m Detect、640×640、Letterbox、50张COCO校准图片、`nash-p`、INT8 PTQ、O2。

如果需要重新导出ONNX，请先阅读 [PT转ONNX指南](pt_to_onnx.md)。

## 1. 准备文件

需要获取以下两个仓库：

| 仓库 | 用途 |
|---|---|
| [D-Robotics/rdk_model_zoo `rdk_s`](https://github.com/D-Robotics/rdk_model_zoo/tree/rdk_s) | 提供官方 `mapper.py` |
| [Amiyin-xu/yolo11m-s600-benchmark](https://github.com/Amiyin-xu/yolo11m-s600-benchmark) | 提供参考ONNX和固定的50张校准图片 |

将Benchmark仓库内容放到D-Robotics项目中的对应位置：

| Benchmark仓库内容 | D-Robotics项目中的位置 |
|---|---|
| `model/yolo11m.onnx` | `samples/vision/ultralytics_yolo/model/source/yolo11m.onnx` |
| `datasets/coco2017/calibration_yolo11m_50/` | `resource/datasets/COCO2017/val2017/calibration_yolo11m_50/` |

参考ONNX信息：

| 项目 | 数据 |
|---|---|
| 文件大小 | 80,450,131 bytes |
| Opset | 19 |
| 输入/输出类型 | FLOAT32 |
| SHA-256 | `51c15134789c8fe10a53e2368de61abf056d9d900527264664d0c05a1f6a3c77` |

## 2. 运行OpenExplorer Docker环境

从[D-Robotics官方工具链页面](https://developer.d-robotics.cc/rdk_s_doc/en/Advanced_development/toolchain_development/algorithm_toolchain/overview)获取S600 OpenExplorer镜像。本次转换固定使用OpenExplorer 3.7.0 **CPU Docker**：

```text
registry.d-robotics.cc/deliver/ai_toolchain_ubuntu_22_s100_s600_cpu:v3.7.0
```

进入PC端D-Robotics项目根目录，启动容器：

```bash
docker run --rm -it \
  --network host \
  --shm-size=8g \
  --user "$(id -u):$(id -g)" \
  -e HOME=/tmp \
  -v "$PWD:/workspace" \
  -w /workspace \
  registry.d-robotics.cc/deliver/ai_toolchain_ubuntu_22_s100_s600_cpu:v3.7.0 \
  bash
```

主要参数：

| 参数 | 含义 |
|---|---|
| `--rm -it` | 使用交互式终端，退出后删除临时容器 |
| `--network host` | 容器直接使用PC网络 |
| `--shm-size=8g` | 为转换任务提供8 GiB共享内存 |
| `--user "$(id -u):$(id -g)"` | 使用当前PC用户身份写入输出文件 |
| `-e HOME=/tmp` | 将容器内用户主目录设为 `/tmp` |
| `-v "$PWD:/workspace"` | 将当前D-Robotics项目挂载到 `/workspace` |
| `-w /workspace` | 容器启动后进入 `/workspace` |
| 最后的 `bash` | 进入容器终端 |

镜像已经包含 `hb_compile`、HMCT和HBDK4，不需要在容器中重新安装工具链。

## 3. 在容器内执行转换

```bash
python3 samples/vision/ultralytics_yolo/conversion/mapper.py \
  --onnx samples/vision/ultralytics_yolo/model/source/yolo11m.onnx \
  --cal-images resource/datasets/COCO2017/val2017/calibration_yolo11m_50 \
  --output-dir outputs/yolo11m_int8 \
  --march nash-p \
  --quantized int8 \
  --cal-sample-num 50 \
  --resize-type letterbox \
  --jobs 8
```

`mapper.py` 是D-Robotics官方转换入口，内部会：

1. 将50张图片按Letterbox方式处理为校准数据。
2. 生成OpenExplorer编译配置。
3. 调用 `hb_compile` 完成INT8 PTQ和HBM编译。

## 4. 检查转换结果

生成文件：

```text
outputs/yolo11m_int8/yolo11m_nashp_640x640_nv12.hbm
```

编译日志：

```text
outputs/yolo11m_int8/hb_compile.log
```

正常结束时日志应包含：

```text
Successfully compile the hbm model
HBDK hbm perf SUCCESS
The hb_compile completes running.
```

当前模型的外部输入是NV12 UINT8，BPU网络内部主要使用INT8定点计算，6个检测头输出为FLOAT32。完成检查后输入 `exit` 退出容器。

HBM编译完成后，按照 [S600 Benchmark指南](s600_benchmark.md) 配置板端环境并测试精度与BPU性能。

## 5. 命令来源

| 文件或工具 | 来源 | 用途 |
|---|---|---|
| `mapper.py` | D-Robotics官方仓库 | 准备校准数据并调用OpenExplorer编译HBM |
| `hb_compile` | D-Robotics OpenExplorer | INT8 PTQ与S600 HBM编译 |
