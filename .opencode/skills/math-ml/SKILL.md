---
name: math-ml
description: Machine Learning engineering: PyTorch (distributed, FSDP, torch.compile), JAX (JIT, vmap, pmap, XLA), training optimization, model architecture design, evaluation methodology
license: MIT
compatibility: opencode
metadata:
  audience: ai-engineers
  domain: math-hpc
  paradigm: statistical-learning
  maturity: god-tier
  lines: ~1150
  integrates_with: [math-hpc, ai-rag, ai-agent-loop, ai-memory, backend-python, infra-kubernetes, infra-observability]
---

# Math-ML: ML Engineering — God-Tier Skill

Comprehensive ML engineering reference: designing, training, evaluating, and deploying production models.

---

## Ringkasan (Bahasa Indonesia)

- Panduan rekayasa ML lengkap: pipeline data → model → deployment.
- Rekomendasi cepat: AdamW + cosine-warmup, mixed-precision (BF16) bila support GPU, DataLoader dengan pin_memory + persistent_workers.
- Perhatian operasional: reproducibility (seed), safe data splits (no leakage), envelope encryption untuk model artifacts.

---

## 1. ML Engineering Fundamentals

### Full Pipeline

```
 PROBLEM DEF → DATA COLLECT → DATA PREP → MODEL DESIGN → TRAINING → EVAL → DEPLOY → MONITOR
    │              │             │            │             │         │       │        │
    │• Business    │• SQL/API    │• Clean     │• Arch       │• Loss   │• Val  │• Serve│• Drift
    │  goal        │• Crawl      │• Split     │• Param budg │• Opt    │  met  │  model│• Retrain
    │• Success met │• Stream     │• Normal    │• Base model │• Sched  │• Test │• Opt  │• Alert
    │• Framing     │• Label      │• Augment   │• Init       │• Reg    │  set  │  model│
    └──────────────┴─────────────┴────────────┴─────────────┴─────────┴───────┴───────┴────────┘
                                                        ↑ feedback loop ────────────────────────┘
```

### Key Concepts

| Concept | Definition | Mitigation |
|---------|-----------|------------|
| **Bias** | Error from wrong assumptions (underfitting) | Increase capacity, reduce regularization |
| **Variance** | Error from sensitivity to training data | Add reg, more data, ensemble |
| **Underfitting** | Model too simple | Increase depth/width, train longer |
| **Overfitting** | Model memorizes noise | Early stopping, dropout, weight decay, aug |
| **Covariate shift** | P(X) changes | Domain adaptation, importance weighting |
| **Concept drift** | P(Y\|X) changes | Online learning, periodic retraining |

### Cross-Validation Strategies

```python
from sklearn.model_selection import KFold, StratifiedKFold, TimeSeriesSplit

 kf = KFold(n_splits=5, shuffle=True, random_state=42)               # general
 skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)    # classification
 tscv = TimeSeriesSplit(n_splits=5, test_size=1000)                  # time-series

 # Train/val/test guidance:
 # - Typical: 70/15/15 or 80/10/10 depending on data size and task.
 # - For very large datasets (>100k), you may reduce val/test fractions (e.g., 95/2.5/2.5),
 #   but ensure absolute counts remain adequate (e.g., min 1k samples per split) and use stratification.
 # - Time-series: use TimeSeriesSplit or rolling windows (avoid future→past leakage).
```

---

## 2. PyTorch Mastery

### Tensor Operations

```python
# Tensor creation examples (separate values, not tuple)
x = torch.randn(32, 64, 128)           # (batch, seq, dim)
zeros = torch.zeros(32, 64)            # 2D zeros
I = torch.eye(64)                      # identity matrix 64x64
r = torch.arange(10)                   # vector [0..9]

# Indexing & broadcasting
slice = x[:, 0:10, :]                   # take first 10 tokens -> (32,10,128)
res = torch.einsum("bij,bjk->bik", A, B)   # batched matmul
attn = torch.einsum("bqhd,bkhd->bqkh", Q, K)  # attention scores

# Broadcasting example: (32,1,128) * (1,64,128) -> (32,64,128)
```

### Autograd

```python
w = torch.randn(64, 10, requires_grad=True)
y = x @ w + b                                      # forward
loss = y.mean(); loss.backward()                   # backward
grads = torch.autograd.grad(loss, [w, b])          # manual grad

z = x.detach()                                     # detach from graph
with torch.no_grad(): y = x @ w + b                # no graph

def grad_hook(grad):                               # backward hook
    return grad * 0.1                              # scale gradient
w.register_hook(grad_hook)
```

### nn.Module

```python
class TransformerBlock(nn.Module):
    """Pre-norm transformer block."""
    def __init__(self, d_model=512, n_heads=8, d_ff=2048, dropout=0.1):
        super().__init__()
        self.attn = nn.MultiheadAttention(d_model, n_heads, dropout, batch_first=True)
        self.ff = nn.Sequential(nn.Linear(d_model, d_ff), nn.GELU(),
                                nn.Dropout(dropout), nn.Linear(d_ff, d_model), nn.Dropout(dropout))
        self.norm1, self.norm2 = nn.LayerNorm(d_model), nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x, mask=None):
        x = x + self.dropout(self.attn(self.norm1(x), self.norm1(x), self.norm1(x), attn_mask=mask)[0])
        x = x + self.ff(self.norm2(x))
        return x

# Parameter management
for name, p in model.named_parameters():
    print(f"{name}: {p.shape}, grad={p.requires_grad}")
total = sum(p.numel() for p in model.parameters())
trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
```

### torch.nn.functional

```python
F.relu(x), F.gelu(x), F.silu(x)                          # activations
F.softmax(x, dim=-1), F.log_softmax(x, dim=-1)           # normalized
F.cross_entropy(logits, targets)                          # classification loss
F.binary_cross_entropy_with_logits(logits, targets)       # binary
F.mse_loss(pred, target), F.l1_loss(pred, target)         # regression
F.smooth_l1_loss(pred, target)                            # Huber
F.kl_div(log_probs, target_probs)                         # KL divergence
F.conv2d(x, w, stride=2, padding=1)                       # convolution
F.layer_norm(x, x.shape[-1:])                             # layer norm
F.group_norm(x, num_groups=32)                            # group norm
F.adaptive_avg_pool2d(x, (1,1))                           # global avg pool
```

### Optimizers & Schedulers

