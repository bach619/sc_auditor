---
name: math-ml
description: Machine Learning engineering: PyTorch (distributed, FSDP, torch.compile), JAX (JIT, vmap, pmap, XLA), training optimization, model architecture design, evaluation methodology
license: MIT
compatibility: opencode
metadata:
  audience: ai-engineers
  domain: math-hpc
  paradigm: statistical-learning
  integrates_with: [math-hpc, ai-rag, ai-agent-loop, ai-memory, backend-python, infra-kubernetes]
---

## Math ML (Machine Learning) Skill

### PyTorch Advanced
- **torch.compile**: Just-in-time compilation; inductor backend; dynamic=False for static graphs; graph breaks to avoid
- **FSDP (Fully Sharded Data Parallel)**: Shard parameters, gradients, optimizer states across GPUs; mixed precision
- **DDP**: Data parallelism with gradient all-reduce; bucket_cap_mb for communication
- **Custom kernels**: torch.library for custom ops; Triton for GPU kernels; torch.fx for graph transforms
- **Checkpointing**: activation checkpointing for memory; distributed checkpoint (DC) for multi-GPU save/load
- **Mixed precision**: torch.cuda.amp (GradScaler deprecated in 2.4+); bfloat16 preferred over fp16

### JAX Advanced
- **JIT**: jax.jit for compilation; static_argnums for non-array args; donate_argnums for in-place updates
- **vmap**: Auto-vectorization; batching without for-loops; in_axes/out_axes for axis control
- **pmap**: Data parallelism; jax.lax.p* collective ops; pjit for sharding patterns
- **Autodiff**: grad, jacobian, hessian, vjp, jvp; stop_gradient for freezing; custom_vjp for custom gradients
- **Pallas/Triton**: Write custom GPU kernels for JAX; lower-level control
- **XLA**: Ahead-of-time compilation; AOT for deployment; stablehlo for interoperability

### Training Optimization
- **Learning rate scheduling**: Cosine decay with warmup (most reliable); OneCycleLR for quick convergence
- **Optimizers**: AdamW (default), Lion (memory efficient), Sophia (second-order), Adam-mini (new)
- **Gradient accumulation**: Simulate larger batch sizes; normalize loss or accumulate with divisor
- **Gradient clipping**: clip_grad_norm_ (default 1.0); prevents gradient explosion in RNNs/Transformers
- **Curriculum learning**: Start with easy examples, progressively harder

### Model Architecture
- **Transformers**: Pre-norm (GPT) vs post-norm (original); RoPE/ALiBi position; FlashAttention-3; GQA/MQA
- **CNNs**: ConvNeXt (modernized), EfficientNet (scaling), ResNet (baseline)
- **State Space Models**: Mamba-2 (selective SSM), S4/H3 (long-range)
- **Diffusion**: DDPM, DDIM, latent diffusion (Stable Diffusion); guidance scale; negative prompts

### Evaluation
- **Metrics**: Accuracy, F1, ROC-AUC for classification; BLEU/ROUGE/BERTScore for text; FID/CLIP score for images
- **Statistical significance**: Bootstrap confidence intervals; McNemar's test; paired t-test with corrections
- **Ablation studies**: Remove one component at a time; measure impact
- **Calibration**: Expected calibration error (ECE); temperature scaling; reliability diagrams

### Data Pipeline
- **DataLoader**: num_workers = 4*GPU_count; pin_memory=True; prefetch_factor=2
- **WebDataset**: Shard-based for cloud storage; tar file format; resampling strategies
- **Data augmentation**: RandAugment (automated), MixUp/CutMix (regularization), AutoAugment

### Common Anti-Patterns

