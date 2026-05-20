---
name: data-deep-learning
description: God-tier deep learning & data science: neural network architectures (CNN, RNN, Transformer, GAN, Diffusion), training optimization (SGD, Adam, LR scheduling, regularization), data pipeline design (ETL, feature engineering, augmentation), model evaluation (metrics, cross-validation, A/B testing), MLOps (experiment tracking, model registry, deployment), and production ML patterns
license: MIT
compatibility: opencode
metadata:
  audience: ml-engineers
  domain: machine-learning
  paradigm: data-driven
  capabilities:
    - neural-network-design
    - cnn-architectures
    - rnn-architectures
    - transformer-architectures
    - gan-design
    - diffusion-models
    - training-optimization
    - regularization-techniques
    - feature-engineering
    - data-augmentation
    - model-evaluation
    - cross-validation
    - hyperparameter-tuning
    - mlops-pipeline
    - experiment-tracking
    - model-deployment
    - transfer-learning
    - fine-tuning
    - prompt-engineering-llm
  prerequisites:
    - math-ml
  integrates_with:
    - math-ml
    - math-hpc
    - backend-python
---

## Deep Learning & Data Science — God-Tier

### Core Philosophy

> **Deep learning is not magic. It is applied mathematics + engineering + empirical science.**
> Every model is a hypothesis. Every training run is an experiment. Every metric is evidence.

```
┌─────────────────────────────────────────────────────────────┐
│              ML LIFECYCLE                                    │
│                                                              │
│  ┌─────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  │
│  │  DATA   │──▶│  MODEL   │──▶│ TRAINING │──▶│ EVALUATE │  │
│  │  PIPE   │   │  DESIGN  │   │  & OPT   │   │  & TUNE  │  │
│  └─────────┘   └──────────┘   └──────────┘   └──────────┘  │
│       ▲                                              │      │
│       │                                              ▼      │
│  ┌─────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  │
│  │MONITOR  │◀──│ DEPLOY   │◀──│  EXPORT  │◀──│  SELECT  │  │
│  │  & RETRAIN│  │  & SERVE │   │  & PACK  │   │  BEST    │  │
│  └─────────┘   └──────────┘   └──────────┘   └──────────┘  │
│                                                              │
│  Iterate: Every deployment generates data → retrain → improve│
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. Neural Network Architectures

### 1.1 Architecture Selection Guide

```
┌─────────────────────────────────────────────────────────┐
│              ARCHITECTURE DECISION TREE                  │
│                                                         │
│  What's your data type?                                 │
│                                                         │
│  ┌─ Tabular ──────────▶ MLP, XGBoost, LightGBM         │
│  │                                                         │
│  ├─ Image ────────────▶ CNN (ResNet, EfficientNet)      │
│  │                    ▶ Vision Transformer (ViT)         │
│  │                    ▶ ConvNeXt                          │
│  │                                                         │
│  ├─ Text ─────────────▶ Transformer (BERT, GPT)          │
│  │                    ▶ RNN/LSTM (legacy)                │
│  │                    ▶ CNN for text (TextCNN)           │
│  │                                                         │
│  ├─ Time Series ──────▶ LSTM, GRU                        │
│  │                    ▶ Temporal Convolution (TCN)       │
│  │                    ▶ Transformer (Informer, Autoformer)│
│  │                                                         │
│  ├─ Graph ────────────▶ GCN, GAT, GraphSAGE              │
│  │                                                         │
│  ├─ Audio ────────────▶ CNN (spectrogram)                │
│  │                    ▶ Wav2Vec, Whisper                  │
│  │                                                         │
│  └─ Multi-modal ──────▶ CLIP, Flamingo, LLaVA            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 1.2 CNN Architectures