```python
opt = optim.AdamW(model.parameters(), lr=3e-4, weight_decay=0.01)    # default
opt = optim.SGD(model.parameters(), lr=0.1, momentum=0.9, nesterov=True)

sched = optim.lr_scheduler.CosineAnnealingLR(opt, T_max=100, eta_min=1e-6)
sched = optim.lr_scheduler.OneCycleLR(opt, max_lr=3e-4, steps_per_epoch=len(loader), epochs=100)
sched = optim.lr_scheduler.ReduceLROnPlateau(opt, mode="min", factor=0.5, patience=5)

# Warmup + cosine
def warmup_cosine(step, warmup=1000, total=10000):
    # Return multiplicative LR factor (float). Avoid returning torch.Tensor.
    if step < warmup:
        return float(step) / float(warmup)
    import math
    p = float(step - warmup) / float(max(1, total - warmup))
    return 0.5 * (1.0 + math.cos(p * math.pi))

# Example usage: sched = optim.lr_scheduler.LambdaLR(opt, warmup_cosine)
```

### DataLoader

```python
from torch.utils.data import Dataset, DataLoader

class ImageDataset(Dataset):
    def __init__(self, paths, labels, transform=None):
        self.paths, self.labels, self.transform = paths, labels, transform
    def __len__(self):
        return len(self.paths)
    def __getitem__(self, idx):
        # Use image loaders suitable for image files (PIL/torchvision), not torch.load
        from PIL import Image
        import torchvision.transforms.functional as TF
        import numpy as np

        path = self.paths[idx]
        img = Image.open(path).convert("RGB")
        img = TF.to_tensor(img)
        label = self.labels[idx]
        if self.transform:
            # albumentations expects numpy arrays in HWC order.
            # Gunakan .detach().cpu().numpy() untuk menghindari CUDA tensor -> numpy error.
            # Jika image berasal dari TF.to_tensor (CHW, float), ubah dtype sesuai augmentasi:
            # - untuk pixel augmentasi (CoarseDropout, ColorJitter) gunakan uint8 HWC
            # - untuk normalized pipeline gunakan float32 HWC
            np_img = img.detach().cpu().numpy().transpose(1, 2, 0)
            # contoh: jika img in [0,1] float -> albumentations expecting float -> keep float32
            # jika albumentations pipeline expects uint8 pixels, cast: np_img = (np_img*255).astype(np.uint8)
            data = self.transform(image=np_img)
            out_img = data["image"]
            # convert back to CHW float tensor in [0,1]
            if out_img.dtype == np.uint8:
                img = torch.from_numpy(out_img).permute(2, 0, 1).float().div(255.0)
            else:
                img = torch.from_numpy(out_img).permute(2, 0, 1).float()
        return img, label

def collate_fn(batch):                                           # variable-length
    inputs, targets = zip(*batch)
    padded = nn.utils.rnn.pad_sequence(inputs, batch_first=True)
    return padded, torch.tensor(targets)

loader = DataLoader(dataset, batch_size=64, shuffle=True, num_workers=8,
    pin_memory=True, prefetch_factor=2, persistent_workers=True, collate_fn=collate_fn)

# Weighted sampler for class imbalance
from torch.utils.data import WeightedRandomSampler
from collections import Counter

# labels: iterable of integer class ids for each sample (len(labels) == len(dataset))
label_counts = Counter([int(l) for l in labels])
# weight per sample = inverse frequency of its class
# Buat daftar floats per-sample (inverse frequency), lalu pastikan sampler menerima weights di CPU
weights = [1.0 / float(label_counts[int(l)]) for l in labels]
# Option A: pass Python list (accepted)
sampler = WeightedRandomSampler(weights=weights, num_samples=len(dataset), replacement=True)
# Option B: explicit DoubleTensor on CPU
# weights_tensor = torch.DoubleTensor(weights).to('cpu')
# sampler = WeightedRandomSampler(weights=weights_tensor, num_samples=len(dataset), replacement=True)
```

### torch.compile

```python
model = torch.compile(model, backend="inductor", mode="reduce-overhead")
# backends: inductor (def), cudagraphs, triton, eager
# modes: default, reduce-overhead, max-autotune, max-autotune-no-cudagraphs

# Prefer explicit compile invocation (PyTorch >= 2.0). Avoid decorator shorthand
# which may be less clear across versions. Example:
# model = torch.compile(model, backend="inductor", mode="reduce-overhead", dynamic=True)
# Note: torch._dynamo.config.verbose can be used for debugging but API may change between releases.
model = torch.compile(model, backend="inductor", mode="reduce-overhead", dynamic=True)
```

### Distributed: DDP / FSDP

```python
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.distributed.fsdp import FullyShardedDataParallel as FSDP

# DDP
dist.init_process_group("nccl", rank=rank, world_size=world_size)
# safer device placement example (guarded):
# device = torch.device(f"cuda:{rank}") if torch.cuda.is_available() else torch.device("cpu")
# model = DDP(MyModel().to(device), device_ids=[rank], bucket_cap_mb=25)
# Launch: torchrun --nproc_per_node=4 train.py

# FSDP
model = FSDP(MyModel(),
    sharding_strategy=FSDP.ShardingStrategy.SHARD_GRAD_OP,   # ZeRO-2
    auto_wrap_policy=transformer_auto_wrap_policy(TransformerBlock),
    mixed_precision=FSDP.MixedPrecision(param_dtype=torch.bfloat16,
        reduce_dtype=torch.bfloat16, buffer_dtype=torch.bfloat16))

# Strategies: NO_SHARD (DDP), SHARD_GRAD_OP (ZeRO-2), FULL_SHARD (ZeRO-3), HYBRID_SHARD
```

### CUDA Features

```python
with torch.cuda.amp.autocast(dtype=torch.bfloat16):    # AMP: BF16 preferred
    loss = model(x)                                     # forward in mixed precision

torch.cuda.empty_cache()                               # clear cached allocator
torch.cuda.set_per_process_memory_fraction(0.9)        # limit VRAM usage

# CUDA Graphs — static replay for fixed shapes
graph = torch.cuda.CUDAGraph()
with torch.cuda.graph(graph): static_out = model(static_in)
# Replay: fill static_in, then graph.replay()
```

---

## 3. JAX Deep Dive

### Core Transformations

