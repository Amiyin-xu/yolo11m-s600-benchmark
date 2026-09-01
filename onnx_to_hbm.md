# YOLO11m ONNX转S600 HBM与Benchmark指南

本文说明如何在PC端使用D-Robotics OpenExplorer，将BPU友好ONNX转换为S600 INT8 HBM，并在S600上执行官方口径的精度与BPU性能测试：

```text
yolo11m.onnx（FP32）
  → OpenExplorer INT8 PTQ
  → S600 HBM
  → COCO精度测试 + 纯BPU性能测试
```

固定条件：YOLO11m Detect、640×640、80类、Letterbox、50张COCO校准图片、S600 `nash-p`、INT8 PTQ、O2。

如果需要重新导出ONNX，请先阅读 [PT转ONNX指南](pt_to_onnx.md)。Benchmark仓库也已提供参考文件 `model/yolo11m.onnx`。

## 1. 准备文件

需要获取以下两个仓库：

| 仓库 | 用途 |
|---|---|
| [D-Robotics/rdk_model_zoo `rdk_s`](https://github.com/D-Robotics/rdk_model_zoo/tree/rdk_s) | 提供官方转换、运行和评估代码 |
| [Amiyin-xu/yolo11m-s600-benchmark](https://github.com/Amiyin-xu/yolo11m-s600-benchmark) | 提供参考ONNX、COCO验证集、标注、50张校准图片和测试结果 |

将Benchmark仓库内容放到D-Robotics项目中的对应位置：

| Benchmark仓库内容 | D-Robotics项目中的位置 |
|---|---|
| `model/yolo11m.onnx` | `samples/vision/ultralytics_yolo/model/source/yolo11m.onnx` |
| `datasets/coco2017/val2017/` | `resource/datasets/COCO2017/val2017/` |
| `datasets/coco2017/annotations/instances_val2017.json` | `resource/datasets/COCO2017/annotations/instances_val2017.json` |
| `datasets/coco2017/calibration_yolo11m_50/` | `resource/datasets/COCO2017/val2017/calibration_yolo11m_50/` |

参考ONNX信息：

| 项目 | 数据 |
|---|---|
| 文件大小 | 80,450,131 bytes |
| Opset | 19 |
| 输入/输出类型 | FLOAT32 |
| SHA-256 | `51c15134789c8fe10a53e2368de61abf056d9d900527264664d0c05a1f6a3c77` |

## 2. 运行OpenExplorer Docker环境

从[D-Robotics官方工具链页面](https://developer.d-robotics.cc/rdk_s_doc/en/Advanced_development/toolchain_development/algorithm_toolchain/overview)获取S600 OpenExplorer镜像。本次转换固定使用OpenExplorer 3.7.0 CPU Docker：

```text
registry.d-robotics.cc/deliver/ai_toolchain_ubuntu_22_s100_s600_cpu:v3.7.0
```

这里的CPU/GPU表示PC端模型转换使用的资源，不是S600板端BPU的类型。为了复现本文结果，应使用上述CPU镜像。GPU镜像可能加速PC端部分转换流程，但不会直接提高生成HBM的板端BPU性能；如果更换镜像，应重新验证精度和性能。

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
| `--network host` | 容器直接使用PC的网络 |
| `--shm-size=8g` | 为转换任务提供8 GiB共享内存 |
| `--user "$(id -u):$(id -g)"` | 使用当前PC用户身份写入输出文件 |
| `-e HOME=/tmp` | 将容器内用户主目录设为 `/tmp` |
| `-v "$PWD:/workspace"` | 将当前D-Robotics项目挂载为 `/workspace` |
| `-w /workspace` | 容器启动后进入 `/workspace` |
| 最后的 `bash` | 进入容器终端 |

镜像已经包含 `hb_compile`、HMCT和HBDK4，不需要在容器内重新安装工具链。

## 3. 在容器内将ONNX转换为HBM

```bash
python3 samples/vision/ultralytics_yolo/conversion/mapper.py \
  --onnx samples/vision/ultralytics_yolo/model/source/yolo11m.onnx \
  --cal-images resource/datasets/COCO2017/val2017/calibration_yolo11m_50 \
  --output-dir outputs/yolo11m \
  --march nash-p \
  --quantized int8 \
  --cal-sample-num 50 \
  --resize-type letterbox \
  --jobs 8
```

`mapper.py` 是D-Robotics官方转换入口，内部执行：

1. 将50张图片按Letterbox方式处理为校准数据。
2. 生成OpenExplorer编译配置。
3. 调用 `hb_compile` 完成INT8 PTQ和HBM编译。

生成文件：

```text
outputs/yolo11m/yolo11m_nashp_640x640_nv12.hbm
```

最终模型的外部输入是NV12 UINT8，BPU网络内部主要使用INT8定点计算，6个检测头输出为FLOAT32。完成后输入 `exit` 退出容器。

## 4. 准备S600板端文件

只需要将以下内容准备到S600，不需要传输PT、ONNX、校准图片或PC端Docker镜像：

| 内容 | 用途 |
|---|---|
| `yolo11m_nashp_640x640_nv12.hbm` | BPU推理与性能测试 |
| 当前 `rdk_model_zoo` 项目 | 官方运行和精度评估代码 |
| COCO2017 `val2017/`，共5000张 | 精度测试 |
| `instances_val2017.json` | pycocotools精度计算 |

建议板端目录：

```text
~/xcl/
├── rdk_model_zoo/
├── models/
│   └── yolo11m_nashp_640x640_nv12.hbm
└── coco2017/
    ├── val2017/
    └── annotations/
        └── instances_val2017.json
```

板端需要能够导入NumPy、OpenCV、未经修改的 `pycocotools` 和 `hbm_runtime`，并能调用 `hrt_model_exec`。

## 5. 官方口径Benchmark

测试口径和官方参考值见[D-Robotics Ultralytics YOLO评估说明](https://github.com/D-Robotics/rdk_model_zoo/blob/rdk_s/samples/vision/ultralytics_yolo/evaluator/README_cn.md#rdk-s600)。精度测试和纯BPU性能测试是两次独立测试，但必须使用同一个HBM文件。

### 5.1 COCO bbox精度

在S600上执行：

```bash
cd ~/xcl/rdk_model_zoo/samples/vision/ultralytics_yolo/evaluator

python3 eval_yolo_det.py \
  --model-path ~/xcl/models/yolo11m_nashp_640x640_nv12.hbm \
  --image-dir ~/xcl/coco2017/val2017 \
  --annotation ~/xcl/coco2017/annotations/instances_val2017.json \
  --conf-thres 0.25 \
  --nms-thres 0.7 \
  --json-save-path ~/xcl/coco2017/yolo11m_results.json
```

脚本默认使用Letterbox并遍历COCO val2017全部5000张图片。官方YOLO11m主表指标为：

| 指标 | S600官方参考值 |
|---|---:|
| AP@[0.50:0.95]，all | 0.429 |
| AP@[0.50:0.95]，small | 0.220 |
| AP@[0.50:0.95]，medium | 0.488 |
| AP@[0.50:0.95]，large | 0.610 |

### 5.2 纯BPU性能

```bash
hrt_model_exec perf \
  --thread_num 1 \
  --model_file ~/xcl/models/yolo11m_nashp_640x640_nv12.hbm

hrt_model_exec perf \
  --thread_num 12 \
  --model_file ~/xcl/models/yolo11m_nashp_640x640_nv12.hbm
```

记录 `Average latency` 和 `Frame rate`：

| 线程数 | S600官方BPU Task Latency | S600官方BPU Throughput |
|---:|---:|---:|
| 1 | 2.584 ms | 384.284 FPS |
| 12 | 7.054 ms | 1642.643 FPS |

该测试不包含JPEG解码、Letterbox、NV12转换和后处理。实际测量结果见 [benchmark_metrics.md](benchmark_metrics.md)。

## 6. 命令来源

| 文件或工具 | 来源 | 用途 |
|---|---|---|
| `mapper.py` | D-Robotics官方仓库 | 准备校准数据并调用OpenExplorer编译HBM |
| `eval_yolo_det.py` | D-Robotics官方仓库 | COCO bbox精度测试 |
| `hrt_model_exec perf` | S600官方板端工具 | BPU任务延迟与吞吐率测试 |