| Architecture | Key Innovation | Parameters | Use Case |
|-------------|----------------|------------|----------|
| **LeNet-5** | First CNN | 60K | MNIST, simple classification |
| **AlexNet** | ReLU, Dropout, GPU | 60M | ImageNet breakthrough |
| **VGG** | 3x3 convolutions stacked | 138M | Feature extraction |
| **ResNet** | Skip connections | 11M-256M | General purpose, transfer learning |
| **Inception** | Multi-scale convolutions | 23M | Efficient feature extraction |
| **DenseNet** | Dense connections | 7M-33M | Parameter efficiency |
| **EfficientNet** | Compound scaling | 4M-480M | Best accuracy/efficiency |
| **ConvNeXt** | Modernized CNN | 28M-658M | CNN vs Transformer |
| **MobileNet** | Depthwise separable conv | 3M-13M | Mobile/edge deployment |

**CNN Design Patterns:**

```python
# Residual Block (ResNet)
class ResidualBlock(nn.Module):
    def __init__(self, in_channels, out_channels, stride=1):
        super().__init__()
        self.conv1 = nn.Conv2d(in_channels, out_channels, 3, stride, 1, bias=False)
        self.bn1 = nn.BatchNorm2d(out_channels)
        self.conv2 = nn.Conv2d(out_channels, out_channels, 3, 1, 1, bias=False)
        self.bn2 = nn.BatchNorm2d(out_channels)

        self.skip = nn.Sequential()
        if stride != 1 or in_channels != out_channels:
            self.skip = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, 1, stride, bias=False),
                nn.BatchNorm2d(out_channels)
            )

    def forward(self, x):
        identity = self.skip(x)
        out = F.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        return F.relu(out + identity)  # Skip connection
```

### 1.3 Transformer Architecture

```
┌─────────────────────────────────────────────────────────┐
│              TRANSFORMER BLOCK                           │
│                                                         │
│  Input ──▶ Multi-Head Self-Attention ──▶ Add & Norm     │
│                │                                        │
│                ▼                                        │
│          Feed-Forward Network ──▶ Add & Norm ──▶ Output │
│                                                         │
│  Self-Attention:                                        │
│  Attention(Q,K,V) = softmax(QK^T / √d_k) V             │
│                                                         │
│  Multi-Head:                                            │
│  MultiHead(Q,K,V) = Concat(head_1, ..., head_h) W^O    │
│  where head_i = Attention(QW_i^Q, KW_i^K, VW_i^V)      │
│                                                         │
│  Positional Encoding:                                   │
│  PE(pos, 2i) = sin(pos / 10000^(2i/d_model))           │
│  PE(pos, 2i+1) = cos(pos / 10000^(2i/d_model))         │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Transformer Variants:**

| Variant | Key Difference | Use Case |
|---------|---------------|----------|
| **BERT** | Encoder-only, bidirectional | Understanding, classification, NER |
| **GPT** | Decoder-only, autoregressive | Generation, completion |
| **T5** | Encoder-decoder, text-to-text | Translation, summarization |
| **ViT** | Image patches as tokens | Image classification |
| **Swin** | Shifted windows | Dense prediction (detection, segmentation) |
| **DETR** | Object queries | Object detection |

### 1.4 RNN/LSTM/GRU

| Architecture | Gates | Parameters | Strength |
|-------------|-------|------------|----------|
| **Vanilla RNN** | None | 2 × (h × (d + h)) | Simple, fast |
| **LSTM** | Input, Forget, Output | 4 × (h × (d + h)) | Long-term memory |
| **GRU** | Reset, Update | 3 × (h × (d + h)) | Faster than LSTM, similar performance |

### 1.5 GAN Architecture

```
┌─────────────────────────────────────────────────────────┐
│              GAN TRAINING LOOP                           │
│                                                         │
│  Generator: z (noise) ──▶ G(z) ──▶ Fake Sample          │
│                                                         │
│  Discriminator:                                         │
│    Real Sample ──▶ D(x) ──▶ P(real)                     │
│    Fake Sample ──▶ D(G(z)) ──▶ P(fake)                  │
│                                                         │
│  Loss:                                                  │
│    D: max log(D(x)) + log(1 - D(G(z)))                 │
│    G: min log(1 - D(G(z)))  or  max log(D(G(z)))       │
│                                                         │
│  GAN Variants:                                          │
│  • DCGAN: Deep Convolutional GAN                        │
│  • WGAN: Wasserstein GAN (stable training)              │
│  • CycleGAN: Unpaired image-to-image translation        │
│  • StyleGAN: High-quality face generation               │
│  • Pix2Pix: Paired image-to-image translation           │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 1.6 Diffusion Models