```python
import jax, jax.numpy as jnp
from jax import grad, jit, vmap, pmap, value_and_grad, lax

@jit                                                          # JIT compilation
def forward(params, x): return jnp.dot(x, params["w"]) + params["b"]

single_fn = lambda p, x: jnp.dot(p["w"], x)                  # single example
batched_fn = vmap(single_fn, in_axes=(None, 0))              # auto-vectorize

grad_fn = grad(lambda p, x, y: jnp.mean((forward(p,x)-y)**2)) # gradient
loss, grads = value_and_grad(loss_fn)(params, x, y)           # both

lax.scan(lambda c, x: (c+x, None), 0.0, jnp.arange(10))      # scan loop
jax.jacfwd(jax.jacrev(loss_fn))                               # Hessian
```

### PRNG — Explicit Key Management

```python
key = jax.random.PRNGKey(42)
key, subkey = jax.random.split(key)                           # split for independent streams
mask = jax.random.bernoulli(subkey, p=0.5, shape=(32, 64))

class RNG:
    def __init__(self, seed): self._key = jax.random.PRNGKey(seed)
    def split(self): self._key, k = jax.random.split(self._key); return k
```

### Flax + Optax

```python
import flax.linen as nn
import optax

class MLP(nn.Module):
    hidden, out_dim = 256, 10
    @nn.compact
    def __call__(self, x):
        x = nn.Dense(self.hidden)(x); x = nn.relu(x); return nn.Dense(self.out_dim)(x)

model = MLP()
params = model.init(jax.random.PRNGKey(42), jnp.ones((1, 128)))

# Optax optimizer
optimizer = optax.chain(optax.clip_by_global_norm(1.0), optax.adamw(3e-4, weight_decay=0.01))
opt_state = optimizer.init(params)

@jit
def train_step(params, opt_state, batch):
    loss, grads = value_and_grad(lambda p: jnp.mean((model.apply(p,batch["x"])-batch["y"])**2))(params)
    updates, opt_state = optimizer.update(grads, opt_state, params)
    return optax.apply_updates(params, updates), opt_state, loss
```

### Parallel Training

```python
@pmap                                                          # data parallelism
def train_step(params, opt_state, batch):
    loss, grads = value_and_grad(loss_fn)(params, batch)
    grads = lax.pmean(grads, axis_name="devices")              # all-reduce mean
    updates, opt_state = optimizer.update(grads, opt_state, params)
    return optax.apply_updates(params, updates), opt_state, loss

# AOT compilation for inference
cached = forward.lower(params, x).compile()                    # compile once
pred = cached(params, x)                                       # fast inference

@jit(donate_argnums=(0,))                                      # in-place buffer reuse
def train_step(params, batch): ...
```

---

## 4. Neural Network Architectures

### Architecture Decision Tree

```
 INPUT TYPE → RECOMMENDED ARCHITECTURE
 ├── Structured/tabular  → MLP (2-4 layers, GELU, LayerNorm, Dropout)
 ├── Images (small data) → ResNet-18/34 or ConvNeXt-T
 ├── Images (large data) → ViT-B/L, EfficientNetV2, or Swin
 ├── Short sequences     → LSTM/GRU + attention
 ├── Long sequences      → Transformer (RoPE, FlashAttention)
 ├── Very long (>8K)     → Mamba-2, S4, or Longformer
 ├── Graphs              → GCN, GAT, or GraphSAGE
 ├── Point cloud         → PointNet++ or DGCNN
 ├── Video               → I3D (3D CNN) or TimeSformer
 └── Multimodal          → CLIP dual encoder or multimodal transformer
```

### MLP

```python
class MLP(nn.Module):
    """Flexible MLP: depth=2-6, width=256-4096 (power of 2)."""
    def __init__(self, in_dim, hidden_dims, out_dim, dropout=0.1, act=nn.GELU):
        super().__init__()
        layers = []
        for h in hidden_dims:
            layers += [nn.Linear(in_dim, h), nn.LayerNorm(h), act(), nn.Dropout(dropout)]
            in_dim = h
        layers.append(nn.Linear(in_dim, out_dim))
        self.net = nn.Sequential(*layers)
    def forward(self, x): return self.net(x)
```

### CNN

```python
class ConvBlock(nn.Module):
    """Conv → BN → Act → Conv → BN → Act."""
    def __init__(self, c_in, c_out, kernel=3, stride=1, groups=1):
        super().__init__()
        self.conv1 = nn.Conv2d(c_in, c_out, kernel, stride, padding=kernel//2, groups=groups, bias=False)
        self.bn1, self.bn2 = nn.BatchNorm2d(c_out), nn.BatchNorm2d(c_out)
        self.conv2 = nn.Conv2d(c_out, c_out, kernel, padding=kernel//2, groups=groups, bias=False)
        self.act = nn.SiLU()
    def forward(self, x): return self.act(self.bn2(self.conv2(self.act(self.bn1(self.conv1(x))))))

# Depthwise separable conv: depthwise(3×3, groups=c_in) → pointwise(1×1)
# Backbone patterns: ResNet (skip), EfficientNet (MBConv+SE), ConvNeXt (7×7 DW→LN→1×1→GELU→1×1)
```

### Transformer

