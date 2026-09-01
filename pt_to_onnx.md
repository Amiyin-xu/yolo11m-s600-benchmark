# YOLO11m PT转ONNX指南

本文说明如何在PC端将官方 `yolo11m.pt` 导出为适合D-Robotics BPU部署的ONNX：

```text
yolo11m.pt（FP32） → BPU友好ONNX（FP32、6输出）
```

## 1. 准备文件

需要获取以下两个仓库：

| 仓库 | 用途 |
|---|---|
| [D-Robotics/rdk_model_zoo `rdk_s`](https://github.com/D-Robotics/rdk_model_zoo/tree/rdk_s) | 提供官方 `export_monkey_patch.py` |
| [Amiyin-xu/yolo11m-s600-benchmark](https://github.com/Amiyin-xu/yolo11m-s600-benchmark) | 提供权重、参考ONNX和环境配置文件 |

将Benchmark仓库中的权重放到D-Robotics项目：

```text
来源：model/yolo11m.pt
目标：samples/vision/ultralytics_yolo/model/source/yolo11m.pt
```

权重信息：

| 项目 | 数据 |
|---|---|
| 文件大小 | 40,684,120 bytes |
| SHA-256 | `d5ffc1a674953a08e11a8d21e022781b1b23a19b730afc309290bd9fb5305b95` |
| 模型 | YOLO11m Detect，80类 |
| 权重张量精度 | FP32 |

## 2. 方法一：使用Conda环境

本方法假设PC已经安装Anaconda。在Benchmark仓库根目录创建Python 3.10环境并安装固定依赖：

```bash
conda create -n yolo11m-export python=3.10 -y
conda activate yolo11m-export
python -m pip install --upgrade pip
python -m pip install -r environment/requirements-pt2onnx.txt
```

检查环境：

```bash
python --version
python -c "import torch, ultralytics, onnx, onnxruntime; print(torch.__version__, ultralytics.__version__, onnx.__version__, onnxruntime.__version__)"
```

保持环境激活，进入D-Robotics项目根目录执行：

```bash
python3 samples/vision/ultralytics_yolo/conversion/export_monkey_patch.py \
  --pt samples/vision/ultralytics_yolo/model/source/yolo11m.pt
```

完成后退出环境：

```bash
conda deactivate
```

## 3. 方法二：使用自建Docker环境（本次实际方案）

`rdk-yolo-export:py310` 不是D-Robotics官方镜像，而是本项目为了隔离Python依赖自行创建的镜像。Benchmark仓库提供：

```text
environment/requirements-pt2onnx.txt
environment/rdk-yolo-export-py310.Dockerfile
```

### 3.1 构建镜像

在Benchmark仓库根目录执行：

```bash
docker build \
  -t rdk-yolo-export:py310 \
  -f environment/rdk-yolo-export-py310.Dockerfile \
  environment
```

确认镜像存在：

```bash
docker image inspect rdk-yolo-export:py310
```

### 3.2 启动容器

进入PC端D-Robotics项目根目录，然后执行：

```bash
docker run --rm -it \
  --user "$(id -u):$(id -g)" \
  -e HOME=/tmp \
  -v "$PWD:/workspace" \
  -w /workspace \
  rdk-yolo-export:py310 \
  bash
```

参数说明：

| 参数 | 含义 |
|---|---|
| `docker run` | 根据指定镜像创建并启动一个新容器 |
| `--rm` | 退出后删除临时容器，不删除镜像和挂载目录中的文件 |
| `-it` | 分配交互式终端 |
| `--user "$(id -u):$(id -g)"` | 使用当前PC用户身份运行，避免生成属于root的文件 |
| `-e HOME=/tmp` | 将容器内用户主目录设为 `/tmp` |
| `-v "$PWD:/workspace"` | 将PC当前目录及全部子目录挂载到容器的 `/workspace` |
| `-w /workspace` | 容器启动后进入 `/workspace` |
| `rdk-yolo-export:py310` | 本地镜像名称和标签 |
| `bash` | 启动Bash终端 |

`$PWD` 是执行命令时PC所在的目录。因为命令在 `rdk_model_zoo` 根目录执行，所以整个项目会显示在容器的 `/workspace` 下。容器在 `/workspace` 内生成的文件会直接保存在PC项目中；这是一种目录挂载，不是文件复制。

### 3.3 在容器内执行转换

```bash
python3 samples/vision/ultralytics_yolo/conversion/export_monkey_patch.py \
  --pt samples/vision/ultralytics_yolo/model/source/yolo11m.pt
```

执行结束后输入 `exit` 退出容器。

## 4. 转换结果

生成文件：

```text
samples/vision/ultralytics_yolo/model/source/yolo11m.onnx
```

`export_monkey_patch.py` 是D-Robotics官方脚本。它调用Ultralytics导出，并把YOLO11检测头改为适合BPU部署的6输出结构。

> git仓库中yolo11m_s600_benchmark_release/model/下提供已转好的yolov11m.onnx