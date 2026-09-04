# YOLO11m S600 Benchmark复现资料

本仓库用于复现YOLO11m Detect在D-Robotics S600上的模型转换、INT8 PTQ和Benchmark流程。

固定测试条件：

- 模型：Ultralytics YOLO11m Detect，COCO 80类
- 输入尺寸：640×640
- 预处理：Letterbox、NV12
- 编译目标：S600 `nash-p`
- 量化方式：OpenExplorer 3.7.0，INT8 PTQ
- 校准集：固定50张COCO2017 val图片
- 精度集：COCO2017 val2017，共5000张图片

## 使用顺序

1. [PT转ONNX指南](pt_to_onnx.md)：准备Python 3.10环境，将`yolo11m.pt`导出为BPU友好的FP32 ONNX。
2. [ONNX转HBM指南](onnx_to_hbm.md)：使用D-Robotics OpenExplorer 3.7.0 CPU Docker完成INT8 PTQ并编译S600 HBM。
3. [S600 Benchmark指南](s600_benchmark.md)：在S600上测试COCO精度、CPU单核后处理延迟，以及BPU单线程和12线程性能。
4. [Benchmark实测指标](benchmark_metrics.md)：查看本次S600测试得到的全部指标。

整体流程：

```text
yolo11m.pt（FP32）
  → yolo11m.onnx（FP32、6输出）
  → 50张COCO图片进行INT8 PTQ
  → yolo11m_nashp_640x640_nv12.hbm
  → S600精度与性能Benchmark
```

## 仓库内容

```text
.
├── model/
│   ├── yolo11m.pt
│   └── yolo11m.onnx
├── datasets/coco2017/
│   ├── calibration_yolo11m_50/
│   ├── val2017/
│   └── annotations/instances_val2017.json
├── environment/
│   ├── requirements-pt2onnx.txt
│   └── rdk-yolo-export-py310.Dockerfile
├── scripts/benchmark_yolo11m_s600.py
├── pt_to_onnx.md
├── onnx_to_hbm.md
├── s600_benchmark.md
└── benchmark_metrics.md
```

HBM属于面向具体工具链版本和目标硬件的编译产物，本仓库不直接提供，请按照[ONNX转HBM指南](onnx_to_hbm.md)生成。

## 官方参考

- [D-Robotics rdk_model_zoo `rdk_s`分支](https://github.com/D-Robotics/rdk_model_zoo/tree/rdk_s)
- [D-Robotics OpenExplorer工具链说明](https://developer.d-robotics.cc/rdk_s_doc/en/Advanced_development/toolchain_development/algorithm_toolchain/overview)
- [D-Robotics Ultralytics YOLO评估说明](https://github.com/D-Robotics/rdk_model_zoo/blob/rdk_s/samples/vision/ultralytics_yolo/evaluator/README_cn.md#rdk-s600)
- [Ultralytics YOLO11模型](https://huggingface.co/Ultralytics/YOLO11)

转换和Benchmark应使用D-Robotics官方`rdk_s`代码。本仓库中的`benchmark_yolo11m_s600.py`是CPU单核后处理分段计时的补充脚本，其余命令来源和适用范围分别在各指南中说明。