```python
class MultiHeadAttention(nn.Module):
    """Scaled dot-product attention with multi-head (stable, clear reshapes).

    Correct shape flow:
      q,k,v: (B, T, D) -> view -> (B, n_heads, T, head_dim)
      attn: (B, n_heads, T, T)
      out: (B, T, D)
    """
    def __init__(self, d_model, n_heads, dropout=0.1):
        super().__init__()
        assert d_model % n_heads == 0, "d_model must be divisible by n_heads"
        self.n_heads = n_heads
        self.head_dim = d_model // n_heads
        self.scale = self.head_dim ** -0.5
        self.qkv = nn.Linear(d_model, d_model * 3, bias=False)
        self.out = nn.Linear(d_model, d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x, mask=None):
        B, T, D = x.shape
        device = x.device
        # compute q,k,v and split heads
        qkv = self.qkv(x)  # (B, T, 3*D)
        q, k, v = qkv.chunk(3, dim=-1)  # each (B, T, D)

        # --- Explicit reshape/permute steps ---
        # (B, T, D) -> (B, T, n_heads, head_dim)
        # -> permute to (B, n_heads, T, head_dim)
        q = q.view(B, T, self.n_heads, self.head_dim).permute(0, 2, 1, 3)
        k = k.view(B, T, self.n_heads, self.head_dim).permute(0, 2, 1, 3)
        v = v.view(B, T, self.n_heads, self.head_dim).permute(0, 2, 1, 3)

        # attention scores: (B, n_heads, T, T)
        attn_scores = (q @ k.transpose(-2, -1)) * self.scale

        # --- Mask handling (robust + clear) ---
        # Accept mask as torch.BoolTensor in one of these shapes:
        #   (B, T)       -> key padding mask (per batch, per token)
        #   (B, 1, T)    -> explicit batch x 1 x T
        #   (B, T, T)    -> full attention mask (per-example pairwise)
        # We convert to bool on the same device and expand to (B, n_heads, T, T)
        if mask is not None:
            # ensure bool on correct device
            mask = mask.to(device=device, dtype=torch.bool)
            if mask.dim() == 2:
                # (B, T) -> (B, 1, 1, T) -> expand to (B, n_heads, T, T)
                mask = mask.unsqueeze(1).unsqueeze(2)
                mask = mask.expand(-1, self.n_heads, T, -1)
            elif mask.dim() == 3:
                # could be (B, 1, T) or (B, T, T)
                if mask.shape[1] == 1 and mask.shape[2] == T:
                    # (B,1,T) -> (B,1,1,T) -> expand
                    mask = mask.unsqueeze(2).expand(-1, self.n_heads, T, -1)
                elif mask.shape[1] == T and mask.shape[2] == T:
                    # (B,T,T) -> (B,1,T,T) -> expand heads
                    mask = mask.unsqueeze(1).expand(-1, self.n_heads, -1, -1)
                else:
                    # fallback: try to broadcast
                    mask = mask.unsqueeze(1).expand(-1, self.n_heads, T, T)
            elif mask.dim() == 4:
                # already (B, 1 or n_heads, T, T) -- ensure heads dim matches
                if mask.shape[1] == 1:
                    mask = mask.expand(-1, self.n_heads, -1, -1)
                # else assume mask.shape[1] == n_heads

            # masked_fill expects the mask to be True for *keep*, so we invert
            # Use float('-inf') for numeric stability before softmax
            attn_scores = attn_scores.masked_fill(~mask, float("-inf"))

        # softmax over last dim (keys), stable because we applied -inf to masked positions
        attn = F.softmax(attn_scores, dim=-1)
        attn = self.dropout(attn)

        out = (attn @ v)  # (B, n_heads, T, head_dim)
        out = out.permute(0, 2, 1, 3).contiguous().view(B, T, D)  # (B, T, D)
        return self.out(out)
```

### GNN & Diffusion

```python
class GCNLayer(nn.Module):
    """Graph convolution: linear → neighbor aggregation."""
    def __init__(self, in_dim, out_dim): super().__init__(); self.linear = nn.Linear(in_dim, out_dim)
    def forward(self, x, adj): return adj @ self.linear(x)

# Diffusion: forward q(x_t|x_0) = N(√ᾱ x_0, (1-ᾱ)I), reverse p_θ(x_{t-1}|x_t) = N(μ_θ(x_t,t), σ²I)
# Training: predict noise ε_θ(x_t, t) with MSE loss
# Sampling: DDPM (T=1000 steps) or DDIM (skip steps for speed)
```

---

## 5. Training Optimization

### Optimizer Comparison

| Optimizer | Speed | Memory | Best For |
|-----------|-------|--------|----------|
| SGD+momentum | Slow, stable | Low | CV baselines, large batch |
| Adam | Fast | Medium | NLP, RL, GANs |
| **AdamW** | **Fast+stable** | **Medium** | **Default for transformers** |
| Lion | Fast | Low | Large models (2× mem efficient) |
| Sophia | Very fast | High | LLM pretraining |
| RAdam | Fast | Medium | Corrects Adam variance |

```python
opt = optim.AdamW(model.parameters(), lr=3e-4, weight_decay=0.01, betas=(0.9, 0.95))
opt = optim.SGD(model.parameters(), lr=0.1, momentum=0.9, nesterov=True, weight_decay=1e-4)
```

### LR Schedules & Regularization

```python
# Cosine decay + warmup — most reliable for transformers
def warmup_cosine_lr(step, warmup=1000, total=10000, max_lr=3e-4):
    # Return multiplicative factor (float) if used with LambdaLR, or absolute LR (float) if desired.
    # Ensure returned value is a Python float for compatibility with LambdaLR / PyTorch schedulers.
    if step < warmup:
        return float(step) / float(warmup)
    import math
    p = float(step - warmup) / float(max(1, total - warmup))
    return float(0.5 * (1.0 + math.cos(p * math.pi)))

# Example: using with LambdaLR (returns multiplicative factor)
# lr_lambda = lambda step: float(warmup_cosine_lr(step, warmup=1000, total=10000))
# sched = optim.lr_scheduler.LambdaLR(opt, lr_lambda)

# OneCycle — aggressive: warmup 10% → cos anneal
sched = optim.lr_scheduler.OneCycleLR(opt, max_lr=3e-4, total_steps=10000, pct_start=0.1)

# Normalization: BatchNorm (CNNs, batch≥16), LayerNorm (transformers, any batch),
#                GroupNorm (small batch, 32 groups), InstanceNorm (style transfer)

# Dropout: standard nn.Dropout(0.1), spatial nn.Dropout2d(0.2) for CNNs
# MC Dropout: keep train mode at inference, stack N predictions → uncertainty

# Gradient clipping
torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
torch.nn.utils.clip_grad_value_(model.parameters(), clip_value=0.5)

# Label smoothing
def smooth(targets, C, s=0.1):
    # targets: (B,) integer labels
    return (1 - s) * F.one_hot(targets, C).float() + float(s) / float(C)

# Model EMA
class EMA:
    def __init__(self, model, decay=0.999):
        # store detached clones on CPU to avoid GPU statefulness
        self.ema = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        self.d = float(decay)
    def update(self, m):
        for k, v in m.state_dict().items():
            self.ema[k] = self.d * self.ema[k] + (1.0 - self.d) * v.detach().cpu()
    def apply(self, m):
        # load EMA params (cast to model device)
        sd = {k: v.to(next(m.parameters()).device) for k, v in self.ema.items()}
        m.load_state_dict(sd)
```

### Mixed Precision

```python
scaler = torch.cuda.amp.GradScaler()                    # FP16 only
with torch.cuda.amp.autocast(dtype=torch.bfloat16):     # BF16 (preferred on Ampere+)
    loss = model(x)
scaler.scale(loss).backward(); scaler.step(opt); scaler.update()
```

---

## 6. Loss Functions & Metrics

### Decision Tree