| Anti-Pattern | Why It Fails | Fix |
|---|---|---|
| Data leakage between train/val/test | Preprocessing before split contaminates validation set | Split first; fit scalers/encoders only on training data |
| Not setting random seeds | Non-reproducible results make debugging impossible | Set `torch.manual_seed(42)`; set CUDA seed; use `torch.use_deterministic_algorithms(True)` |
| Overfitting to validation set | Hyperparameter tuning on val set → inflated val score → poor generalization | Use three-way split (train/val/test); never tune on test set |
| Ignoring gradient flow | Silent training failure where gradients vanish/explode | Monitor gradient norms with `torch.nn.utils.clip_grad_norm_`; log histogram of gradients |
| Batch size too large without gradient accumulation | Memory explosion; suboptimal convergence | Use gradient accumulation to simulate large batches; `loss = loss / accumulation_steps` |
| FP16/BF16 without loss scaling | Underflow in small gradients → zero updates | Use `torch.cuda.amp.GradScaler` (FP16) or native BF16 (no scaling needed) |
| Training without early stopping | Wastes compute; model overfits | Monitor validation loss; stop when no improvement for N epochs |
| Not profiling DataLoader | Data loading is the bottleneck, not GPU | Use `DataLoader(pin_memory=True, num_workers=4, prefetch_factor=2)` |
| Deploying training code to inference | Unnecessary autograd overhead; memory waste | Wrap inference in `with torch.no_grad()`; use `torch.jit.script` or `torch.compile` |

### Troubleshooting

| Symptom | Likely Cause | Diagnosis | Fix |
|---|---|---|---|
| Loss is NaN | Exploding gradients; log(0); division by zero | Check loss value after first few batches; `torch.autograd.detect_anomaly()` | Add gradient clipping; use `eps` in log/division; reduce learning rate |
| Loss not decreasing | Learning rate too high (oscillating) or too low (stuck) | Plot loss curve; check gradient norms | LR range test; use learning rate scheduler |
| Training works, eval fails | Overfitting; preprocessing inconsistency | Compare train vs val loss curve; check preprocessing pipeline between modes | Add dropout/batchnorm eval mode; verify preprocessing match |
| `CUDA out of memory` | Model too large; batch too big; memory leak | `torch.cuda.memory_summary()`; check gradient accumulation | Reduce batch size; enable gradient checkpointing; use FSDP/DDP |
| GPU utilization < 50% | DataLoader bottleneck; small model; excessive synchronization | `nvidia-smi dmon`; profile with Nsight; check CPU utilization | Increase `num_workers` and `prefetch_factor`; move augmentations to GPU |
| `DistBackendError` / NCCL timeout | Network issue; mismatched NCCL versions; deadlock in collective | Check NCCL_DEBUG=INFO logs; verify all ranks running same code | Update NCCL; set `NCCL_TIMEOUT=1800`; verify network topology |
| Model outputs all zeros after quantization | Incorrect calibration; unsupported op | Check quantized model outputs vs baseline; per-layer analysis | Use representative calibration dataset; skip unsupported ops |

### Implementation Checklist

- [ ] Random seeds set for reproducibility (Python, NumPy, PyTorch, CUDA)
- [ ] Train/validation/test split created before any preprocessing
- [ ] Data preprocessing pipeline identical between training and inference
- [ ] Learning rate schedule defined (cosine decay + warmup recommended)
- [ ] Gradient clipping enabled (default `max_norm=1.0`)
- [ ] Mixed-precision training configured (BF16 preferred on Ampere+)
- [ ] Early stopping configured based on validation metric
- [ ] Model checkpointing saves best and latest weights
- [ ] Gradient accumulation configured for effective batch size
- [ ] DataLoader optimized (`num_workers`, `pin_memory`, `prefetch_factor`)
- [ ] Distributed training strategy selected (DDP, FSDP, or single-GPU)
- [ ] Evaluation metrics aligned with business objective (not just accuracy)
- [ ] Ablation studies to validate architectural choices
- [ ] Experiment tracking configured (MLflow/W&B/TensorBoard)
- [ ] Model versioning and registry for deployment
- [ ] Inference optimization (torch.compile, quantization, pruning) evaluated
- [ ] Production monitoring: prediction latency, drift detection, error rates
