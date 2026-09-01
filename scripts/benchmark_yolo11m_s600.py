#!/usr/bin/env python3
"""Run an instrumented S600 YOLO11m COCO benchmark.

The inference and COCO evaluation path intentionally matches eval_yolo_det.py.
This script only adds warm-up, per-stage timing, progress output, and a JSON
summary so that an official-style accuracy run is also reproducible.
"""

import argparse
from collections import Counter
import json
import os
import platform
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval


CURRENT_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = (CURRENT_DIR / "../runtime/python").resolve()
PROJECT_ROOT = (CURRENT_DIR / "../../../../").resolve()
sys.path.append(str(RUNTIME_DIR))
sys.path.append(str(PROJECT_ROOT))

from yolo_detect import YoloDetect, YoloDetectConfig  # noqa: E402


COCO_STAT_NAMES = [
    "AP_50_95",
    "AP_50",
    "AP_75",
    "AP_small",
    "AP_medium",
    "AP_large",
    "AR_1",
    "AR_10",
    "AR_100",
    "AR_small",
    "AR_medium",
    "AR_large",
]


def summarize_ms(samples):
    values = np.asarray(samples, dtype=np.float64) * 1000.0
    return {
        "count": int(values.size),
        "mean_ms": float(np.mean(values)),
        "p50_ms": float(np.percentile(values, 50)),
        "p95_ms": float(np.percentile(values, 95)),
        "p99_ms": float(np.percentile(values, 99)),
        "min_ms": float(np.min(values)),
        "max_ms": float(np.max(values)),
    }


def parse_args():
    parser = argparse.ArgumentParser(
        description="S600 YOLO11m COCO accuracy and stage-latency benchmark")
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--image-dir", required=True)
    parser.add_argument("--annotation", required=True)
    parser.add_argument("--result-json", default="results_det.json")
    parser.add_argument("--report-json", default="benchmark_report.json")
    parser.add_argument("--conf-thres", type=float, default=0.25)
    parser.add_argument("--nms-thres", type=float, default=0.7)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--progress-every", type=int, default=100)
    return parser.parse_args()


def main():
    args = parse_args()
    coco = COCO(args.annotation)
    image_ids = coco.getImgIds()
    if args.limit > 0:
        image_ids = image_ids[:args.limit]
    if not image_ids:
        raise RuntimeError("No COCO images selected")

    coco_cat_ids = [cat["id"] for cat in coco.dataset["categories"]]
    # Keep every benchmark aligned with the official YOLO Detect runtime.
    model = YoloDetect(YoloDetectConfig(
        model_path=args.model_path,
        resize_type=1,
    ))

    first_info = coco.loadImgs([image_ids[0]])[0]
    first_image = cv2.imread(os.path.join(args.image_dir, first_info["file_name"]))
    if first_image is None:
        raise RuntimeError(f"Failed to read warm-up image: {first_info['file_name']}")
    for _ in range(args.warmup):
        input_tensor = model.pre_process(first_image)
        outputs = model.forward(input_tensor)
        model.post_process(
            outputs, first_image.shape[1], first_image.shape[0],
            args.conf_thres, args.nms_thres)

    timings = {
        "image_decode": [],
        "preprocess": [],
        "runtime_forward": [],
        "postprocess": [],
        "e2e_pipeline": [],
    }
    results = []
    processed = 0
    loop_start = time.perf_counter()

    for index, image_id in enumerate(image_ids, start=1):
        info = coco.loadImgs([image_id])[0]
        path = os.path.join(args.image_dir, info["file_name"])

        e2e_start = time.perf_counter()
        stage_start = e2e_start
        image = cv2.imread(path)
        decode_end = time.perf_counter()
        if image is None:
            print(f"WARNING: failed to read {path}", file=sys.stderr)
            continue

        input_tensor = model.pre_process(image)
        preprocess_end = time.perf_counter()
        outputs = model.forward(input_tensor)
        forward_end = time.perf_counter()
        boxes, scores, cls_ids = model.post_process(
            outputs, image.shape[1], image.shape[0],
            args.conf_thres, args.nms_thres)
        postprocess_end = time.perf_counter()

        timings["image_decode"].append(decode_end - stage_start)
        timings["preprocess"].append(preprocess_end - decode_end)
        timings["runtime_forward"].append(forward_end - preprocess_end)
        timings["postprocess"].append(postprocess_end - forward_end)
        timings["e2e_pipeline"].append(postprocess_end - e2e_start)
        processed += 1

        for box, score, cls_id in zip(boxes, scores, cls_ids):
            x1, y1, x2, y2 = [float(value) for value in box]
            results.append({
                "image_id": image_id,
                "category_id": int(coco_cat_ids[int(cls_id)]),
                "bbox": [x1, y1, x2 - x1, y2 - y1],
                "score": float(score),
            })

        if args.progress_every > 0 and index % args.progress_every == 0:
            elapsed = time.perf_counter() - loop_start
            print(
                f"processed={index}/{len(image_ids)} "
                f"elapsed={elapsed:.1f}s rate={processed / elapsed:.2f} image/s",
                flush=True)

    loop_elapsed = time.perf_counter() - loop_start
    Path(args.result_json).parent.mkdir(parents=True, exist_ok=True)
    with open(args.result_json, "w", encoding="utf-8") as file:
        json.dump(results, file)

    coco_dt = coco.loadRes(args.result_json)
    coco_eval = COCOeval(coco, coco_dt, "bbox")
    coco_eval.evaluate()
    coco_eval.accumulate()
    coco_eval.summarize()
    coco_stats = {
        name: float(value)
        for name, value in zip(COCO_STAT_NAMES, coco_eval.stats)
    }
    detections_per_image = Counter(item["image_id"] for item in results)
    max_detections_per_image = max(detections_per_image.values(), default=0)

    report = {
        "model_path": os.path.abspath(args.model_path),
        "image_dir": os.path.abspath(args.image_dir),
        "annotation": os.path.abspath(args.annotation),
        "result_json": os.path.abspath(args.result_json),
        "thresholds": {
            "confidence": args.conf_thres,
            "nms_iou": args.nms_thres,
        },
        "warmup_iterations": args.warmup,
        "selected_images": len(image_ids),
        "processed_images": processed,
        "detections": len(results),
        "detections_per_image": {
            "mean_over_all_images": len(results) / processed,
            "max": max_detections_per_image,
            "images_over_100": sum(
                count > 100 for count in detections_per_image.values()),
        },
        "loop_elapsed_sec": loop_elapsed,
        "pipeline_throughput_fps": processed / loop_elapsed,
        "timing_scope": {
            "postprocess": (
                "CPU-only model.post_process call: confidence filtering, DFL "
                "box decoding, NMS, and coordinate scaling. Excludes image "
                "decode, preprocessing, BPU inference, and COCO evaluation."),
            "runtime_forward": (
                "Synchronous hbm_runtime.run call; includes runtime-visible "
                "submission, synchronization, and tensor handling. It does not "
                "split input copy, queue, BPU execution, and output copy."),
            "e2e_pipeline": (
                "cv2.imread through final decoded/NMS detections; excludes model "
                "construction, warm-up, JSON writing, and COCO evaluation."),
        },
        "stage_timings": {
            name: summarize_ms(samples) for name, samples in timings.items()
        },
        "coco_bbox": coco_stats,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "opencv": cv2.__version__,
            "cpu_affinity": sorted(os.sched_getaffinity(0)),
            "single_core_requested": len(os.sched_getaffinity(0)) == 1,
        },
    }
    Path(args.report_json).parent.mkdir(parents=True, exist_ok=True)
    with open(args.report_json, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