```
 TASK → LOSS
 ├── Multi-class       → CrossEntropyLoss (hard) or LabelSmoothing (soft)
 ├── Multi-label       → BCEWithLogitsLoss
 ├── Imbalanced        → Focal Loss (γ=2, α=0.25) or Weighted CE
 ├── Regression        → MSELoss (normal), SmoothL1 (robust), Quantile (quantiles)
 ├── Segmentation      → DiceLoss + CrossEntropy, or Focal Tversky (imbalanced)
 ├── Object detection  → Focal Loss (cls) + SmoothL1/GIoU (box)
 ├── Metric learning   → ArcFace, CosFace, or Triplet Loss
 ├── Generative        → Diffusion MSE / VAE (recon+KL) / GAN BCE
 └── Ranking           → BPR (pairwise), ListNet (listwise)
```

### Loss Implementations

```python
class FocalLoss(nn.Module):
    """Stable multi-class focal loss implementation.
    Usage: logits (B,C), targets (B,) integer class labels.
    alpha can be scalar or tensor of shape (C,).
    """
    def __init__(self, gamma=2.0, alpha=0.25, reduction='mean'):
        super().__init__(); self.gamma, self.reduction = gamma, reduction
        if alpha is not None and not isinstance(alpha, (float, int, torch.Tensor)):
            raise ValueError("alpha must be float or torch.Tensor or None")
        self.alpha = torch.tensor(alpha) if isinstance(alpha, (float, int)) else alpha

    def forward(self, logits, targets):
        # logits: (B, C); targets: (B,)
        logpt = -F.cross_entropy(logits, targets, reduction='none')  # negative log-likelihood per sample
        pt = torch.exp(logpt)  # probabilities of true classes
        focal_term = (1 - pt) ** self.gamma
        loss = -focal_term * logpt  # because logpt is negative NLL

        if self.alpha is not None:
            if self.alpha.numel() == 1:
                loss = loss * float(self.alpha)
            else:
                # alpha per class
                at = self.alpha.to(logits.device)[targets]
                loss = loss * at

        if self.reduction == 'mean':
            return loss.mean()
        elif self.reduction == 'sum':
            return loss.sum()
        return loss

class TripletLoss(nn.Module):
    def __init__(self, margin=1.0): super().__init__(); self.margin = margin
    def forward(self, a, p, n): return F.relu(F.pairwise_distance(a,p) - F.pairwise_distance(a,n) + self.margin).mean()

def dice_loss(pred, target, smooth=1.0):
    inter = (pred.contiguous().view(-1) * target.contiguous().view(-1)).sum()
    return 1 - (2.*inter + smooth) / (pred.sum() + target.sum() + smooth)
```

### Metrics

```python
from sklearn.metrics import (accuracy_score, precision_recall_fscore_support,
    roc_auc_score, confusion_matrix, mean_squared_error, r2_score)

acc = accuracy_score(y_true, y_pred)
p, r, f1, _ = precision_recall_fscore_support(y_true, y_pred, average="weighted")
auc = roc_auc_score(y_true, y_probas)                        # binary
rmse = mean_squared_error(y_true, y_pred, squared=False)
r2 = r2_score(y_true, y_pred)

# Calibration — Expected Calibration Error
def ece(probas, labels, n_bins=10):
    bins = torch.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        in_bin = (probas >= lo) & (probas < hi)
        if in_bin.any():
            ece += abs(probas[in_bin].mean() - labels[in_bin].float().mean()) * in_bin.float().mean()
    return ece.item()
```

---

## 7. Data Pipeline & Augmentation

### Production DataLoader

```python
import albumentations as A
from functools import lru_cache

class ProdDataset(Dataset):
    def __init__(self, paths, labels, transform):
        self.paths, self.labels, self.transform = paths, labels, transform
        # per-instance LRU via dict; functools.lru_cache is not safe for bound methods
        from collections import OrderedDict
        self._cache = OrderedDict()
        self._cache_max = 1000

    def _load_file(self, path):
        # implement memmap-friendly loader for large tensors (numpy memmap or image libs)
        import numpy as np
        if path.endswith('.npy'):
            return np.load(path, mmap_mode='r')
        from PIL import Image
        img = Image.open(path).convert('RGB')
        return np.array(img)

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx):
        import numpy as np
        if idx in self._cache:
            img = self._cache[idx]
        else:
            arr = self._load_file(self.paths[idx])
            if len(self._cache) >= self._cache_max:
                self._cache.popitem(last=False)
            self._cache[idx] = arr
            img = arr
        label = self.labels[idx]
        if self.transform:
            out = self.transform(image=img)
            img = out['image']
        # ensure torch.Tensor
        if not isinstance(img, torch.Tensor):
            img = torch.from_numpy(img).permute(2,0,1).float()/255.0
        return img, label

train_aug = A.Compose([
    A.RandomResizedCrop(224, 224, scale=(0.08, 1.0)),
    A.HorizontalFlip(p=0.5),
    A.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.1),
    A.CoarseDropout(max_holes=8, max_height=32, max_width=32, p=0.3),
    A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

val_aug = A.Compose([
    A.Resize(256, 256),
    A.CenterCrop(224, 224),
    A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

# DataLoader: num_workers=4×GPU, pin_memory=True, prefetch_factor=2, persistent_workers=True
```

### Advanced Augmentation

```python
# MixUp
import numpy as np
def mixup(x, y, alpha=0.2):
    lam = float(np.random.beta(alpha, alpha))
    idx = torch.randperm(x.size(0))
    return lam * x + (1 - lam) * x[idx], lam * y + (1 - lam) * y[idx]

# RandAugment — automated (use torchvision transforms compose)
from torchvision.transforms import RandAugment
from torchvision import transforms as T
transform = T.Compose([RandAugment(num_ops=2, magnitude=9), T.ToTensor()])

# Class imbalance: weighted loss, WeightedRandomSampler, SMOTE, oversample minority
```

---

## 8. Model Evaluation & Validation

### Statistical Significance

```python
from scipy import stats
import numpy as np

def bootstrap_ci(y_true, y_pred, metric, n=1000, ci=0.95):
    scores = [metric(y_true[s], y_pred[s]) for s in [np.random.choice(len(y_true), len(y_true), replace=True) for _ in range(n)]]
    return np.percentile(scores, (1-ci)/2*100), np.percentile(scores, (1+ci)/2*100), np.mean(scores)

def mcnemar_test(y_true, a, b):
    n01 = np.sum((a==y_true)&(b!=y_true)); n10 = np.sum((a!=y_true)&(b==y_true))
    chi2 = (abs(n01-n10)-1)**2/(n01+n10); p = 1 - stats.chi2.cdf(chi2, 1)
    return {"chi2": chi2, "p_value": p, "n01": n01, "n10": n10}

# Paired t-test: t_stat, p = stats.ttest_rel(scores_a, scores_b)
# Permutation test: shuffle labels, compare metric difference distribution
```