```
┌─────────────────────────────────────────────────────────┐
│              DIFFUSION PROCESS                           │
│                                                         │
│  Forward (noising):                                     │
│  x_0 ──▶ x_1 ──▶ x_2 ──▶ ... ──▶ x_T (pure noise)     │
│  q(x_t | x_{t-1}) = N(x_t; √(1-β_t)x_{t-1}, β_t I)    │
│                                                         │
│  Reverse (denoising):                                   │
│  x_T ──▶ x_{T-1} ──▶ ... ──▶ x_0 (generated image)     │
│  p_θ(x_{t-1} | x_t) = N(x_{t-1}; μ_θ(x_t, t), σ_t² I) │
│                                                         │
│  Training:                                              │
│  L = E[||ε - ε_θ(x_t, t)||²]                           │
│  Predict noise ε from noisy x_t at timestep t           │
│                                                         │
│  Variants:                                              │
│  • DDPM: Denoising Diffusion Probabilistic Model        │
│  • DDIM: Deterministic (faster sampling)                │
│  • Stable Diffusion: Latent diffusion (efficient)       │
│  • DALL-E 2: Prior + Decoder architecture               │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Training Optimization

### 2.1 Optimizer Comparison

| Optimizer | Formula | Best For | Notes |
|-----------|---------|----------|-------|
| **SGD** | θ = θ - η∇L | General, proven | Needs tuning, can escape sharp minima |
| **SGD + Momentum** | v = βv + ∇L; θ = θ - ηv | Faster convergence | β = 0.9 standard |
| **Adam** | m = β₁m + (1-β₁)g; v = β₂v + (1-β₂)g²; θ = θ - ηm/(√v + ε) | Default choice | β₁=0.9, β₂=0.999, ε=1e-8 |
| **AdamW** | Adam + decoupled weight decay | Transformers | Better generalization than Adam |
| **RMSProp** | v = βv + (1-β)g²; θ = θ - ηg/(√v + ε) | RNNs | Good for non-stationary |
| **AdaGrad** | G = G + g²; θ = θ - ηg/(√G + ε) | Sparse features | Learning rate decays too fast |
| **LAMB** | Layer-wise Adaptive Moments | Large batch training | Used for BERT pre-training |

### 2.2 Learning Rate Scheduling

```
┌─────────────────────────────────────────────────────────┐
│              LR SCHEDULES                                │
│                                                         │
│  Step Decay:                                            │
│  η_t = η_0 × γ^(⌊t/step_size⌋)                         │
│  Drop by factor γ every step_size epochs                │
│                                                         │
│  Cosine Annealing:                                      │
│  η_t = η_min + 0.5(η_max - η_min)(1 + cos(πt/T))       │
│  Smooth decay, good for fine-tuning                     │
│                                                         │
│  Warmup + Cosine:                                       │
│  η_t = η_max × t/warmup_steps  (t < warmup)            │
│  η_t = cosine_decay(t - warmup)  (t >= warmup)         │
│  Standard for Transformers                              │
│                                                         │
│  One Cycle:                                             │
│  Ramp up → Ramp down (single cycle)                     │
│  Fast training, good regularization                     │
│                                                         │
│  Reduce on Plateau:                                     │
│  If val_loss doesn't improve for patience epochs:       │
│    η = η × factor                                       │
│  Adaptive, safe choice                                  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 2.3 Regularization Techniques

