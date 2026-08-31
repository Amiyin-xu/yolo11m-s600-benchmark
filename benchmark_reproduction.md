# S600 YOLO11m Benchmark 复现指南

本指南只复现下面这条流程：

```text
yolo11m.pt（FP32）
  → BPU友好ONNX（FP32）
  → S600 HBM（INT8 PTQ）
  → COCO精度测试 + 纯BPU性能测试
```

固定条件：YOLO11m Detect、640×640、80类、Letterbox、50张COCO校准图片、S600 `nash-p`、INT8 PTQ、O2。

## 1. 准备文件

这里只提供下载地址，不提供下载命令。后续可把下表中的文件统一打包到自己的GitHub仓库。

| 内容 | 下载地址或来源 |
|---|---|
| D-Robotics官方 `rdk_s` 项目 | [D-Robotics/rdk_model_zoo](https://github.com/D-Robotics/rdk_model_zoo/tree/rdk_s) |
| `yolo11m.pt` | [Hugging Face：Ultralytics/YOLO11](https://huggingface.co/Ultralytics/YOLO11/blob/main/yolo11m.pt) |
| COCO2017验证图片 | [val2017.zip](https://images.cocodataset.org/zips/val2017.zip) |
| COCO2017标注 | [annotations_trainval2017.zip](https://images.cocodataset.org/annotations/annotations_trainval2017.zip) |
| S600 OpenExplorer工具链 | [D-Robotics S600工具链说明](https://developer.d-robotics.cc/rdk_s_doc/en/Advanced_development/toolchain_development/algorithm_toolchain/overview) |
| 官方Benchmark说明 | [D-Robotics evaluator README](https://github.com/D-Robotics/rdk_model_zoo/blob/rdk_s/samples/vision/ultralytics_yolo/evaluator/README_cn.md#rdk-s600) |

建议资源包包含：

```text
yolo11m.pt
val2017/                         # 5000张精度测试图片
instances_val2017.json
calibration_yolo11m_50/         # 固定的50张校准图片
rdk-yolo-export-py310.tar       # PT转ONNX环境
ai_toolchain_ubuntu_22_s100_s600_cpu_v3.7.0.tar
```

当前使用的权重信息：

| 项目 | 数据 |
|---|---|
| 文件大小 | 40,684,120 bytes |
| SHA-256 | `d5ffc1a674953a08e11a8d21e022781b1b23a19b730afc309290bd9fb5305b95` |
| 模型 | YOLO11m Detect，80类 |
| 权重张量精度 | FP32 |

## 2. 运行Docker环境

本指南假设Docker和两个离线镜像已经准备好，不介绍Docker安装或镜像下载过程。所有命令均在PC端项目根目录执行。

### PT转ONNX环境

```bash
docker run --rm -it \
  --user "$(id -u):$(id -g)" \
  -e HOME=/tmp \
  -v "$PWD:/workspace" \
  -w /workspace \
  rdk-yolo-export:py310 bash
```

该镜像包含Python 3.10、PyTorch CPU、Ultralytics、ONNX和ONNX Runtime。

### ONNX转HBM环境

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

该镜像已经包含 `hb_compile`、HMCT和HBDK4，不需要在容器中另行安装工具链。

## 3. PT转ONNX

把权重放到：

```text
samples/vision/ultralytics_yolo/model/source/yolo11m.pt
```

进入PT转ONNX容器后运行：

```bash
python3 samples/vision/ultralytics_yolo/conversion/export_monkey_patch.py \
  --pt samples/vision/ultralytics_yolo/model/source/yolo11m.pt
```

生成文件：

```text
samples/vision/ultralytics_yolo/model/source/yolo11m.onnx
```

`export_monkey_patch.py` 是D-Robotics官方脚本。它调用Ultralytics导出，并将YOLO11检测头改成适合BPU部署的6输出结构。实际转换命令只有上面这一条；Docker命令只是启动运行环境。

当前参考ONNX为opset 19，输入和6个输出均为FLOAT32，SHA-256为：

```text
51c15134789c8fe10a53e2368de61abf056d9d900527264664d0c05a1f6a3c77
```

## 4. ONNX转INT8 HBM

将固定的50张校准图片放到：

```text
resource/datasets/COCO2017/val2017/calibration_yolo11m_50/
```

进入OpenExplorer容器后运行：

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

生成文件：

```text
outputs/yolo11m/yolo11m_nashp_640x640_nv12.hbm
```

`mapper.py` 是D-Robotics官方转换入口，内部会完成以下工作：

1. 将50张图片按Letterbox方式处理成校准数据。
2. 生成OpenExplorer编译配置。
3. 调用官方 `hb_compile` 完成INT8 PTQ和HBM编译。

命令换行较多只是为了明确固定实验条件，并不是手工执行多级转换。`nash-p`、INT8、50张校准图和Letterbox是与当前S600实验对齐的必要条件；O2使用脚本默认值。

最终模型的外部输入是NV12 UINT8，BPU网络内部主要使用INT8定点计算，6个检测头输出为FLOAT32。

## 5. 需要放到S600的文件

只需要将以下内容准备到S600，不需要传输PT、ONNX、校准图片或PC端Docker镜像：

| 内容 | 用途 |
|---|---|
| `yolo11m_nashp_640x640_nv12.hbm` | BPU推理与性能测试 |
| 当前 `rdk_model_zoo` 项目 | 提供官方运行和精度评估代码 |
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

板端需要能导入NumPy、OpenCV、未经修改的 `pycocotools` 和 `hbm_runtime`，并能调用 `hrt_model_exec`。

## 6. 官方口径Benchmark

精度测试和纯BPU性能测试是两次独立测试，但必须使用同一个HBM文件。

### 6.1 COCO bbox精度

在S600上运行D-Robotics官方精度脚本：

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

该脚本默认使用Letterbox，并按照官方条件遍历COCO val2017全部5000张图片。需要对齐的官方指标是：

| 指标 | S600官方参考值 |
|---|---:|
| AP@[0.50:0.95]，all | 0.429 |
| AP@[0.50:0.95]，small | 0.220 |
| AP@[0.50:0.95]，medium | 0.488 |
| AP@[0.50:0.95]，large | 0.610 |

`pycocotools`还会输出AP50、AP75和AR等数据，可以作为额外指标记录，但官方YOLO11m主表使用上面4项。

### 6.2 纯BPU性能

在S600上使用官方 `hrt_model_exec perf` 分别测试1线程和12线程：

```bash
hrt_model_exec perf \
  --thread_num 1 \
  --model_file ~/xcl/models/yolo11m_nashp_640x640_nv12.hbm

hrt_model_exec perf \
  --thread_num 12 \
  --model_file ~/xcl/models/yolo11m_nashp_640x640_nv12.hbm
```

需要记录 `Average latency` 和 `Frame rate`：

| 线程数 | S600官方BPU Task Latency | S600官方BPU Throughput |
|---:|---:|---:|
| 1 | 2.584 ms | 384.284 FPS |
| 12 | 7.054 ms | 1642.643 FPS |

该测试只计算从提交BPU任务到等待任务完成的时间，不包含JPEG解码、Letterbox、NV12转换和后处理。

## 7. 命令来源

| 文件或工具 | 来源 | 用途 |
|---|---|---|
| `export_monkey_patch.py` | D-Robotics官方仓库 | PT转BPU友好ONNX |
| `mapper.py` | D-Robotics官方仓库 | 准备校准数据并调用OpenExplorer编译HBM |
| `eval_yolo_det.py` | D-Robotics官方仓库 | COCO bbox精度测试 |
| `hrt_model_exec perf` | S600官方板端工具 | BPU任务延迟与吞吐率测试 |

本指南没有重新实现转换或官方Benchmark，只是为YOLO11m明确了文件路径和复现参数。实际测量结果见 [benchmark_metrics.md](benchmark_metrics.md)。