### A/B Test for Models

```python
class MLABTest:
    def __init__(self, min_effect=0.01, alpha=0.05, power=0.8):
        self.min_effect, self.alpha, self.power = min_effect, alpha, power

    def required_n(self, mu, std):
        z_a, z_p = stats.norm.ppf(1-self.alpha/2), stats.norm.ppf(self.power)
        return int(2*(z_a+z_p)**2*std**2/(mu*self.min_effect)**2)

    def evaluate(self, control, variant):
        t, p = stats.ttest_ind(control, variant)
        return {"p": p, "effect": np.mean(variant)-np.mean(control), "significant": p<self.alpha}
```

---

## 9. Hyperparameter Optimization

### Optuna

```python
import optuna
from optuna.samplers import TPESampler

def objective(trial):
    lr = trial.suggest_float("lr", 1e-5, 1e-2, log=True)
    wd = trial.suggest_float("weight_decay", 1e-6, 1e-2, log=True)
    dropout = trial.suggest_float("dropout", 0.0, 0.5)
    hidden = trial.suggest_categorical("hidden_dim", [256, 512, 1024])
    opt_name = trial.suggest_categorical("optimizer", ["adamw", "sgd"])

    model = MLP(128, [hidden, hidden], 10, dropout=dropout)
    opt = optim.AdamW(model.parameters(), lr=lr, weight_decay=wd)
    return train_and_eval(model, opt)

study = optuna.create_study(direction="minimize", sampler=TPESampler(seed=42),
    pruner=optuna.pruners.MedianPruner(n_warmup_steps=5))
study.optimize(objective, n_trials=100)
```

### Key Ranges

| HP | MLP | CNN | Transformer |
|----|-----|-----|-------------|
| LR | 1e-4 – 1e-2 | 1e-4 – 1e-1 | 1e-5 – 3e-4 |
| Batch | 32 – 512 | 64 – 1024 | 16 – 512 |
| Weight decay | 1e-5 – 1e-2 | 1e-5 – 1e-3 | 0.01 – 0.1 |
| Dropout | 0.1 – 0.5 | 0.1 – 0.3 | 0.0 – 0.2 |
| Depth | 2 – 6 | 18 – 152 | 6 – 96 |
| Width/ch | 128 – 4096 | 64 – 2048 | 512 – 12288 |

---

## 10. Distributed Training

### Strategy Decision Tree

```
 MODEL SIZE → STRATEGY
 ├── <1B params, 1-8 GPUs → DDP (simplest)
 ├── <1B params, 8+ GPUs  → FSDP ZeRO-2 (shard grads+opt states)
 ├── 1B–10B                → FSDP ZeRO-3 + gradient checkpointing
 ├── 10B–100B              → FSDP + TP + PP + sequence parallelism
 └── 100B+                 → 4D parallelism + ZeRO-Infinity (offload CPU/NVMe)
```

### DDP Launch

```bash
# Single-node: torchrun --nproc_per_node=4 train.py
# Multi-node:
torchrun --nnodes=2 --node_rank=0 --nproc_per_node=8 \
  --master_addr=192.168.1.1 --master_port=29500 train.py

# NCCL tuning: NCCL_DEBUG=INFO NCCL_TIMEOUT=1800 NCCL_IB_DISABLE=0
```

### Memory Optimization

```python
# Gradient checkpointing — trade compute for memory
model.gradient_checkpointing_enable()                    # HF API

# Activation offloading (PyTorch 2.1+)
# ZeRO stages: 0(none) → 1(opt) → 2(grad+opt) → 3(param+grad+opt) → Infinity(offload)

# PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:128 (reduce fragmentation)
# PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True (2.1+)
```

### Attention Optimization

```python
# Flash Attention (PyTorch 2.0+ built-in SDPA)
with torch.backends.cuda.sdp_kernel(enable_flash=True, enable_math=False, enable_mem_efficient=False):
    out = F.scaled_dot_product_attention(q, k, v, attn_mask=mask)

# xformers: xops.memory_efficient_attention(q, k, v, attn_bias=LowerTriangularMask())
# Flash Attention v3: from flash_attn import flash_attn_func (Hopper WGMMA only)
```

---

## 11. Transfer Learning & PEFT

### PEFT Method Comparison

| Method | Trainable Params | Memory | vs Full FT | Use Case |
|--------|-----------------|--------|-----------|----------|
| Full FT | 100% | High | Baseline | Large data, enough compute |
| Linear probe | ~0.5% (head) | Very low | -5% to -15% | Small data, fast baseline |
| **LoRA (r=8)** | **~0.5–2%** | **Low** | **On par** | **Most common PEFT** |
| QLoRA | ~0.5–2% | Very low (4-bit) | -1% to -5% | Single GPU LLM FT |
| DoRA | ~0.5–2% | Low | Slightly better | LoRA + magnitude |
| Adapters | ~3–6% | Medium | On par | FFN bottlenecks |
| Prefix tuning | ~0.1% | Very low | -3% to -10% | Extreme memory constraint |

### LoRA Fine-Tuning

```python
from peft import LoraConfig, get_peft_model

lora_config = LoraConfig(r=16, lora_alpha=32, target_modules=["q_proj","v_proj"],
                          lora_dropout=0.1, bias="none", task_type="CAUSAL_LM")

base = AutoModelForCausalLM.from_pretrained("meta-llama/Llama-2-7b-hf", device_map="auto")
model = get_peft_model(base, lora_config)
model.print_trainable_parameters()                     # ~0.5%
# train normally → save model.save_pretrained("lora-llama-7b")
# merge: model.merge_and_unload() (fuse into base)
```

### Hugging Face

```python
from transformers import AutoModelForSequenceClassification, TrainingArguments, Trainer

model = AutoModelForSequenceClassification.from_pretrained("bert-base-uncased", num_labels=2)
args = TrainingArguments(output_dir="./r", per_device_train_batch_size=32, learning_rate=2e-5,
    num_train_epochs=3, fp16=True, evaluation_strategy="steps", report_to="wandb")
trainer = Trainer(model=model, args=args, train_dataset=ds, eval_dataset=val_ds)
trainer.train()
```

---

## 12. Model Deployment

### ONNX Export + FastAPI