| Technique | How | When to Use |
|-----------|-----|-------------|
| **Dropout** | Randomly zero out neurons (p=0.1-0.5) | FC layers, prevent co-adaptation |
| **Weight Decay (L2)** | Add λ||w||² to loss | Always, default 0.01 |
| **Batch Normalization** | Normalize per batch, learnable scale/shift | CNNs, stabilizes training |
| **Layer Normalization** | Normalize per sample | Transformers, RNNs |
| **Label Smoothing** | Soft targets: (1-ε)one_hot + ε/K | Classification, prevents overconfidence |
| **Early Stopping** | Stop when val_loss stops improving | Always, patience 10-20 epochs |
| **Data Augmentation** | Transform training data | CV, NLP (back-translation) |
| **Gradient Clipping** | Clip gradient norm to max_norm | RNNs, Transformers, prevent explosion |
| **Mixup/CutMix** | Blend samples and labels | CV, improves generalization |
| **Stochastic Depth** | Randomly skip layers | Deep ResNets |

---

## 3. Data Pipeline Design

### 3.1 ETL Pipeline Pattern

```
┌─────────────────────────────────────────────────────────┐
│              DATA PIPELINE                               │
│                                                         │
│  Raw Data ──▶ Extract ──▶ Transform ──▶ Load ──▶ Train │
│                                                         │
│  Extract:                                               │
│  • Sources: DB, API, files, streams                     │
│  • Format: Parquet, CSV, JSON, Avro                     │
│  • Validation: schema check, null check, range check    │
│                                                         │
│  Transform:                                             │
│  • Cleaning: handle missing, outliers, duplicates       │
│  • Feature Engineering: encode, scale, create features  │
│  • Augmentation: transform, noise, synthetic data       │
│  • Split: train/val/test (stratified if needed)         │
│                                                         │
│  Load:                                                  │
│  • Storage: TFRecord, HDF5, Parquet                     │
│  • Format: optimized for fast reading                   │
│  • Versioning: DVC, LakeFS                              │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 3.2 Feature Engineering Patterns

| Data Type | Techniques |
|-----------|------------|
| **Numerical** | StandardScaler, MinMaxScaler, RobustScaler, log transform, binning |
| **Categorical** | One-hot, Label encoding, Target encoding, Embedding |
| **Text** | TF-IDF, Word2Vec, BERT embeddings, n-grams |
| **Time** | Lag features, rolling stats, Fourier features, time since event |
| **Image** | Resize, normalize, augment (flip, rotate, crop, color jitter) |
| **Graph** | Node degree, centrality, community, node2vec embeddings |

### 3.3 Data Augmentation

```python
# Image Augmentation Pipeline
transform = transforms.Compose([
    transforms.RandomResizedCrop(224, scale=(0.8, 1.0)),
    transforms.RandomHorizontalFlip(p=0.5),
    transforms.RandomRotation(15),
    transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
    transforms.RandomAffine(degrees=0, translate=(0.1, 0.1)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                         std=[0.229, 0.224, 0.225]),
    transforms.RandomErasing(p=0.25),
])

# Text Augmentation
def augment_text(text):
    strategies = [
        synonym_replacement,    # Replace words with synonyms
        random_insertion,       # Insert random words
        random_swap,            # Swap word positions
        random_deletion,        # Delete words randomly
        back_translation,       # Translate to other language and back
    ]
    return random.choice(strategies)(text)
