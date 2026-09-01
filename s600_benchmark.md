# YOLO11m S600 Benchmark指南

本文只说明如何在S600板端准备运行环境，并对同一个YOLO11m HBM分别执行：

```text
COCO bbox精度测试 + 单核CPU后处理延迟测试 + 纯BPU性能测试
```

测试口径和官方参考值见[D-Robotics Ultralytics YOLO评估说明](https://github.com/D-Robotics/rdk_model_zoo/blob/rdk_s/samples/vision/ultralytics_yolo/evaluator/README_cn.md#rdk-s600)。预处理固定使用Letterbox。

## 1. 准备S600板端文件

需要将以下内容准备到S600：

| 内容 | 用途 |
|---|---|
| `yolo11m_nashp_640x640_nv12.hbm` | BPU推理、精度与性能测试 |
| D-Robotics `rdk_model_zoo` 的 `rdk_s` 分支 | 官方运行和精度评估代码 |
| Benchmark仓库中的 `scripts/benchmark_yolo11m_s600.py` | 单核CPU后处理分段计时 |
| COCO2017 `val2017/`，共5000张 | 精度测试 |
| `instances_val2017.json` | COCO精度计算 |

本文使用以下目录。其他目录也可以，但必须同步修改后续命令：

```text
~/xcl/
├── rdk_model_zoo/
├── models/
│   └── yolo11m_int8/
│       └── yolo11m_nashp_640x640_nv12.hbm
└── coco2017/
    ├── val2017/
    └── annotations/
        └── instances_val2017.json
```

PT、ONNX、50张校准图片和PC端Docker镜像不需要传到S600。

## 2. 配置S600 Benchmark环境

S600系统需要已经包含D-Robotics板端运行时，至少能够找到：

```bash
command -v hrt_model_exec
python3 -c "import hbm_runtime; print(hbm_runtime.__file__)"
```

本次实测板端使用Python 3.12.3。创建虚拟环境时必须增加 `--system-site-packages`，让虚拟环境继承S600系统提供的 `hbm_runtime`：

```bash
cd ~/xcl
python3 -m venv --system-site-packages benchmark_venv
source ~/xcl/benchmark_venv/bin/activate
python -m pip install --upgrade pip
python -m pip install \
  numpy==1.26.4 \
  opencv-python==4.11.0.86 \
  pycocotools==2.0.11 \
  scipy==1.17.1
```

检查精度脚本需要的依赖：

```bash
python -c "import numpy, cv2, pycocotools, scipy, hbm_runtime; print('Benchmark Python environment: OK')"
```

正常输出应包含：

```text
Benchmark Python environment: OK
```

如果直接使用系统 `/usr/bin/python3` 运行精度脚本，可能出现：

```text
ModuleNotFoundError: No module named 'pycocotools'
```

因此后续精度测试应保持虚拟环境激活，或者直接使用 `~/xcl/benchmark_venv/bin/python`。纯BPU性能测试调用 `hrt_model_exec`，不依赖这个Python虚拟环境。

## 3. 测试前检查

```bash
ls -lh ~/xcl/models/yolo11m_int8/yolo11m_nashp_640x640_nv12.hbm
ls -lh ~/xcl/coco2017/annotations/instances_val2017.json
find ~/xcl/coco2017/val2017 -maxdepth 1 -type f -name '*.jpg' | wc -l
```

前两条应显示文件信息，第三条应输出 `5000`。然后确认模型能够被板端工具读取：

```bash
hrt_model_exec model_info \
  --model_file ~/xcl/models/yolo11m_int8/yolo11m_nashp_640x640_nv12.hbm
```

## 4. COCO bbox精度Benchmark

精度测试包含图片读取、Letterbox预处理、BPU推理、后处理和COCO指标计算。运行：

```bash
cd ~/xcl/rdk_model_zoo/samples/vision/ultralytics_yolo/evaluator

~/xcl/benchmark_venv/bin/python eval_yolo_det.py \
  --model-path ~/xcl/models/yolo11m_int8/yolo11m_nashp_640x640_nv12.hbm \
  --image-dir ~/xcl/coco2017/val2017 \
  --annotation ~/xcl/coco2017/annotations/instances_val2017.json \
  --conf-thres 0.25 \
  --nms-thres 0.7 \
  --json-save-path ~/xcl/coco2017/yolo11m_results.json
```

脚本遍历COCO val2017全部5000张图片。官方YOLO11m主表指标为：

| 指标 | S600官方参考值 |
|---|---:|
| AP@[0.50:0.95]，all | 0.429 |
| AP@[0.50:0.95]，small | 0.220 |
| AP@[0.50:0.95]，medium | 0.488 |
| AP@[0.50:0.95]，large | 0.610 |

`pycocotools`还会输出AP50、AP75和AR等额外指标，可以一并记录。

## 5. CPU Latency（Single Core）Benchmark

D-Robotics官方表格中的 `CPU Latency (Single Core)` 指CPU单核后处理耗时。这里使用Benchmark仓库提供的补充脚本计时；该脚本复用官方 `YoloDetect.post_process()`，只统计阈值过滤、DFL框解码、NMS和坐标恢复，不计入图片解码、Letterbox、BPU推理与COCO计算。

先把补充脚本放入官方评估目录，然后固定使用CPU 0运行：

```bash
cp <Benchmark仓库目录>/scripts/benchmark_yolo11m_s600.py \
  ~/xcl/rdk_model_zoo/samples/vision/ultralytics_yolo/evaluator/

cd ~/xcl/rdk_model_zoo/samples/vision/ultralytics_yolo/evaluator

taskset -c 0 ~/xcl/benchmark_venv/bin/python benchmark_yolo11m_s600.py \
  --model-path ~/xcl/models/yolo11m_int8/yolo11m_nashp_640x640_nv12.hbm \
  --image-dir ~/xcl/coco2017/val2017 \
  --annotation ~/xcl/coco2017/annotations/instances_val2017.json \
  --conf-thres 0.25 \
  --nms-thres 0.7 \
  --warmup 50 \
  --progress-every 500 \
  --result-json ~/xcl/benchmark_results/cpu_latency_official_results.json \
  --report-json ~/xcl/benchmark_results/cpu_latency_official_report.json
```

以报告中的 `stage_timings.postprocess.mean_ms` 作为CPU Latency，同时检查：

```text
environment.cpu_affinity = [0]
environment.single_core_requested = true
detections_per_image.images_over_100 = 0
```

官方YOLO11m参考值为 `2.0 ms`。本次补测平均值为 `1.744 ms`，处理5000张图片，单张最大检测数为59，没有图片超过100个检测结果。

## 6. 纯BPU性能Benchmark

使用同一个HBM分别测试1线程和12线程：

```bash
hrt_model_exec perf \
  --thread_num 1 \
  --model_file ~/xcl/models/yolo11m_int8/yolo11m_nashp_640x640_nv12.hbm

hrt_model_exec perf \
  --thread_num 12 \
  --model_file ~/xcl/models/yolo11m_int8/yolo11m_nashp_640x640_nv12.hbm
```

记录 `Average latency` 和 `Frame rate`：

| 线程数 | S600官方BPU Task Latency | S600官方BPU Throughput |
|---:|---:|---:|
| 1 | 2.584 ms | 384.284 FPS |
| 12 | 7.054 ms | 1642.643 FPS |

该测试只计算BPU任务，不包含JPEG解码、Letterbox、NV12转换和后处理。

## 7. 三类Benchmark的环境区别

| 测试 | 需要Python虚拟环境 | 需要COCO数据 | 需要板端BPU运行时 |
|---|---|---|---|
| COCO精度 | 是 | 是 | 是 |
| CPU单核后处理延迟 | 是 | 是 | 是；仅用于生成输出，计时不包含BPU推理 |
| `hrt_model_exec perf` | 否 | 否 | 是 |

三类测试需要分开运行，但必须使用同一个HBM文件。实际测量结果见 [benchmark_metrics.md](benchmark_metrics.md)。

## 8. 命令来源

| 文件或工具 | 来源 | 用途 |
|---|---|---|
| `eval_yolo_det.py` | D-Robotics官方仓库 | COCO bbox精度测试 |
| `benchmark_yolo11m_s600.py` | 本Benchmark仓库的补充脚本 | 复用官方后处理代码并测量单核CPU延迟 |
| `hrt_model_exec` | S600官方板端工具 | 模型检查、BPU延迟与吞吐率测试 |