```python
# Export
torch.onnx.export(model, dummy, "model.onnx", input_names=["input"],
    output_names=["output"], dynamic_axes={"input":{0:"batch"},"output":{0:"batch"}}, opset_version=17)

# Serve
import onnxruntime as ort
from fastapi import FastAPI
import numpy as np
app = FastAPI()
session = ort.InferenceSession("model.onnx", providers=["CUDAExecutionProvider"])

@app.post("/predict")
def predict(data: list[list[float]]):
    outputs = session.run(None, {"input": np.array(data, dtype=np.float32)})
    return {"predictions": np.argmax(outputs[0], axis=1).tolist()}
# uvicorn serve:app --host 0.0.0.0 --port 8000 --workers 4
```

### Optimization for Deployment

```python
# Static quantization (x86)
model.qconfig = torch.quantization.get_default_qconfig("fbgemm")
model = torch.quantization.convert(torch.quantization.prepare(model, inplace=True).eval(), inplace=True)

# QAT: prepare_qat → fine-tune → convert

# TorchScript
torch.jit.save(torch.jit.script(model), "model.pt")
torch.jit.save(torch.jit.trace(model, example), "model_traced.pt")

# TensorRT: ONNX → TRT engine, inference with trt runtime
```

### Dynamic Batcher

```python
import asyncio
class Batcher:
    def __init__(self, model, max_batch=32, max_latency=0.01):
        self.model, self.max_batch, self.queue = model, max_batch, asyncio.Queue()
        self.max_latency = max_latency

    async def predict(self, x):
        fut = asyncio.get_event_loop().create_future()
        await self.queue.put((x, fut))
        return await fut

    async def _run(self):
        while True:
            batch = [await self.queue.get()]
            while len(batch) < self.max_batch:
                try:
                    batch.append(await asyncio.wait_for(self.queue.get(), timeout=self.max_latency))
                except asyncio.TimeoutError:
                    break
            # Build batched tensor safely: handle padding if variable shapes
            inputs = [item[0] for item in batch]
            try:
                batched = torch.stack(inputs)
            except Exception:
                # fallback: pad to max shape along dim=1 (sequence) if applicable
                max_shape = [s for s in map(lambda t: t.shape, inputs)]
                # simple pad to max H/W for images or seq len for tokens
                # implement application-specific collate function for production
                batched = torch.nn.utils.rnn.pad_sequence([t if t.dim()>1 else t.unsqueeze(0) for t in inputs], batch_first=True)

            outputs = self.model(batched)
            # outputs expected to be tensor or list of outputs per example
            if isinstance(outputs, torch.Tensor):
                it = iter(outputs)
            else:
                it = iter(outputs)
            for (_, fut), out in zip(batch, it):
                try:
                    fut.set_result(out)
                except Exception as e:
                    fut.set_exception(e)
```

---

## 13. MLOps & Experiment Tracking

### MLflow

```python
import mlflow
mlflow.set_experiment("my-experiment")
with mlflow.start_run() as run:
    mlflow.log_params({"lr": 3e-4, "batch_size": 64, "optimizer": "adamw"})
    for epoch in range(100):
        mlflow.log_metrics({"train_loss": train_loss, "val_acc": val_acc}, step=epoch)
    mlflow.pytorch.log_model(model, "model")
    mlflow.log_artifact("config.yaml")
    mlflow.register_model(f"runs:/{run.info.run_id}/model", "Classifier")
```

### Monitoring

```python
# Data drift — Evidently AI
from evidently.report import Report
from evidently.metric_preset import DataDriftPreset
Report(metrics=[DataDriftPreset()]).run(reference=train_df, current=prod_df).save_html("drift.html")

# Concept drift — sliding window accuracy
def detect_drift(preds, targets, window=1000, threshold=0.05):
    for i in range(0, len(preds), 100):
        if accuracy_score(targets[i:i+window], preds[i:i+window]) < threshold:
            trigger_retraining()
```

---

## 14. Responsible AI & Safety

```python
# SHAP explanations
import shap
explainer = shap.Explainer(model, train_data)
shap_values = explainer(test_data[:100])
shap.summary_plot(shap_values, test_data[:100])
shap.plots.waterfall(shap_values[0])

# Fairness metrics
def fairness_metrics(y_true, y_pred, sensitive):
    groups = np.unique(sensitive)
    rates = {g: y_pred[sensitive==g].mean() for g in groups}
    di = rates[min(rates,key=rates.get)] / rates[max(rates,key=rates.get)]  # disparate impact
    return {"disparate_impact": di, "group_rates": rates}
```

---

## 15. GPU Performance Optimization

### Profiling

```python
from torch.profiler import profile, ProfilerActivity

with profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA],
             schedule=torch.profiler.schedule(wait=1, warmup=1, active=3),
             record_shapes=True, profile_memory=True) as prof:
    for step in range(5):
        train_step(model, batch); prof.step()
print(prof.key_averages().table(sort_by="cuda_time_total", row_limit=20))
prof.export_chrome_trace("trace.json")               # → chrome://tracing
```

### Performance Checklists

```
THROUGHPUT:
├── [ ] torch.compile with inductor backend
├── [ ] cudnn.benchmark = True
├── [ ] Flash Attention v2/v3 enabled
├── [ ] Tensor Cores: dims divisible by 8
├── [ ] DataLoader: num_workers=4×GPU, pin_memory
├── [ ] BF16 mixed precision (Ampere+)
├── [ ] Static KV cache for LLM inference

MEMORY:
├── [ ] Gradient checkpointing
├── [ ] FSDP ZeRO-2/3
├── [ ] Activation offloading to CPU
├── [ ] Mixed precision (halves activation memory)
├── [ ] Gradient accumulation (simulate large batch)
├── [ ] PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
├── [ ] Reduce batch size + increase accumulation steps
├── [ ] torch.cuda.empty_cache() between runs
└── [ ] Monitor fragmentation: memory_summary()
```

---

## 16. Anti-Patterns