```

---

## 4. Model Evaluation

### 4.1 Metrics by Task

| Task | Metrics | When to Use |
|------|---------|-------------|
| **Classification (balanced)** | Accuracy, F1, ROC-AUC | Balanced classes |
| **Classification (imbalanced)** | Precision, Recall, F1, PR-AUC, MCC | Imbalanced classes |
| **Multi-class** | Macro/Micro F1, Confusion Matrix | Multiple classes |
| **Regression** | MAE, MSE, RMSE, R², MAPE | Continuous output |
| **Ranking** | NDCG, MAP, MRR | Search, recommendation |
| **Object Detection** | mAP, IoU | Detection tasks |
| **Segmentation** | IoU, Dice, Pixel Accuracy | Segmentation tasks |
| **Generation** | BLEU, ROUGE, Perplexity, FID | Text/image generation |

### 4.2 Cross-Validation Strategies

```
┌─────────────────────────────────────────────────────────┐
│              CROSS-VALIDATION                            │
│                                                         │
│  K-Fold:                                                │
│  [Train Train Train Val]                                │
│  [Train Train Val Train]  → K=4                         │
│  [Train Val Train Train]                                │
│  [Val Train Train Train]                                │
│                                                         │
│  Stratified K-Fold:                                     │
│  Same as K-Fold but preserves class distribution        │
│  Use for: imbalanced classification                     │
│                                                         │
│  Time Series Split:                                     │
│  [Train] [Val]                                          │
│  [Train Train] [Val]                                    │
│  [Train Train Train] [Val]                              │
│  Use for: time-dependent data                           │
│                                                         │
│  Group K-Fold:                                          │
│  Same group always in train or val (never split)        │
│  Use for: patient data, user data                       │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 4.3 Confusion Matrix Analysis

```
┌─────────────────────────────────────────────────────────┐
│              CONFUSION MATRIX                            │
│                                                         │
│                  Predicted                               │
│                  Positive    Negative                    │
│  Actual  Positive   TP          FN         │             │
│          Negative   FP          TN         │             │
│                                                         │
│  Metrics:                                               │
│  Accuracy  = (TP + TN) / (TP + TN + FP + FN)           │
│  Precision = TP / (TP + FP)     → "When I say positive,│
│                                    how often am I right?"│
│  Recall    = TP / (TP + FN)     → "Of all positives,    │
│                                    how many did I find?" │
│  F1        = 2 × (Precision × Recall) / (P + R)        │
│  Specificity = TN / (TN + FP)   → "True negative rate"  │
│                                                         │
│  Trade-off:                                             │
│  ↑ Precision → ↓ Recall (conservative predictions)      │
│  ↑ Recall → ↓ Precision (aggressive predictions)        │
│  Adjust threshold to balance based on business needs    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 5. Hyperparameter Tuning

### 5.1 Search Strategies

| Strategy | How | Pros | Cons |
|----------|-----|------|------|
| **Grid Search** | Try all combinations | Exhaustive, simple | Exponential cost |
| **Random Search** | Random sampling | Better than grid, parallel | No learning from past |
| **Bayesian Optimization** | Model the objective function | Sample efficient | Sequential, complex |
| **Hyperband** | Successive halving | Fast, resource efficient | May discard good configs |
| **Optuna** | Tree-structured Parzen | State-of-the-art, pruning | Library dependency |

### 5.2 Hyperparameter Ranges (Rules of Thumb)

| Hyperparameter | Range | Notes |
|---------------|-------|-------|
| **Learning Rate** | 1e-5 to 1e-1 | Log-uniform sampling |
| **Batch Size** | 16, 32, 64, 128, 256 | Power of 2, larger = faster but less regularization |
| **Hidden Size** | 64, 128, 256, 512, 768, 1024 | Power of 2, depends on data complexity |
| **Number of Layers** | 1 to 12+ | More layers = more capacity but harder to train |
| **Dropout** | 0.0 to 0.5 | 0.1-0.3 for small nets, 0.3-0.5 for large |
| **Weight Decay** | 1e-6 to 1e-2 | Log-uniform, 0.01 standard for AdamW |
| **Optimizer** | Adam, AdamW, SGD | AdamW default, SGD for final fine-tuning |

---

## 6. Transfer Learning & Fine-Tuning

### 6.1 Transfer Learning Strategies

```
┌─────────────────────────────────────────────────────────┐
│              TRANSFER LEARNING STRATEGIES                │
│                                                         │
│  Strategy 1: Feature Extraction                         │
│  ┌─────────────────┐                                    │
│  │ Pre-trained CNN │ ← Frozen                           │
│  └────────┬────────┘                                    │
│           ▼                                             │
│  ┌─────────────────┐                                    │
│  │ New Classifier  │ ← Train from scratch               │
│  └─────────────────┘                                    │
│  Use when: Small dataset, similar domain                │
│                                                         │
│  Strategy 2: Fine-Tuning (All Layers)                   │
│  ┌─────────────────┐                                    │
│  │ Pre-trained CNN │ ← Unfrozen, low LR                 │
│  └────────┬────────┘                                    │
│           ▼                                             │
│  ┌─────────────────┐                                    │
│  │ New Classifier  │ ← Train from scratch               │
│  └─────────────────┘                                    │
│  Use when: Large dataset, similar domain                │
│                                                         │
│  Strategy 3: Gradual Unfreezing                         │
│  1. Train classifier head (frozen backbone)             │
│  2. Unfreeze last layer group, train                    │
│  3. Unfreeze more, train with lower LR                  │
│  4. Repeat until all layers unfrozen                    │
│  Use when: Dataset size medium, want best performance   │
│                                                         │
│  Strategy 4: Discriminative LR                          │
│  Early layers: LR = base_lr / 100  (keep pretrained)   │
│  Middle layers: LR = base_lr / 10                       │
│  Late layers: LR = base_lr                              │
│  Head: LR = base_lr × 10                                │
│  Use when: Fine-tuning with risk of catastrophic forgetting│
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 6.2 LLM Fine-Tuning

