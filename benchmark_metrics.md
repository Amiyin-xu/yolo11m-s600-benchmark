# S600 YOLO11m Benchmark 指标

## 纯 BPU 性能指标

| 并发线程数 | BPU Task 平均延迟 | BPU Task 最小延迟 | BPU Task 最大延迟 | System Throughput |
|---:|---:|---:|---:|---:|
| 1 | 2.573 ms | 2.549 ms | 2.857 ms | 385.858 FPS |
| 12 | 7.087 ms | 3.193 ms | 7.512 ms | 1635.376 FPS |

## Letterbox COCO Benchmark：精度与端到端阶段耗时

### 分阶段耗时

| 指标 | 均值 | P50 | P95 | P99 | 最小值 | 最大值 |
|---|---:|---:|---:|---:|---:|---:|
| Image Decode | 3.865 ms | 3.809 ms | 5.591 ms | 6.503 ms | 0.403 ms | 13.164 ms |
| Preprocess Latency | 1.448 ms | 1.038 ms | 3.316 ms | 4.415 ms | 0.926 ms | 4.597 ms |
| Runtime Forward | 4.442 ms | 4.389 ms | 4.642 ms | 4.740 ms | 4.320 ms | 16.040 ms |
| Postprocess Latency | 1.748 ms | 1.660 ms | 2.223 ms | 2.605 ms | 1.321 ms | 80.948 ms |
| E2E Latency | 11.503 ms | 11.387 ms | 13.403 ms | 15.145 ms | 8.119 ms | 90.372 ms |

### 端到端汇总指标

| 指标 | 数据 |
|---|---:|
| 处理图片数 | 5,000 |
| 检测结果数 | 30,521 |
| 完整循环耗时 | 57.699 s |
| 单流顺序端到端吞吐量 | 86.656 FPS |

### COCO bbox 精度指标

| 指标 | 数据 |
|---|---:|
| AP@[0.50:0.95] | 0.429883 |
| AP@0.50 | 0.552785 |
| AP@0.75 | 0.471316 |
| AP small | 0.217009 |
| AP medium | 0.491309 |
| AP large | 0.616695 |
| AR，maxDets=1 | 0.330571 |
| AR，maxDets=10 | 0.482919 |
| AR，maxDets=100 | 0.488777 |
| AR small | 0.233784 |
| AR medium | 0.552894 |
| AR large | 0.696506 |