| # | Anti-Pattern | Why It Fails | Fix |
|---|--------------|--------------|-----|
| 1 | Wrong norm mode at eval | BN uses wrong running stats | Switch model.eval() at inference |
| 2 | Not shuffling training data | Model learns batch order | DataLoader(shuffle=True) |
| 3 | Data leakage (preproc before split) | Validation "sees" training stats | Split FIRST, then fit encoders on train |
| 4 | ReLU dying | Dead neurons from large grads | Use LeakyReLU, GELU; reduce LR |
| 5 | BN with batch < 16 | Noisy running stats | Use GroupNorm or LayerNorm |
| 6 | BN placed after activation | Conv → Act → BN is wrong order | Conv → BN → Act |
| 7 | LR too large | Loss oscillates or diverges | Cosine warmup scheduler; LR range test |
| 8 | LR too small | Training stalls | Check gradient norms; increase LR |
| 9 | Overfitting to val set via early stopping | Val score no longer unbiased | Three-way split; retrain on train+val after stop |
| 10 | Not normalizing inputs | Features with different scales dominate | Z-score normalize per feature |
| 11 | Using test set for tuning | Test score not unbiased | Val set for tuning; test = ONE final eval |
| 12 | Not setting random seeds | Non-reproducible | Set torch/np/random seeds |
| 13 | Training on CPU accidentally | 10-100× slower | Check torch.cuda.is_available() |
| 14 | Grad accumulation without scale | Loss summed, not averaged | loss /= accumulation_steps |
| 15 | FP16 without loss scaling | Underflow to zero | Use GradScaler; BF16 doesn't need it |
| 16 | Too many DataLoader workers | OS thrashing | num_workers = 4×GPU (max 16-32) |

---

## 17. Troubleshooting

| Symptom | Likely Cause | Diagnosis | Fix |
|---------|-------------|-----------|-----|
| Loss NaN | Exploding gradients; log(0) | detect_anomaly(); check first batch | Clip grads; epsilon in log/div; reduce LR |
| Loss flat | LR too low; no gradient flow | Log gradient norms; check for zero grads | Increase LR; remove dead layers |
| Loss oscillating | LR too high | Reduce LR 10×; check per-step curve | LR scheduler; larger batch |
| Val loss diverges from train | Overfitting; pipeline mismatch | Compare train vs val loss curves | Add reg; verify augmentation match |
| OOM | Model too big; mem frag | memory_summary(); check model size | Reduce batch; checkpointing; FSDP; frag config |
| GPU util < 30% | DataLoader bottleneck | Nsight profile; check CPU util | Increase workers/prefetch; move augs to GPU |
| NCCL timeout | Network issue | NCCL_DEBUG=INFO; verify all ranks | Update NCCL; NCCL_TIMEOUT=1800 |
| All outputs 0 after quant | Bad calibration; unsupported op | Per-layer output vs float32 | Use representative calibration data |
| Dead ReLUs | Large grads kill ReLU | % dead units per layer | LeakyReLU/GELU; reduce LR |
| Inconsistent runs | Non-deterministic ops; unset seed | Compare run outputs | Set seeds; deterministic_algorithms=True |
| Training diverges mid-run | Bad batch; LR peak | Per-batch loss | Clip gradients; reduce max LR |

---

## 18. Quick Reference

### Activation Functions

| Activation | Range | Pro | Con | Best For |
|-----------|-------|-----|-----|----------|
| ReLU | [0, ∞) | Fast, sparse | Dead neurons | CNNs (default) |
| GELU | (-∞, ∞) | Smooth, best acc | Slower | Transformers (best) |
| SiLU/Swish | (-∞, ∞) | Self-gated | Slightly slower | Deep nets |
| LeakyReLU | (-∞, ∞) | No dead neurons | Inconsistent | GANs, RNNs |
| Tanh | (-1, 1) | Bounded | Vanishing grad | RNNs |
| Sigmoid | (0, 1) | Probabilistic | Vanishing grad | Binary output |

### Loss Function Quick Reference

| Task | Primary | Alternative | Notes |
|------|---------|-------------|-------|
| Multi-class | CrossEntropy | LabelSmoothing | Default |
| Multi-label | BCEWithLogits | Focal | Multiple labels/sample |
| Imbalanced | Focal | WeightedCE | Minority < 10% |
| Regression | MSE | SmoothL1, Huber | Huber robust to outliers |
| Segmentation | Dice + CE | Tversky | Overlap-based metric |
| Detection | Focal (cls) + SmoothL1 (box) | GIoU | RetinaNet-style |
| Metric learning | ArcFace | Triplet, CosFace | Face/embedding |

### Common Functions

```python
torch.randn, zeros, ones, eye, arange               # creation
torch.cat, stack, chunk, split                       # composition
torch.einsum, matmul, bmm                            # linear algebra
torch.argmax, topk, sort                             # reduction
torch.nn.utils.clip_grad_norm_                       # gradient mgmt
torch.cuda.amp.autocast, GradScaler                  # mixed precision
torch.jit.script, torch.jit.trace                    # compilation
torch.onnx.export                                    # ONNX export
torch.utils.data.DataLoader, Dataset                 # data pipeline
torch.distributed.init_process_group                 # distributed
torch.compile                                        # JIT (2.x)
```

### Hyperparameter Ranges

| Param | Small (<10M) | Medium (10M-1B) | Large (>1B) |
|-------|-------------|-----------------|-------------|
| LR (AdamW) | 1e-3 – 3e-3 | 3e-4 – 1e-3 | 1e-5 – 3e-4 |
| Batch size | 128 – 512 | 64 – 256 | 16 – 128 |
| Weight decay | 1e-4 – 1e-3 | 0.01 – 0.1 | 0.01 – 0.1 |
| Warmup | 0 – 5% | 5 – 10% | 10 – 20% |
| Dropout | 0.1 – 0.3 | 0.0 – 0.2 | 0.0 – 0.1 |

---

## 19. Implementation Checklist

- [ ] Problem defined: task type, metrics, constraints, baseline
- [ ] Train/val/test split BEFORE preprocessing
- [ ] Random seeds set (Python, NumPy, PyTorch, CUDA)
- [ ] Data pipeline: num_workers, pin_memory, prefetch_factor
- [ ] Preprocessing identical train↔inference
- [ ] Model architecture selected via decision tree
- [ ] Loss function matched to task
- [ ] Optimizer + scheduler: AdamW + cosine warmup recommended
- [ ] Gradient clipping: max_norm=1.0
- [ ] Mixed precision: BF16 on Ampere+
- [ ] Regularization: dropout, weight decay, label smoothing
- [ ] Gradient checkpointing for large models
- [ ] Early stopping configured on val metric
- [ ] Checkpointing: best (val) + latest (resume)
- [ ] Gradient accumulation for effective batch size
- [ ] Distributed strategy: DDP/FSDP/single-GPU
- [ ] Experiment tracking: MLflow/W&B/TensorBoard
- [ ] Ablation studies to validate choices
- [ ] Statistical significance tests for model comparison
- [ ] Model export: TorchScript, ONNX, state_dict
- [ ] Inference optimized: compile, quantize, batch
- [ ] Production monitoring: drift, latency, errors
- [ ] Model card: intended use, limitations, fairness