| Method | GPU Memory | Quality | Speed |
|--------|-----------|---------|-------|
| **Full Fine-Tuning** | Very High | Best | Slow |
| **LoRA** | Low | Near-full | Fast |
| **QLoRA** | Very Low | Near-LoRA | Fast |
| **Prompt Tuning** | Very Low | Good | Fastest |
| **P-Tuning v2** | Low | Good | Fast |
| **RLHF** | High | Best alignment | Very slow |

---

## 7. MLOps Pipeline

### 7.1 ML Pipeline Architecture

```
┌─────────────────────────────────────────────────────────┐
│              MLOPS PIPELINE                              │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │  DATA    │─▶│ TRAINING │─▶│ EVALUATE │─▶│ REGISTER│ │
│  │ VERSION  │  │ EXPERIMENT│  │  & TUNE  │  │  MODEL  │ │
│  │ (DVC)    │  │ (MLflow) │  │          │  │         │ │
│  └──────────┘  └──────────┘  └──────────┘  └────┬────┘ │
│                                                  │      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────▼────┐ │
│  │ MONITOR  │◀─│  SERVE   │◀─│  DEPLOY  │◀─│  STAGE  │ │
│  │ & ALERT  │  │ (API)    │  │ (CI/CD)  │  │ (Staging)│ │
│  │ (Prometheus)│ │         │  │          │  │         │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
│                                                         │
│  Feedback Loop: Monitor → Detect drift → Retrain → Deploy│
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 7.2 Experiment Tracking

```python
import mlflow

with mlflow.start_run(run_name="experiment_001"):
    # Log parameters
    mlflow.log_params({
        "learning_rate": 0.001,
        "batch_size": 32,
        "epochs": 100,
        "model": "resnet50",
    })

    # Log metrics per epoch
    for epoch in range(epochs):
        train_loss, val_loss, val_acc = train_epoch()
        mlflow.log_metrics({
            "train_loss": train_loss,
            "val_loss": val_loss,
            "val_accuracy": val_acc,
        }, step=epoch)

    # Log model
    mlflow.pytorch.log_model(model, "model")

    # Log artifacts
    mlflow.log_artifact("confusion_matrix.png")
    mlflow.log_artifact("training_curve.png")
```

### 7.3 Model Deployment Patterns

| Pattern | Description | Use Case |
|---------|-------------|----------|
| **Batch Inference** | Process data in batches | Offline predictions, nightly jobs |
| **Real-time API** | REST/gRPC endpoint | User-facing predictions |
| **Edge Deployment** | Model on device (mobile, IoT) | Low latency, offline, privacy |
| **Streaming** | Process data streams | Real-time anomaly detection |
| **A/B Testing** | Serve multiple models, compare | Model selection, gradual rollout |
| **Shadow Mode** | Run new model alongside old, compare | Safe testing before switching |

### 7.4 Model Monitoring

| Metric | What to Track | Alert Threshold |
|--------|--------------|-----------------|
| **Data Drift** | Input distribution change | PSI > 0.2 |
| **Concept Drift** | P(y|x) change over time | Accuracy drop > 5% |
| **Prediction Drift** | Output distribution change | Significant shift |
| **Latency** | Inference time | p99 > SLA |
| **Throughput** | Requests per second | Below capacity |
| **Error Rate** | Failed predictions | > 1% |
| **Data Quality** | Missing values, outliers | > 5% missing |

---

## 8. Production ML Patterns

### 8.1 Feature Store Pattern

```
┌─────────────────────────────────────────────────────────┐
│              FEATURE STORE                               │
│                                                         │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │  Offline     │    │  Online      │                   │
│  │  Store       │    │  Store       │                   │
│  │  (Parquet/   │◀──▶│  (Redis/     │                   │
│  │   BigQuery)  │    │   DynamoDB)  │                   │
│  └──────┬───────┘    └──────┬───────┘                   │
│         │                   │                            │
│         ▼                   ▼                            │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │  Training    │    │  Inference   │                   │
│  │  Pipeline    │    │  Service     │                   │
│  └──────────────┘    └──────────────┘                   │
│                                                         │
│  Benefits:                                              │
│  • Consistent features between training & inference     │
│  • Feature reuse across teams                           │
│  • Point-in-time correctness                            │
│  • Feature versioning                                   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 8.2 ML Anti-Patterns

| Anti-Pattern | Symptom | Fix |
|--------------|---------|-----|
| **Training-Serving Skew** | Model works in training, fails in production | Use feature store, same preprocessing |
| **Data Leakage** | Unrealistically high training accuracy | Check temporal order, remove future info |
| **No Baseline** | Can't tell if model is good | Always compare to simple baseline |
| **Overfitting to Test Set** | Test score drops after deployment | Hold out final test set, never touch during development |
| **No Monitoring** | Model degrades silently | Track drift, accuracy, latency |
| **Big Model for Simple Problem** | Overkill, slow, expensive | Start simple, add complexity only if needed |
| **Ignoring Class Imbalance** | Model predicts majority class always | Resample, class weights, focal loss |
| **No Reproducibility** | Can't recreate results | Seed everything, version data + code + config |

---

## 9. Deep Learning Design Checklist

- [ ] **Problem type identified**: Classification, regression, generation, etc.
- [ ] **Architecture selected**: Based on data type and task
- [ ] **Data pipeline built**: ETL, validation, augmentation
- [ ] **Train/val/test split**: Stratified or time-based as appropriate
- [ ] **Baseline established**: Simple model as reference point
- [ ] **Loss function chosen**: Appropriate for task and data
- [ ] **Optimizer selected**: AdamW default, SGD for fine-tuning
- [ ] **LR schedule set**: Warmup + cosine for Transformers
- [ ] **Regularization applied**: Dropout, weight decay, early stopping
- [ ] **Gradient clipping**: For RNNs and Transformers
- [ ] **Mixed precision**: FP16/BF16 for faster training
- [ ] **Experiment tracking**: MLflow, Weights & Biases
- [ ] **Reproducibility**: Seeds fixed, versions logged
- [ ] **Evaluation metrics**: Appropriate for task and business needs
- [ ] **Error analysis**: Confusion matrix, failure cases examined
- [ ] **Deployment plan**: Batch, real-time, edge, or streaming
- [ ] **Monitoring set up**: Drift detection, latency, accuracy tracking
